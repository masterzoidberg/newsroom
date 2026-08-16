"""Standalone Newsroom evaluation subsystem.

Evaluation is a permanent product subsystem, not disposable test glue. This
package provides the versioned evaluation data contract, corpus loading and
validation, deterministic replay, reproducible metrics, the v1 baseline, and a
developer CLI.

No live web access, Hermes, paid API, or the production v1 database is required
for normal use.
"""

from __future__ import annotations

from .taxonomy import (
    CASE_TYPES,
    CASE_TYPE_LABELS,
    CLAIM_STATES,
    EVIDENCE_RELATIONSHIPS,
    IMPORTANCES,
    MONITOR_TARGET_KINDS,
)

__all__ = [
    "SCHEMA_VERSION",
    "CASE_TYPES",
    "CASE_TYPE_LABELS",
    "CLAIM_STATES",
    "EVIDENCE_RELATIONSHIPS",
    "IMPORTANCES",
    "MONITOR_TARGET_KINDS",
]

SCHEMA_VERSION = 1
