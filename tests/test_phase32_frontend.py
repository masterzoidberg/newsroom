from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def test_ast32_watch_setup_explains_recommendation_review_and_source_health():
    view = (FRONTEND / "views" / "WatchManagementView.tsx").read_text(encoding="utf-8")

    for label in (
        "Recommended Sources",
        "unverified",
        "Recommendation provenance",
        "Manual fallback",
        "Source health",
        "Last failure",
        "Retry source",
        "Approve",
        "Reject",
    ):
        assert label in view

    for contract in (
        "source_discovery",
        "last_result",
        "last_run_at",
        "/monitors/",
        "source-candidates",
    ):
        assert contract in view


def test_ast32_sources_admin_surface_keeps_health_and_partial_failures_visible():
    view = (FRONTEND / "views" / "AdminViews.tsx").read_text(encoding="utf-8")

    for label in (
        "Source health",
        "Last failure",
        "Retry source",
        "successful sibling",
        "source_id",
        "/diagnostics",
    ):
        assert label in view
