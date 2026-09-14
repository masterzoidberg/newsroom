from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def test_ast29_terminology_review_exposes_distinct_safe_review_states():
    view = (FRONTEND / "views" / "WatchManagementView.tsx").read_text(encoding="utf-8")
    types = (FRONTEND / "lib" / "types.ts").read_text(encoding="utf-8")

    for label in (
        "Review terminology",
        "Suggested terminology",
        "Approved monitoring scope",
        "Rejected terminology",
        "Manual terms always available",
        "Provider route and cost",
        "Save edited term",
    ):
        assert label in view
    for contract in ("getAIStatus", "vocabulary/suggest", "expansion_of", "rationale"):
        assert contract in view
    for status in ('status === "suggested"', 'status === "approved"', 'status === "rejected"'):
        assert status in view
    assert "WatchVocabularyTerm" in types
    assert "VocabularyKind" in types


def test_watch_setup_keeps_question_name_and_primary_term_independent():
    view = (FRONTEND / "views" / "WatchManagementView.tsx").read_text(encoding="utf-8")
    inbox = (FRONTEND / "views" / "InboxView.tsx").read_text(encoding="utf-8")

    assert 'name: current.name,' in view
    assert 'term_draft: current.term_draft' in view
    assert "Seeded from your interest; edit before confirming" not in view
    assert "drives exact relevance matching and the initial Watch query variants" in view
    assert "AI and synonym proposals remain separate review-only suggestions after setup" in view
    assert "give the Watch its own short name" in inbox
    assert "optional AI terminology suggestions can be reviewed after saving" in inbox


def test_watch_setup_can_discard_only_the_unsubmitted_draft():
    view = (FRONTEND / "views" / "WatchManagementView.tsx").read_text(encoding="utf-8")

    assert "setupDraftHasContent" in view
    assert "Discard this Watch draft?" in view
    assert "Discard Watch draft" in view
    assert "window.sessionStorage.removeItem(SETUP_DRAFT_KEY)" in view
    assert "if (pendingSubmission || !setupDraftHasContent(setupDraft)) return;" in view


def test_ai_provider_settings_has_minimax_token_plan_preset():
    view = (ROOT / "frontend" / "src" / "components" / "AIProviderSettings.tsx").read_text(encoding="utf-8")

    for label in (
        "MiniMax Token Plan",
        "MiniMax Token Plan subscription key",
        "https://api.minimax.cn/v1",
        "MiniMax-M3",
        "subscription key here, not its separate pay-as-you-go API key",
        "Get a Token Plan key",
    ):
        assert label in view
    assert "Provider preset" in view
    assert "https://platform.minimaxi.com/user-center/payment/token-plan" in view
