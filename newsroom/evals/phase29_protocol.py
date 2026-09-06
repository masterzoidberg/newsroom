"""Small operator-layer helpers for the Phase 29 evaluation protocol.

The benchmark runners remain the authority for execution and contract checks.
This module only records the surrounding protocol state needed for a resumable,
blinded, auditable run.  It deliberately has no scoring logic.
"""
from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


PROTOCOL_VERSION = "phase29-evaluation-protocol-v1"
DEFAULT_BLIND_SEED = 20260906


class Phase29ProtocolError(ValueError):
    """A protocol artifact or execution record is not safe to continue."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_blind_plan(
    question_ids: Sequence[str],
    *,
    seed: int = DEFAULT_BLIND_SEED,
) -> dict[str, Any]:
    """Create the reproducible question order and A/B assignment.

    The returned mapping is operator-only.  It must not be copied into the
    scorer-facing blind output until scoring is complete.
    """

    ids = [str(question_id) for question_id in question_ids]
    if not ids or len(set(ids)) != len(ids):
        raise Phase29ProtocolError("blind plan requires unique question IDs")
    rng = random.Random(seed)
    order = list(ids)
    rng.shuffle(order)
    mapping: dict[str, dict[str, Any]] = {}
    for position, question_id in enumerate(order, start=1):
        labels = ["system-a", "system-b"]
        rng.shuffle(labels)
        mapping[question_id] = {
            "position": position,
            "full_label": labels[0],
            "lite_label": labels[1],
        }
    return {
        "protocol_version": PROTOCOL_VERSION,
        "blind_seed": seed,
        "question_order": order,
        "mapping": mapping,
    }


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_snapshot_timestamps(db_path: str | Path) -> list[dict[str, Any]]:
    path = Path(db_path).resolve()
    if not path.is_file():
        raise Phase29ProtocolError(f"snapshot does not exist: {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute(
                """
                SELECT document_versions.id AS document_version_id,
                       document_versions.document_id AS document_id,
                       document_versions.retrieved_at AS retrieved_at,
                       document_versions.content_hash AS content_hash,
                       documents.source_id AS source_id,
                       documents.published_at AS published_at
                FROM document_versions
                JOIN documents ON documents.id = document_versions.document_id
                ORDER BY document_versions.id
                """
            ).fetchall()
        except sqlite3.Error as exc:
            raise Phase29ProtocolError("snapshot lacks the authoritative document tables") from exc
        return [dict(row) for row in rows]
    finally:
        conn.close()


def snapshot_manifest(
    db_path: str | Path,
    *,
    manifest_hash: str,
    cutoff: str,
) -> dict[str, Any]:
    """Describe the evidence rows eligible under one frozen cutoff.

    This supplements the existing corpus hash with a cutoff audit.  It does
    not change the database or the frozen benchmark contract.
    """

    try:
        cutoff_dt = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Phase29ProtocolError(f"invalid UTC cutoff: {cutoff}") from exc
    rows = _read_snapshot_timestamps(db_path)
    eligible: list[str] = []
    excluded: list[str] = []
    for row in rows:
        retrieved_at = row.get("retrieved_at")
        if not isinstance(retrieved_at, str):
            excluded.append(str(row["document_version_id"]))
            continue
        try:
            retrieved_dt = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise Phase29ProtocolError(
                f"invalid retrieved_at for DocumentVersion {row['document_version_id']}"
            ) from exc
        if retrieved_dt <= cutoff_dt:
            eligible.append(str(row["document_version_id"]))
        else:
            excluded.append(str(row["document_version_id"]))
    return {
        "snapshot_path": str(Path(db_path).resolve()),
        "manifest_hash": manifest_hash,
        "cutoff": cutoff,
        "eligible_document_version_ids": eligible,
        "excluded_post_cutoff_document_version_ids": excluded,
        "row_identity_hash": _canonical_hash(rows),
    }


def _answer_refusal_state(result: Mapping[str, Any]) -> str:
    answer = result.get("answer")
    if not isinstance(answer, Mapping):
        return "unknown"
    status = answer.get("status")
    refusal_code = answer.get("refusal_code")
    if refusal_code:
        return f"refused:{refusal_code}"
    if status in {"refused", "insufficient_evidence", "uncertain"}:
        return str(status)
    return "answered"


def _execution_record(
    result: Mapping[str, Any],
    *,
    latency_ms: int,
    actual_cost_usd: float | None,
) -> dict[str, Any]:
    requested = result.get("requested_config")
    effective = result.get("effective_config")
    verification = result.get("contract_verification")
    if not isinstance(requested, Mapping) or not isinstance(effective, Mapping):
        raise Phase29ProtocolError("execution envelope lacks requested/effective configuration")
    if not isinstance(verification, Mapping):
        raise Phase29ProtocolError("execution envelope lacks contract verification")
    return {
        "requested_provider": requested.get("provider"),
        "requested_model": requested.get("model"),
        "effective_provider": effective.get("effective_provider"),
        "effective_model": effective.get("effective_model"),
        "relevant_requested_settings": dict(requested),
        "relevant_effective_settings": dict(effective),
        "paid_local_identity": {
            "provider_route": effective.get("provider_route"),
            "fallback_used": effective.get("fallback_used"),
            "test_double": result.get("test_double"),
        },
        "corpus_snapshot": result.get("frozen_corpus"),
        "cutoff": result.get("corpus_cutoff"),
        "question_contract_version": result.get("contract_id"),
        "latency_ms": latency_ms,
        "actual_cost_usd": actual_cost_usd,
        "cost_status": "provided" if actual_cost_usd is not None else "unavailable",
        "refusal_state": _answer_refusal_state(result),
        "execution_validity": dict(verification),
    }


def _blind_answer(result: Mapping[str, Any], label: str, execution: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "blind_label": label,
        "question_id": result.get("opaque_question_id"),
        "question": result.get("question"),
        "answer": result.get("answer"),
        "cited_document_ids": result.get("cited_document_ids", []),
        "refusal_state": execution.get("refusal_state"),
    }


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, sort_keys=True, default=str) + "\n")


class ResumablePairRecorder:
    """Persist one question-pair at a time without adding scoring behavior."""

    def __init__(
        self,
        output_dir: str | Path,
        *,
        identity: Mapping[str, Any],
        contract_id: str,
        corpus_cutoff: str,
        question_ids: Sequence[str],
        blind_seed: int = DEFAULT_BLIND_SEED,
    ):
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.output_dir / "run-manifest.json"
        self.mapping_path = self.output_dir / "blind-mapping.operator-only.json"
        self.raw_path = self.output_dir / "raw-envelopes.jsonl"
        self.blind_path = self.output_dir / "blind-answers.jsonl"
        self.question_ids = tuple(str(question_id) for question_id in question_ids)
        if not self.question_ids or len(set(self.question_ids)) != len(self.question_ids):
            raise Phase29ProtocolError("recorder requires unique question IDs")
        self.identity = dict(identity)
        self.plan = create_blind_plan(self.question_ids, seed=blind_seed)
        self._state = self._load_or_create_state(contract_id, corpus_cutoff)

    def _load_or_create_state(self, contract_id: str, corpus_cutoff: str) -> dict[str, Any]:
        expected = {
            "protocol_version": PROTOCOL_VERSION,
            "contract_id": contract_id,
            "corpus_cutoff": corpus_cutoff,
            "question_ids": list(self.question_ids),
            "question_order": self.plan["question_order"],
            "blind_seed": self.plan["blind_seed"],
            "identity": self.identity,
        }
        if self.manifest_path.exists():
            try:
                state = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise Phase29ProtocolError("cannot read existing evaluation manifest") from exc
            for key, value in expected.items():
                if state.get(key) != value:
                    raise Phase29ProtocolError(f"existing evaluation manifest mismatch: {key}")
            if not self.mapping_path.exists() or not self.raw_path.exists() or not self.blind_path.exists():
                raise Phase29ProtocolError("existing evaluation manifest has missing audit artifacts")
            return state

        state = {
            **expected,
            "status": "pending",
            "scoring_started": False,
            "identities_revealed": False,
            "scoring_complete": False,
            "attempts": [],
            "completed_question_ids": [],
            "artifacts": {
                "mapping": self.mapping_path.name,
                "raw_envelopes": self.raw_path.name,
                "blind_answers": self.blind_path.name,
            },
        }
        _write_json(self.mapping_path, self.plan)
        self.raw_path.touch()
        self.blind_path.touch()
        _write_json(self.manifest_path, state)
        return state

    @property
    def completed_question_ids(self) -> tuple[str, ...]:
        return tuple(self._state.get("completed_question_ids", []))

    @property
    def status(self) -> str:
        return str(self._state.get("status", "pending"))

    def record_pair(
        self,
        pair: Mapping[str, Any],
        *,
        latency_ms: int,
        actual_cost_usd: Mapping[str, float | None] | None = None,
    ) -> dict[str, Any]:
        question_id = str(pair.get("question_id") or "")
        if question_id not in self.question_ids:
            raise Phase29ProtocolError(f"pair question is outside the frozen question set: {question_id}")
        if question_id in self.completed_question_ids:
            return self._state
        full = pair.get("full")
        lite = pair.get("lite")
        if not isinstance(full, Mapping) or not isinstance(lite, Mapping):
            raise Phase29ProtocolError("pair must contain Full and Lite envelopes")
        full_execution = _execution_record(
            full,
            latency_ms=latency_ms,
            actual_cost_usd=(actual_cost_usd or {}).get("full"),
        )
        lite_execution = _execution_record(
            lite,
            latency_ms=latency_ms,
            actual_cost_usd=(actual_cost_usd or {}).get("lite"),
        )
        full_valid = bool(full_execution["execution_validity"].get("valid"))
        lite_valid = bool(lite_execution["execution_validity"].get("valid"))
        pair_valid = bool(pair.get("pair_valid", True)) and full_valid and lite_valid
        attempt = sum(1 for item in self._state["attempts"] if item.get("question_id") == question_id) + 1
        record = {
            "question_id": question_id,
            "attempt": attempt,
            "recorded_at": utc_now(),
            "pair_valid": pair_valid,
            "full_execution": full_execution,
            "lite_execution": lite_execution,
            "raw_pair": dict(pair),
        }
        self._state["attempts"].append(
            {
                "question_id": question_id,
                "attempt": attempt,
                "recorded_at": record["recorded_at"],
                "pair_valid": pair_valid,
            }
        )
        _append_jsonl(self.raw_path, record)
        if not pair_valid:
            self._state["status"] = "invalid"
            self._state["last_invalid_question_id"] = question_id
            _write_json(self.manifest_path, self._state)
            raise Phase29ProtocolError("invalid Full/Lite pair recorded; run is not scoreable")

        assignment = self.plan["mapping"][question_id]
        _append_jsonl(
            self.blind_path,
            {
                "question_id": question_id,
                "attempt": attempt,
                "pair_valid": True,
                "answers": [
                    _blind_answer(full, assignment["full_label"], full_execution),
                    _blind_answer(lite, assignment["lite_label"], lite_execution),
                ],
            },
        )
        self._state["completed_question_ids"].append(question_id)
        self._state["status"] = (
            "complete" if set(self.completed_question_ids) == set(self.question_ids) else "partial"
        )
        _write_json(self.manifest_path, self._state)
        return self._state


__all__ = [
    "DEFAULT_BLIND_SEED",
    "PROTOCOL_VERSION",
    "Phase29ProtocolError",
    "ResumablePairRecorder",
    "create_blind_plan",
    "snapshot_manifest",
    "utc_now",
]
