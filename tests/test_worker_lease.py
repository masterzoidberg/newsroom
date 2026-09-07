from __future__ import annotations

import threading
import time

from newsroom.jobs import JobService
from newsroom.migrations import apply_migrations
from newsroom.worker import WorkerProcess


def test_worker_renews_long_handler_lease_and_cancellation_does_not_duplicate(tmp_db):
    apply_migrations(tmp_db)
    queue = JobService(tmp_db, lease_seconds=2, backoff_base_seconds=1)
    job = queue.enqueue("long_fixture", {}, max_attempts=2)
    entered = threading.Event()
    release = threading.Event()
    result_box = []

    def handler(_job):
        entered.set()
        assert release.wait(5)
        return {"done": True}

    worker = WorkerProcess(tmp_db, {"long_fixture": handler}, worker_id="worker-a", queue=queue)
    thread = threading.Thread(target=lambda: result_box.append(worker.run_once()), daemon=True)
    thread.start()
    assert entered.wait(2)

    queue.cancel(job["id"], reason="test_cancel")
    time.sleep(2.4)  # beyond the original lease; renewer must preserve ownership
    competing = JobService(tmp_db, lease_seconds=2, backoff_base_seconds=1)
    assert competing.recover_expired() == 0
    assert competing.claim(job["id"], "worker-b") is None

    release.set()
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert result_box[0]["status"] == "cancelled"
    final = queue.get(job["id"])
    assert final["status"] == "cancelled"
    assert final["attempts"] == 1
    assert final["attempts_detail"][0]["status"] == "cancelled"
