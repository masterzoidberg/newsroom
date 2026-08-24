"""Provider-neutral evaluation measures for Phase 27 Story corrections.

These measures intentionally sit beside, rather than alter, the existing
pairwise clustering metrics. They score the durable current/historical
contracts and expose correction burden as a separate operational measure.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _ratio(matches: int, total: int) -> float:
    return matches / total if total else 1.0


def _exact_mapping_accuracy(expected: Mapping[str, Any], observed: Mapping[str, Any]) -> float:
    return _ratio(sum(observed.get(key) == value for key, value in expected.items()), len(expected))


def _set_mapping_accuracy(
    expected: Mapping[str, Sequence[str]], observed: Mapping[str, Sequence[str]]
) -> float:
    return _ratio(
        sum(set(observed.get(key, ())) == set(value) for key, value in expected.items()),
        len(expected),
    )


def story_correction_metrics(
    *,
    current_membership_expected: Mapping[str, str | None],
    current_membership_observed: Mapping[str, str | None],
    historical_membership_expected: Mapping[str, Sequence[str]],
    historical_membership_observed: Mapping[str, Sequence[str]],
    merge_expected: Mapping[str, str | None],
    merge_observed: Mapping[str, str | None],
    split_expected: Mapping[str, Sequence[str]],
    split_observed: Mapping[str, Sequence[str]],
    stale_context_expected: Mapping[str, Sequence[str]],
    stale_context_observed: Mapping[str, Sequence[str]],
    automatic_assignment_count: int,
    manual_correction_count: int,
) -> dict[str, float | int | None]:
    """Score Phase 27 correction outcomes without changing baseline metrics."""
    if automatic_assignment_count < 0 or manual_correction_count < 0:
        raise ValueError("correction counts cannot be negative")
    return {
        "current_membership_correctness": _exact_mapping_accuracy(
            current_membership_expected, current_membership_observed
        ),
        "historical_membership_correctness": _set_mapping_accuracy(
            historical_membership_expected, historical_membership_observed
        ),
        "merge_correctness": _exact_mapping_accuracy(merge_expected, merge_observed),
        "split_correctness": _set_mapping_accuracy(split_expected, split_observed),
        "stale_context_correctness": _set_mapping_accuracy(
            stale_context_expected, stale_context_observed
        ),
        "automatic_assignment_count": automatic_assignment_count,
        "manual_correction_count": manual_correction_count,
        "automatic_assignment_correction_burden": (
            manual_correction_count * 100.0 / automatic_assignment_count
            if automatic_assignment_count
            else None
        ),
    }


__all__ = ["story_correction_metrics"]
