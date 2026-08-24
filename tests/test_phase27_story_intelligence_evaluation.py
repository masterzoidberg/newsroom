from newsroom.evals.story_intelligence import story_correction_metrics


def test_story_correction_metrics_keep_history_separate_from_current_state():
    result = story_correction_metrics(
        current_membership_expected={"claim-a": "story-b", "claim-b": None},
        current_membership_observed={"claim-a": "story-b", "claim-b": None},
        historical_membership_expected={"claim-a": ["story-a", "story-b"], "claim-b": ["story-a"]},
        historical_membership_observed={"claim-a": ["story-a", "story-b"], "claim-b": ["story-a"]},
        merge_expected={"story-a": "story-b"},
        merge_observed={"story-a": "story-b"},
        split_expected={"story-c": ["story-d", "story-e"]},
        split_observed={"story-c": ["story-e", "story-d"]},
        stale_context_expected={"story-a": ["document-old"], "story-b": ["document-new"]},
        stale_context_observed={"story-a": ["document-old"], "story-b": ["document-new"]},
        automatic_assignment_count=4,
        manual_correction_count=1,
    )
    assert result["current_membership_correctness"] == 1.0
    assert result["historical_membership_correctness"] == 1.0
    assert result["merge_correctness"] == 1.0
    assert result["split_correctness"] == 1.0
    assert result["stale_context_correctness"] == 1.0
    assert result["automatic_assignment_correction_burden"] == 25.0
