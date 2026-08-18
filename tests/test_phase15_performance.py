from __future__ import annotations

import statistics
import time

from fastapi.testclient import TestClient

from newsroom.acquisition import AcquisitionService, HttpResponse
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.domain import CoreService
from newsroom.jobs import JobService
from newsroom.migrations import apply_migrations
from newsroom.workbench import SearchService


def test_representative_single_user_search_queue_and_database_workload_stays_bounded(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Scale source", "slug": "scale-source"})
    for index in range(250):
        core.create_document(
            {
                "source_id": source["id"],
                "canonical_url": f"https://scale.test/story-{index}",
                "title": f"Atlas representative workload story {index}",
            }
        )

    queue = JobService(tmp_db)
    queue_started = time.perf_counter()
    for index in range(100):
        queue.enqueue("fixture", {"index": index}, idempotency_key=f"phase15-{index}")
    queue_elapsed = time.perf_counter() - queue_started
    assert queue_elapsed < 5.0
    assert queue.list(page=1, page_size=100)["total"] == 100

    search = SearchService(tmp_db)
    timings = []
    for _ in range(3):
        started = time.perf_counter()
        result = search.search("Atlas representative", page=1, page_size=25)
        timings.append((time.perf_counter() - started) * 1000)
        assert result["total"] == 250
    assert statistics.median(timings) < 1000


def test_representative_acquisition_and_api_workload_stays_bounded(tmp_db, tmp_path):
    apply_migrations(tmp_db)
    source = CoreService(tmp_db).create_source({"name": "Acquisition scale source", "slug": "acquisition-scale"})

    class FixtureTransport:
        def get(self, url, *, headers, policy):
            return HttpResponse(200, url, {"content-type": "text/plain"}, b"bounded fixture content")

    acquisition = AcquisitionService(tmp_db, transport=FixtureTransport())
    started = time.perf_counter()
    for index in range(25):
        result = acquisition.acquire_document(source["id"], f"https://scale.test/document-{index}")
        assert result.outcome == "retrieved"
    assert time.perf_counter() - started < 5.0

    app = create_app(
        config=RuntimeConfig.for_environment("dev", root=tmp_path / "dev"),
        frontend_dist=tmp_path / "missing-dist",
    )
    with TestClient(app) as client:
        timings = []
        for _ in range(20):
            started = time.perf_counter()
            response = client.get("/api/v1/health")
            timings.append((time.perf_counter() - started) * 1000)
            assert response.status_code == 200
    assert statistics.median(timings) < 250
