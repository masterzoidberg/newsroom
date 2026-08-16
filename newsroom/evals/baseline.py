"""v1 (Hermes Newsroom) baseline.

The v1 baseline scores the completed reference implementation's *actual*
grouping behavior against the human gold labels, using a committed metadata-only
export of v1 stories/sources (no article bodies, no live database access).

v1 had no Claim/Evidence Ledger, so claim-level and evidence-level metrics are
not computed for the v1 baseline; the event/grouping and primary-source metrics
are the meaningful comparison. This limitation is documented in
``docs/EVALUATION.md`` and surfaced in the result summary.

The export is regenerated from a read-only v1 SQLite database by
:func:`extract_v1_db`, which never opens the database for writing.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .corpus import evals_dir
from .prediction import (
    Prediction,
    PredictedStoryGroup,
    UsageRecord,
    validate_prediction,
)
from .metrics import score, ScoreResult
from .schema import EvaluationCase

SYSTEM_NAME = "hermes-v1"

# Explicit, reviewed mapping that ties v1 rows to corpus candidates. Each entry
# names the profile (dev/prod) the story came from so the two isolated v1
# databases can be read side-by-side without conflating their rows.
V1_MAPPING: list[dict] = [
    {
        "db": "dev",
        "story_id": "st_18914797405a3cab",
        "case_id": "multi-outlet-hermes-v0200",
        "sources": {
            "https://github.com/NousResearch/hermes-agent/releases/tag/v2026.8.3": "github-v0200",
            "https://hermesatlas.com/guide": "hermesatlas-guide",
        },
    },
    {
        "db": "dev",
        "story_id": "st_0de940cc3c4ee044",
        "case_id": "duplicate-syndication-hermes-v0201",
        "sources": {
            "https://github.com/NousResearch/hermes-agent/releases/tag/v2026.8.13": "github-v0201-dev",
        },
    },
    {
        "db": "prod",
        "story_id": "st_689a3b0afb284b26",
        "case_id": "duplicate-syndication-hermes-v0201",
        "sources": {
            "https://github.com/NousResearch/hermes-agent/releases/tag/v2026.8.13": "github-v0201-prod",
        },
    },
    {
        "db": "dev",
        "story_id": "st_a28ea22dea867c95",
        "case_id": "primary-vs-secondary-nous-funding",
        "sources": {
            "https://techcrunch.com/2026/07/13/hermes-agent-maker-nous-research-in-talks-for-new-funding-at-1-5b-valuation": "techcrunch-funding",
        },
    },
    {
        "db": "dev",
        "story_id": "st_49fa81b2eba911af",
        "case_id": "similar-distinct-hermes-events",
        "sources": {
            "https://github.com/NousResearch/hermes-agent/pull/80593": "pr-portable-plugins",
        },
    },
    {
        "db": "dev",
        "story_id": "st_3ca5b4726b3d4f7c",
        "case_id": "similar-distinct-hermes-events",
        "sources": {
            "https://vercel.com/changelog/vercel-ai-gateway-and-vercel-sandbox-now-available-on-hermes-agent": "vercel-integration",
        },
    },
    {
        "db": "dev",
        "story_id": "st_166579af265cace9",
        "case_id": "similar-distinct-hermes-events",
        "sources": {
            "https://github.com/nesquena/hermes-webui/pull/4955": "webui-4955",
        },
    },
    {
        "db": "dev",
        "story_id": "st_fb665c5aa0cf4147",
        "case_id": "similar-distinct-hermes-events",
        "sources": {
            "https://github.com/nesquena/hermes-webui/pull/6036": "webui-6036",
        },
    },
]


def v1_export_path() -> Path:
    return evals_dir() / "baseline" / "v1_predictions.json"


@dataclass(frozen=True)
class V1Export:
    system: str
    source_db: str
    generated_at: str
    note: str
    predictions: tuple[Prediction, ...]


def load_v1_export(path: Optional[str | Path] = None) -> V1Export:
    p = Path(path) if path is not None else v1_export_path()
    with open(p, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    preds = tuple(validate_prediction(d) for d in data.get("predictions", []))
    return V1Export(
        system=data.get("system", SYSTEM_NAME),
        source_db=data.get("source_db", ""),
        generated_at=data.get("generated_at", ""),
        note=data.get("note", ""),
        predictions=preds,
    )


def run_baseline(
    cases: dict[str, EvaluationCase],
    export: Optional[V1Export] = None,
) -> list[ScoreResult]:
    """Score v1 against each gold case, merging multiple v1 stories that
    belong to the same case into a single prediction."""
    if export is None:
        export = load_v1_export()

    # Merge predictions by case so a case with several v1 stories is scored
    # once, as one system.
    by_case: dict[str, list[Prediction]] = {}
    for pred in export.predictions:
        by_case.setdefault(pred.case_id, []).append(pred)

    results: list[ScoreResult] = []
    for case_id, preds in sorted(by_case.items()):
        case = cases.get(case_id)
        if case is None:
            continue
        merged_groups = [g for p in preds for g in p.story_groups]
        merged_primary = [c for p in preds for c in p.primary_sources]
        merged = Prediction(
            prediction_id=f"v1-{case_id}",
            case_id=case_id,
            system=SYSTEM_NAME,
            story_groups=tuple(merged_groups),
            claims=(),
            evidence=(),
            contradictions=(),
            primary_sources=tuple(merged_primary),
            synthesized_propositions=(),
            usage=UsageRecord(),
        )
        results.append(score(case, merged))
    return results


def _connect_ro(db_path: str | Path) -> sqlite3.Connection:
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _story_prediction(conn: sqlite3.Connection, mapping: dict) -> dict | None:
    story_id = mapping["story_id"]
    row = conn.execute(
        "SELECT id, headline, event_key FROM stories WHERE id = ?", (story_id,)
    ).fetchone()
    if row is None:
        return None
    sources = conn.execute(
        "SELECT url, is_primary FROM sources WHERE story_id = ?", (story_id,)
    ).fetchall()

    candidate_ids: list[str] = []
    primary: list[str] = []
    for s in sources:
        cid = mapping["sources"].get(s["url"])
        if cid is None:
            continue
        candidate_ids.append(cid)
        if s["is_primary"]:
            primary.append(cid)

    if not candidate_ids:
        return None

    return {
        "prediction_id": f"v1-{story_id}",
        "case_id": mapping["case_id"],
        "system": SYSTEM_NAME,
        "story_groups": [{"story_id": story_id, "candidate_ids": candidate_ids}],
        "claims": [],
        "evidence": [],
        "contradictions": [],
        "primary_sources": primary,
        "synthesized_propositions": [],
        "usage": {
            "acquisition_requests": 0,
            "paid_requests": 0,
            "local_model_calls": 0,
            "frontier_calls": 0,
            "latency_ms": 0,
            "cost_usd": 0.0,
        },
    }


def extract_v1_db(
    db_paths: dict[str, str | Path],
    *,
    mapping: Optional[list[dict]] = None,
    source_note: str = "",
) -> dict:
    """Extract the v1 baseline export from one or more v1 SQLite databases.

    ``db_paths`` maps a profile name (e.g. ``"dev"``/``"prod"``) to a database
    path. Every database is opened with ``mode=ro`` so the reference data is
    never written. Returns the export dict (for serialization to JSON).
    """
    predictions: list[dict] = []
    for m in (mapping or V1_MAPPING):
        db_path = db_paths.get(m["db"])
        if db_path is None:
            continue
        conn = _connect_ro(db_path)
        try:
            pred = _story_prediction(conn, m)
        finally:
            conn.close()
        if pred is not None:
            predictions.append(pred)

    return {
        "export_version": 1,
        "system": SYSTEM_NAME,
        "source_db": str(db_paths),
        "source_note": source_note,
        "note": (
            "Metadata-only export of v1 story groupings and primary sources. "
            "No article bodies. Claim/evidence metrics are N/A for v1 because "
            "v1 had no Claim/Evidence Ledger."
        ),
        "predictions": predictions,
    }
