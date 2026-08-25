"""Correctable Story organization with append-only decision history."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import storage
from .automatic_story_resolution import AUTOMATIC_STORY_RESOLVER_VERSION
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, precise_utc_now, utc_now
from .story_context import reconcile_story_entity_projection_tx
from .worker import RetryableJobFailure


STORY_CORRECTION_RECONCILIATION_JOB_TYPE = "story_correction_reconcile"
CAUSE_CLASSES = {"new_evidence", "reprocessing", "human_correction", "administrative"}
ORIGINS = {"human", "automatic", "import", "repair"}


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is not None


class StoryCorrectionService:
    """Own current Story membership, correction identity, and Story lineage."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @staticmethod
    def _require_story(conn: sqlite3.Connection, story_id: str, *, active: bool = False) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM stories WHERE id = ? AND deleted_at IS NULL", (story_id,)).fetchone()
        if row is None:
            raise DomainNotFound("story not found")
        if active and row["lifecycle"] == "archived":
            raise DomainConflict("story is not an active correction target")
        return row

    @staticmethod
    def _create_correction_tx(
        conn: sqlite3.Connection,
        operation_type: str,
        *,
        actor: str | None,
        reason: str,
        reason_code: str,
        cause_class: str = "human_correction",
        caused_by_type: str | None = None,
        caused_by_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        correction_id: str | None = None,
        occurred_at: str | None = None,
    ) -> str:
        if operation_type not in {"reassign", "unassign", "merge", "split", "extract", "duplicate_dismissal"}:
            raise DomainValidation("unsupported Story correction operation")
        if cause_class not in CAUSE_CLASSES:
            raise DomainValidation("unsupported Story correction cause class")
        identifier = correction_id or new_id("sc")
        conn.execute(
            """
            INSERT INTO story_corrections
                (id, operation_type, origin, actor, reason_code, reason,
                 cause_class, caused_by_type, caused_by_id, occurred_at, metadata_json)
            VALUES (?, ?, 'human', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (identifier, operation_type, actor, reason_code, reason[:4000], cause_class,
             caused_by_type, caused_by_id, occurred_at or precise_utc_now(), _json(metadata or {})),
        )
        return identifier

    @staticmethod
    def _enqueue_reconciliation_tx(conn: sqlite3.Connection, correction_id: str, affected_story_ids: Iterable[str]) -> str:
        key = f"story_correction_reconcile:{correction_id}"
        existing = conn.execute("SELECT id FROM jobs WHERE idempotency_key = ?", (key,)).fetchone()
        if existing is not None:
            return existing[0]
        identifier = new_id("job")
        now = utc_now()
        conn.execute(
            """
            INSERT INTO jobs
                (id, job_type, status, payload_json, idempotency_key, priority,
                 max_attempts, created_at, updated_at)
            VALUES (?, ?, 'queued', ?, ?, 20, 5, ?, ?)
            """,
            (identifier, STORY_CORRECTION_RECONCILIATION_JOB_TYPE,
             _json({"correction_id": correction_id, "story_ids": sorted(set(affected_story_ids))}),
             key, now, now),
        )
        return identifier

    @staticmethod
    def _transition_claim_tx(
        conn: sqlite3.Connection,
        claim_id: str,
        story_id: str | None,
        *,
        correction_id: str | None,
        origin: str,
        reason_code: str,
        reason: str,
        expected_from_story_id: str | None = None,
        require_expected: bool = False,
        occurred_at: str | None = None,
    ) -> tuple[str | None, str | None]:
        if origin not in ORIGINS:
            raise DomainValidation("unsupported Story membership origin")
        claim = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        if claim is None:
            raise DomainNotFound("claim not found")
        previous = claim["story_id"]
        if require_expected and previous != expected_from_story_id:
            raise DomainConflict("Claim current Story changed since preview")
        if previous == story_id:
            return previous, story_id
        if story_id is not None:
            StoryCorrectionService._require_story(conn, story_id, active=True)
        authorization = new_id("sta")
        conn.execute(
            "INSERT INTO story_transition_authorizations(id, claim_id) VALUES (?, ?)",
            (authorization, claim_id),
        )
        try:
            conn.execute("UPDATE claims SET story_id = ? WHERE id = ?", (story_id, claim_id))
        finally:
            conn.execute("DELETE FROM story_transition_authorizations WHERE id = ?", (authorization,))
        occurred = occurred_at or precise_utc_now()
        conn.execute(
            """
            INSERT INTO claim_story_assignment_history
                (id, claim_id, from_story_id, to_story_id, correction_id, origin,
                 reason_code, reason, occurred_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id("csa"), claim_id, previous, story_id, correction_id, origin,
             reason_code, reason[:4000], occurred, occurred),
        )
        return previous, story_id

    def reassign_claim(
        self,
        claim_id: str,
        story_id: str,
        *,
        actor: str | None = None,
        reason: str = "",
        expected_from_story_id: str | None = None,
        correction_id: str | None = None,
        cause_class: str = "human_correction",
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        if not str(story_id).strip():
            raise DomainValidation("story_id is required")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                claim = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
                if claim is None:
                    raise DomainNotFound("claim not found")
                if claim["story_id"] == story_id:
                    return {"claim": dict(claim), "correction_id": None, "job_id": None, "already_applied": True}
                correction = self._create_correction_tx(
                    conn, "reassign", actor=actor, reason=reason,
                    reason_code="reassign", cause_class=cause_class,
                    correction_id=correction_id,
                    occurred_at=occurred_at,
                )
                previous, _ = self._transition_claim_tx(
                    conn, claim_id, story_id, correction_id=correction,
                    origin="human", reason_code="reassign", reason=reason,
                    expected_from_story_id=expected_from_story_id,
                    require_expected=expected_from_story_id is not None,
                    occurred_at=occurred_at,
                )
                job_id = self._enqueue_reconciliation_tx(conn, correction, [previous, story_id])
                result = dict(conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone())
                return {"claim": result, "correction_id": correction, "job_id": job_id}
        finally:
            conn.close()

    def unassign_claim(
        self,
        claim_id: str,
        *,
        actor: str | None = None,
        reason: str = "",
        expected_from_story_id: str | None = None,
        correction_id: str | None = None,
    ) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                claim = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
                if claim is None:
                    raise DomainNotFound("claim not found")
                if claim["story_id"] is None:
                    latest = conn.execute(
                        "SELECT origin, to_story_id FROM claim_story_assignment_history WHERE claim_id = ? ORDER BY occurred_at DESC, id DESC LIMIT 1",
                        (claim_id,),
                    ).fetchone()
                    return {"claim": dict(claim), "correction_id": None, "job_id": None,
                            "already_applied": bool(latest and latest["origin"] == "human" and latest["to_story_id"] is None)}
                correction = self._create_correction_tx(
                    conn, "unassign", actor=actor, reason=reason,
                    reason_code="unassign", correction_id=correction_id,
                )
                previous, _ = self._transition_claim_tx(
                    conn, claim_id, None, correction_id=correction,
                    origin="human", reason_code="unassign", reason=reason,
                    expected_from_story_id=expected_from_story_id,
                    require_expected=expected_from_story_id is not None,
                )
                job_id = self._enqueue_reconciliation_tx(conn, correction, [previous] if previous else [])
                return {"claim": dict(conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()),
                        "correction_id": correction, "job_id": job_id}
        finally:
            conn.close()

    def automatic_initial_assignment(self, claim_id: str, story_id: str) -> dict[str, Any]:
        """Compatibility helper for deterministic initial assignment tests."""
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                claim = conn.execute("SELECT story_id FROM claims WHERE id = ?", (claim_id,)).fetchone()
                if claim is None:
                    raise DomainNotFound("claim not found")
                if claim["story_id"] == story_id:
                    return dict(conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone())
                if claim["story_id"] is not None:
                    raise DomainConflict("Claim Story association cannot be reassigned")
                latest = conn.execute(
                    "SELECT origin, to_story_id FROM claim_story_assignment_history WHERE claim_id = ? ORDER BY occurred_at DESC, id DESC LIMIT 1",
                    (claim_id,),
                ).fetchone()
                if latest and latest["origin"] == "human" and latest["to_story_id"] is None:
                    raise DomainConflict("human unassignment is authoritative")
                previous, _ = self._transition_claim_tx(
                    conn, claim_id, story_id, correction_id=None, origin="automatic",
                    reason_code=AUTOMATIC_STORY_RESOLVER_VERSION,
                    reason=f"automatic Story assignment via {AUTOMATIC_STORY_RESOLVER_VERSION}",
                )
                return dict(conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone())
        finally:
            conn.close()

    def set_manual_entity(self, story_id: str, entity_id: str, *, origin: str = "user") -> dict[str, Any]:
        if origin not in {"user", "import"}:
            raise DomainValidation("manual Story Entity origin must be user or import")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_story(conn, story_id)
                if conn.execute("SELECT 1 FROM entities WHERE id = ?", (entity_id,)).fetchone() is None:
                    raise DomainNotFound("entity not found")
                conn.execute(
                    "INSERT OR IGNORE INTO story_entities(story_id, entity_id, origin, authority, created_at) VALUES (?, ?, ?, 'manual', ?)",
                    (story_id, entity_id, origin, utc_now()),
                )
                return {"story_id": story_id, "entity_id": entity_id, "origin": origin, "authority": "manual"}
        finally:
            conn.close()

    def remove_manual_entity(self, story_id: str, entity_id: str) -> None:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_story(conn, story_id)
                conn.execute("DELETE FROM story_entities WHERE story_id = ? AND entity_id = ? AND authority = 'manual'", (story_id, entity_id))
        finally:
            conn.close()

    def story_entities(self, story_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            self._require_story(conn, story_id)
            manual = [dict(row) for row in conn.execute(
                "SELECT * FROM story_entities WHERE story_id = ? AND authority = 'manual' ORDER BY entity_id",
                (story_id,),
            )]
            derived = [dict(row) for row in conn.execute(
                "SELECT * FROM story_entities WHERE story_id = ? AND authority = 'derived' ORDER BY entity_id",
                (story_id,),
            )]
            effective = sorted({row["entity_id"] for row in manual + derived})
            return {"story_id": story_id, "effective_entity_ids": effective, "manual": manual, "derived": derived}
        finally:
            conn.close()

    def extract_claims(
        self,
        source_story_id: str,
        claim_ids: Iterable[str],
        story_data: Mapping[str, Any],
        *,
        actor: str | None = None,
        reason: str = "",
    ) -> dict[str, Any]:
        selected = list(dict.fromkeys(str(item) for item in claim_ids))
        if not selected:
            raise DomainValidation("at least one Claim is required for extraction")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_story(conn, source_story_id, active=True)
                new_story = self._create_story_tx(conn, story_data)
                correction = self._create_correction_tx(conn, "extract", actor=actor, reason=reason, reason_code="extract")
                for claim_id in selected:
                    self._transition_claim_tx(
                        conn, claim_id, new_story, correction_id=correction,
                        origin="human", reason_code="extract", reason=reason,
                        expected_from_story_id=source_story_id, require_expected=True,
                    )
                job_id = self._enqueue_reconciliation_tx(conn, correction, [source_story_id, new_story])
                return {"story": dict(conn.execute("SELECT * FROM stories WHERE id = ?", (source_story_id,)).fetchone()),
                        "new_story": dict(conn.execute("SELECT * FROM stories WHERE id = ?", (new_story,)).fetchone()),
                        "moved_claim_ids": selected, "correction_id": correction, "job_id": job_id}
        finally:
            conn.close()

    def preview_merge(
        self,
        source_story_id: str,
        destination_story_id: str,
        metadata_decisions: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            source = self._require_story(conn, source_story_id)
            destination = self._require_story(conn, destination_story_id, active=True)
            if source_story_id == destination_story_id:
                raise DomainConflict("cannot merge a Story into itself")
            fingerprint = self._current_state_fingerprint(
                conn, source_story_id, destination_story_id, metadata_decisions or {}
            )
            return {
                "source": dict(source), "destination": dict(destination),
                "source_claim_count": conn.execute("SELECT COUNT(*) FROM claims WHERE story_id = ?", (source_story_id,)).fetchone()[0],
                "destination_claim_count": conn.execute("SELECT COUNT(*) FROM claims WHERE story_id = ?", (destination_story_id,)).fetchone()[0],
                "source_documents": self._current_document_ids(conn, source_story_id),
                "destination_documents": self._current_document_ids(conn, destination_story_id),
                "source_entity_ids": self._current_entity_ids(conn, source_story_id),
                "destination_entity_ids": self._current_entity_ids(conn, destination_story_id),
                "watch_consequences": self._watch_preview(conn, source_story_id, destination_story_id),
                "expected_claim_moves": [row[0] for row in conn.execute("SELECT id FROM claims WHERE story_id = ? ORDER BY created_at, id", (source_story_id,))],
                "expected_current_state_fingerprint": fingerprint,
            }
        finally:
            conn.close()

    def merge_stories(
        self,
        source_story_id: str,
        destination_story_id: str,
        *,
        actor: str | None = None,
        reason: str = "",
        expected_source_updated_at: str | None = None,
        expected_current_state_fingerprint: str | None = None,
        metadata_decisions: Mapping[str, Any] | None = None,
        duplicate_evidence_hash: str | None = None,
    ) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if source_story_id == destination_story_id:
                    raise DomainConflict("cannot merge a Story into itself")
                source = self._require_story(conn, source_story_id)
                destination = self._require_story(conn, destination_story_id, active=True)
                existing = conn.execute(
                    "SELECT * FROM story_lineage WHERE source_story_id = ? AND relationship = 'merged_into'",
                    (source_story_id,),
                ).fetchone()
                if existing is not None:
                    if existing["target_story_id"] == destination_story_id:
                        if duplicate_evidence_hash:
                            low, high = sorted((source_story_id, destination_story_id))
                            conn.execute(
                                "INSERT OR IGNORE INTO story_duplicate_decisions(id, source_story_id, destination_story_id, evidence_hash, decision, correction_id, reason, created_at) VALUES (?, ?, ?, ?, 'approved', ?, ?, ?)",
                                (new_id("sdd"), low, high, duplicate_evidence_hash, existing["correction_id"], reason[:4000], utc_now()),
                            )
                        return {"source": dict(source), "destination": dict(destination), "correction_id": existing["correction_id"], "already_applied": True}
                    raise DomainConflict("Story already has a merge destination")
                if source["lifecycle"] == "archived":
                    raise DomainConflict("historical Story cannot be merged again")
                if expected_source_updated_at is not None and source["updated_at"] != expected_source_updated_at:
                    raise DomainConflict("merge preview is stale")
                if expected_current_state_fingerprint is not None:
                    actual_fingerprint = self._current_state_fingerprint(
                        conn,
                        source_story_id,
                        destination_story_id,
                        metadata_decisions or {},
                    )
                    if actual_fingerprint != expected_current_state_fingerprint:
                        raise DomainConflict("merge preview is stale")
                if self._would_merge_cycle(conn, source_story_id, destination_story_id):
                    raise DomainConflict("Story merge would create a lineage cycle")
                correction = self._create_correction_tx(
                    conn, "merge", actor=actor, reason=reason, reason_code="merge",
                    metadata=metadata_decisions,
                )
                conn.execute(
                    "INSERT INTO story_lineage(id, source_story_id, target_story_id, relationship, correction_id, created_at) VALUES (?, ?, ?, 'merged_into', ?, ?)",
                    (new_id("sl"), source_story_id, destination_story_id, correction, utc_now()),
                )
                if duplicate_evidence_hash:
                    low, high = sorted((source_story_id, destination_story_id))
                    conn.execute(
                        "INSERT INTO story_duplicate_decisions(id, source_story_id, destination_story_id, evidence_hash, decision, correction_id, reason, created_at) VALUES (?, ?, ?, ?, 'approved', ?, ?, ?)",
                        (new_id("sdd"), low, high, duplicate_evidence_hash, correction, reason[:4000], utc_now()),
                    )
                moved = []
                for row in conn.execute("SELECT id FROM claims WHERE story_id = ? ORDER BY created_at, id", (source_story_id,)).fetchall():
                    self._transition_claim_tx(
                        conn, row[0], destination_story_id, correction_id=correction,
                        origin="human", reason_code="merge", reason=reason,
                        expected_from_story_id=source_story_id, require_expected=True,
                    )
                    moved.append(row[0])
                conn.execute("UPDATE stories SET lifecycle = 'archived', updated_at = ? WHERE id = ?", (utc_now(), source_story_id))
                self._merge_metadata_tx(conn, source_story_id, destination_story_id, metadata_decisions or {})
                self._retarget_watch_tx(conn, source_story_id, destination_story_id)
                job_id = self._enqueue_reconciliation_tx(conn, correction, [source_story_id, destination_story_id])
                return {"source": dict(conn.execute("SELECT * FROM stories WHERE id = ?", (source_story_id,)).fetchone()),
                        "destination": dict(conn.execute("SELECT * FROM stories WHERE id = ?", (destination_story_id,)).fetchone()),
                        "moved_claim_ids": moved, "correction_id": correction, "job_id": job_id}
        finally:
            conn.close()

    def split_story(
        self,
        source_story_id: str,
        groups: Iterable[Iterable[str]],
        *,
        actor: str | None = None,
        reason: str = "",
        child_metadata: Iterable[Mapping[str, Any]] | None = None,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        normalized_groups = [list(dict.fromkeys(str(item) for item in group)) for group in groups]
        if len(normalized_groups) < 2 or any(not group for group in normalized_groups):
            raise DomainValidation("a split requires at least two non-empty Claim groups")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                source = self._require_story(conn, source_story_id, active=True)
                current = {row[0] for row in conn.execute("SELECT id FROM claims WHERE story_id = ?", (source_story_id,))}
                selected = [item for group in normalized_groups for item in group]
                if len(selected) != len(set(selected)) or set(selected) != current:
                    raise DomainConflict("split groups must cover each current Claim exactly once")
                correction = self._create_correction_tx(
                    conn, "split", actor=actor, reason=reason, reason_code="split", occurred_at=occurred_at
                )
                metadata = list(child_metadata or [])
                children: list[str] = []
                for index, group in enumerate(normalized_groups):
                    child = self._create_story_tx(conn, metadata[index] if index < len(metadata) else {"headline": f"{source_story_id} — part {index + 1}"})
                    children.append(child)
                    conn.execute(
                        "INSERT INTO story_lineage(id, source_story_id, target_story_id, relationship, correction_id, created_at) VALUES (?, ?, ?, 'split_into', ?, ?)",
                        (new_id("sl"), source_story_id, child, correction, occurred_at or precise_utc_now()),
                    )
                    for claim_id in group:
                        self._transition_claim_tx(
                            conn, claim_id, child, correction_id=correction,
                            origin="human", reason_code="split", reason=reason,
                            expected_from_story_id=source_story_id, require_expected=True,
                            occurred_at=occurred_at,
                        )
                conn.execute("UPDATE stories SET lifecycle = 'archived', updated_at = ? WHERE id = ?", (utc_now(), source_story_id))
                self._mark_split_watch_review_tx(conn, source_story_id, children)
                job_id = self._enqueue_reconciliation_tx(conn, correction, [source_story_id, *children])
                return {"source": dict(conn.execute("SELECT * FROM stories WHERE id = ?", (source_story_id,)).fetchone()),
                        "children": [dict(conn.execute("SELECT * FROM stories WHERE id = ?", (child,)).fetchone()) for child in children],
                        "groups": normalized_groups, "correction_id": correction, "job_id": job_id}
        finally:
            conn.close()

    def preview_split(self, source_story_id: str) -> dict[str, Any]:
        """Return the bounded current-state payload needed to approve a split."""
        conn = storage.connect(self.db_path)
        try:
            source = self._require_story(conn, source_story_id, active=True)
            claims = [dict(row) for row in conn.execute(
                "SELECT id, proposition, importance, state FROM claims WHERE story_id = ? ORDER BY created_at, id",
                (source_story_id,),
            )]
            return {
                "source": dict(source),
                "claims": claims,
                "current_document_ids": self._current_document_ids(conn, source_story_id),
                "current_entity_ids": self._current_entity_ids(conn, source_story_id),
                "watch_consequences": [
                    dict(row) for row in conn.execute(
                        "SELECT id, 'watch' AS kind, name FROM watches WHERE target_type = 'story' AND target_id = ? "
                        "UNION ALL SELECT id, 'monitor' AS kind, id AS name FROM monitors WHERE target_type = 'story' AND target_id = ?",
                        (source_story_id, source_story_id),
                    )
                ],
                "expected_claim_ids": [item["id"] for item in claims],
            }
        finally:
            conn.close()

    def resolve_story(self, story_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            self._require_story(conn, story_id)
            resolved, path = self._resolve_story_ids_tx(conn, story_id, [], set())
            if resolved == [story_id]:
                resolution = "active"
                canonical = story_id
            elif len(resolved) == 1:
                resolution = "merged"
                canonical = resolved[0]
            else:
                resolution = "split"
                canonical = None
            return {
                "story_id": story_id,
                "resolution": resolution,
                "canonical_story_id": canonical,
                "resulting_story_ids": resolved,
                "lineage_path": path,
            }
        finally:
            conn.close()

    def dismiss_duplicate(self, source_story_id: str, destination_story_id: str, *, evidence_hash: str = "current", actor: str | None = None, reason: str = "") -> dict[str, Any]:
        low, high = sorted((source_story_id, destination_story_id))
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_story(conn, source_story_id)
                self._require_story(conn, destination_story_id)
                existing = conn.execute("SELECT * FROM story_duplicate_decisions WHERE source_story_id = ? AND destination_story_id = ? AND evidence_hash = ?", (low, high, evidence_hash)).fetchone()
                if existing is not None:
                    return dict(existing)
                correction = self._create_correction_tx(conn, "duplicate_dismissal", actor=actor, reason=reason, reason_code="duplicate_dismissal")
                identifier = new_id("sdd")
                conn.execute("INSERT INTO story_duplicate_decisions(id, source_story_id, destination_story_id, evidence_hash, decision, correction_id, reason, created_at) VALUES (?, ?, ?, ?, 'dismissed', ?, ?, ?)", (identifier, low, high, evidence_hash, correction, reason[:4000], utc_now()))
                return dict(conn.execute("SELECT * FROM story_duplicate_decisions WHERE id = ?", (identifier,)).fetchone())
        finally:
            conn.close()

    def approve_duplicate(
        self,
        source_story_id: str,
        destination_story_id: str,
        *,
        evidence_hash: str = "current",
        actor: str | None = None,
        reason: str = "",
        expected_source_updated_at: str | None = None,
        metadata_decisions: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Approve a duplicate suggestion through the canonical merge path."""
        result = self.merge_stories(
            source_story_id,
            destination_story_id,
            actor=actor,
            reason=reason or f"Approved duplicate suggestion {evidence_hash}",
            expected_source_updated_at=expected_source_updated_at,
            metadata_decisions=metadata_decisions,
            duplicate_evidence_hash=evidence_hash,
        )
        result["duplicate_evidence_hash"] = evidence_hash
        return result

    def correction_history(self, story_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1 or limit > 500:
            raise DomainValidation("limit must be between 1 and 500")
        conn = storage.connect(self.db_path)
        try:
            self._require_story(conn, story_id)
            correction_ids = {
                row[0] for row in conn.execute(
                    "SELECT correction_id FROM claim_story_assignment_history WHERE (from_story_id = ? OR to_story_id = ?) AND correction_id IS NOT NULL",
                    (story_id, story_id),
                )
            }
            correction_ids.update(
                row[0] for row in conn.execute(
                    "SELECT correction_id FROM story_lineage WHERE (source_story_id = ? OR target_story_id = ?) AND correction_id IS NOT NULL",
                    (story_id, story_id),
                )
            )
            correction_ids.update(
                row[0] for row in conn.execute(
                    "SELECT correction_id FROM story_duplicate_decisions WHERE (source_story_id = ? OR destination_story_id = ?) AND correction_id IS NOT NULL",
                    (story_id, story_id),
                )
            )
            if not correction_ids:
                return []
            placeholders = ",".join("?" for _ in correction_ids)
            rows = [dict(row) for row in conn.execute(
                f"SELECT * FROM story_corrections WHERE id IN ({placeholders}) ORDER BY occurred_at DESC, id DESC LIMIT ?",
                (*sorted(correction_ids), limit),
            )]
            for item in rows:
                item["transitions"] = [dict(row) for row in conn.execute(
                    "SELECT * FROM claim_story_assignment_history WHERE correction_id = ? ORDER BY occurred_at, id",
                    (item["id"],),
                )]
                item["lineage"] = [dict(row) for row in conn.execute(
                    "SELECT * FROM story_lineage WHERE correction_id = ? ORDER BY created_at, id",
                    (item["id"],),
                )]
            return rows
        finally:
            conn.close()

    def lineage(self, story_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            self._require_story(conn, story_id)
            return {
                "story_id": story_id,
                "resolution": self.resolve_story(story_id),
                "incoming": [dict(row) for row in conn.execute(
                    "SELECT * FROM story_lineage WHERE target_story_id = ? ORDER BY created_at, id", (story_id,)
                )],
                "outgoing": [dict(row) for row in conn.execute(
                    "SELECT * FROM story_lineage WHERE source_story_id = ? ORDER BY created_at, id", (story_id,)
                )],
            }
        finally:
            conn.close()

    def suggest_duplicates(self, story_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        if limit < 1 or limit > 100:
            raise DomainValidation("limit must be between 1 and 100")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_story(conn, story_id, active=True)
                source_claims = [self._tokens(row[0]) for row in conn.execute("SELECT proposition FROM claims WHERE story_id = ?", (story_id,))]
                output = []
                source_tokens = sorted({token for tokens in source_claims for token in tokens})
                if not source_tokens:
                    return []
                clauses = " OR ".join("LOWER(c.proposition) LIKE '%' || ? || '%'" for _ in source_tokens)
                candidate_rows = conn.execute(
                    f"""
                    SELECT DISTINCT s.id
                    FROM stories s JOIN claims c ON c.story_id = s.id
                    WHERE s.id <> ? AND s.deleted_at IS NULL AND s.lifecycle <> 'archived'
                      AND ({clauses})
                    ORDER BY s.updated_at DESC, s.id
                    LIMIT ?
                    """,
                    (story_id, *source_tokens, max(50, min(500, limit * 10))),
                ).fetchall()
                for row in candidate_rows:
                    candidate_claims = [self._tokens(item[0]) for item in conn.execute("SELECT proposition FROM claims WHERE story_id = ?", (row[0],))]
                    score = max((len(left & right) / max(1, len(left | right)) for left in source_claims for right in candidate_claims), default=0.0)
                    if score < 0.6:
                        continue
                    source, destination = sorted((story_id, row[0]))
                    score = round(score, 6)
                    evidence_hash = hashlib.sha256(
                        _json({
                            "source": source,
                            "destination": destination,
                            "score": score,
                            "claims": {
                                source: sorted(" ".join(sorted(tokens)) for tokens in source_claims),
                                destination: sorted(" ".join(sorted(tokens)) for tokens in candidate_claims),
                            },
                        }).encode()
                    ).hexdigest()
                    dismissed = conn.execute("SELECT 1 FROM story_duplicate_decisions WHERE source_story_id = ? AND destination_story_id = ? AND evidence_hash = ? AND decision = 'dismissed'", (source, destination, evidence_hash)).fetchone()
                    if dismissed:
                        continue
                    conn.execute(
                        "INSERT OR IGNORE INTO story_duplicate_suggestions(id, source_story_id, destination_story_id, evidence_hash, score, explanation_json, resolver_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (new_id("sds"), source, destination, evidence_hash, score, _json({"method": "proposition_token_jaccard", "source_claim_count": len(source_claims), "candidate_claim_count": len(candidate_claims)}), AUTOMATIC_STORY_RESOLVER_VERSION, utc_now()),
                    )
                    suggestion = conn.execute(
                        "SELECT id FROM story_duplicate_suggestions WHERE source_story_id = ? AND destination_story_id = ? AND evidence_hash = ?",
                        (source, destination, evidence_hash),
                    ).fetchone()
                    output.append({"id": suggestion[0], "source_story_id": source, "destination_story_id": destination, "score": score, "evidence_hash": evidence_hash})
                return output[:limit]
        finally:
            conn.close()

    def metrics(self) -> dict[str, Any]:
        """Return bounded, durable Story-correction quality measures.

        The inputs come from append-only membership history, correction
        aggregates, and duplicate decisions.  Suggestion identity is the
        evidence hash returned by ``suggest_duplicates`` and persisted with
        any later approval or dismissal, so changed evidence can be counted
        separately without creating a second metrics subsystem.
        """
        conn = storage.connect(self.db_path)
        try:
            automatic_assignments = conn.execute(
                "SELECT COUNT(*) FROM claim_story_assignment_history WHERE origin = 'automatic'"
            ).fetchone()[0]
            operation_counts = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT operation_type, COUNT(*) FROM story_corrections GROUP BY operation_type"
                )
            }
            origin_counts = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT origin, COUNT(*) FROM claim_story_assignment_history GROUP BY origin"
                )
            }
            suggestion_count = conn.execute(
                "SELECT COUNT(*) FROM story_duplicate_suggestions"
            ).fetchone()[0]
            approval_count = conn.execute(
                "SELECT COUNT(*) FROM story_duplicate_decisions WHERE decision = 'approved'"
            ).fetchone()[0]
            dismissal_count = conn.execute(
                "SELECT COUNT(*) FROM story_duplicate_decisions WHERE decision = 'dismissed'"
            ).fetchone()[0]
            avg_seconds = conn.execute(
                """
                SELECT AVG((julianday(h.occurred_at) - julianday(a.occurred_at)) * 86400.0)
                FROM claim_story_assignment_history h
                JOIN claim_story_assignment_history a
                  ON a.claim_id = h.claim_id
                 AND a.origin = 'automatic'
                 AND a.occurred_at <= h.occurred_at
                WHERE h.origin = 'human'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM claim_story_assignment_history newer
                      WHERE newer.claim_id = a.claim_id
                        AND newer.origin = 'automatic'
                        AND newer.occurred_at > a.occurred_at
                        AND newer.occurred_at <= h.occurred_at
                  )
                """
            ).fetchone()[0]
            manual_corrections = sum(
                int(operation_counts.get(operation, 0))
                for operation in ("reassign", "unassign", "merge", "split", "extract")
            )
            return {
                "automatic_assignment_count": int(automatic_assignments),
                "manual_reassignment_count": int(operation_counts.get("reassign", 0)),
                "manual_unassignment_count": int(operation_counts.get("unassign", 0)),
                "merge_suggestion_count": int(suggestion_count),
                "merge_approval_count": int(approval_count),
                "merge_dismissal_count": int(dismissal_count),
                "split_count": int(operation_counts.get("split", 0)),
                "extract_count": int(operation_counts.get("extract", 0)),
                "time_to_correction_seconds": round(float(avg_seconds), 3) if avg_seconds is not None else None,
                "manual_corrections_per_100_automatic_assignments": round(
                    manual_corrections * 100.0 / automatic_assignments, 3
                ) if automatic_assignments else None,
                "origin_counts": origin_counts,
                "resolver_algorithm_version": AUTOMATIC_STORY_RESOLVER_VERSION,
            }
        finally:
            conn.close()

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return {item for item in value.casefold().split() if len(item) >= 3}

    @staticmethod
    def _current_document_ids(conn: sqlite3.Connection, story_id: str) -> list[str]:
        from .story_context import current_story_document_ids
        return list(current_story_document_ids(conn, story_id))

    @staticmethod
    def _current_entity_ids(conn: sqlite3.Connection, story_id: str) -> list[str]:
        from .story_context import effective_story_entity_ids
        return list(effective_story_entity_ids(conn, story_id))

    @staticmethod
    def _watch_state(conn: sqlite3.Connection, story_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT 'watch' AS kind, id, target_id, status AS operational_state,
                   resolution_state, resolution_options_json
            FROM watches WHERE target_type = 'story' AND target_id = ?
            UNION ALL
            SELECT 'monitor' AS kind, id, target_id, CAST(enabled AS TEXT),
                   resolution_state, resolution_options_json
            FROM monitors WHERE target_type = 'story' AND target_id = ?
            ORDER BY kind, id
            """,
            (story_id, story_id),
        ).fetchall()
        return [dict(row) for row in rows]

    @classmethod
    def _current_state_fingerprint(
        cls,
        conn: sqlite3.Connection,
        source_story_id: str,
        destination_story_id: str,
        metadata_decisions: Mapping[str, Any],
    ) -> str:
        def story_state(story_id: str) -> dict[str, Any]:
            latest_revision = conn.execute(
                "SELECT id, claim_set_hash FROM story_revisions WHERE story_id = ? ORDER BY revision_number DESC, id DESC LIMIT 1",
                (story_id,),
            ).fetchone()
            tags = [row[0] for row in conn.execute("SELECT tag_id FROM story_tags WHERE story_id = ? ORDER BY tag_id", (story_id,))]
            assignments = [row[0] for row in conn.execute(
                "SELECT tag_id FROM tag_assignments WHERE object_type = 'story' AND object_id = ? ORDER BY tag_id",
                (story_id,),
            )] if _table_exists(conn, "tag_assignments") else []
            return {
                "claim_ids": [row[0] for row in conn.execute("SELECT id FROM claims WHERE story_id = ? ORDER BY created_at, id", (story_id,))],
                "revision": dict(latest_revision) if latest_revision else None,
                "topics": [row[0] for row in conn.execute("SELECT topic_id FROM story_topics WHERE story_id = ? ORDER BY topic_id", (story_id,))],
                "subjects": [row[0] for row in conn.execute("SELECT subject_id FROM story_subjects WHERE story_id = ? ORDER BY subject_id", (story_id,))],
                "tags": sorted(set(tags) | set(assignments)),
                "manual_entities": [row[0] for row in conn.execute("SELECT entity_id FROM story_entities WHERE story_id = ? AND authority = 'manual' ORDER BY entity_id", (story_id,))],
                "watch_state": cls._watch_state(conn, story_id),
            }

        payload = {
            "source_story_id": source_story_id,
            "destination_story_id": destination_story_id,
            "source": story_state(source_story_id),
            "destination": story_state(destination_story_id),
            "metadata_decisions": dict(metadata_decisions),
        }
        return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()

    @staticmethod
    def _watch_preview(conn: sqlite3.Connection, source_story_id: str, destination_story_id: str) -> list[dict[str, Any]]:
        return [dict(row) for row in conn.execute("SELECT id, 'watch' AS kind, name FROM watches WHERE target_type = 'story' AND target_id IN (?, ?) UNION ALL SELECT id, 'monitor' AS kind, id AS name FROM monitors WHERE target_type = 'story' AND target_id IN (?, ?)", (source_story_id, destination_story_id, source_story_id, destination_story_id)).fetchall()]

    @staticmethod
    def _would_merge_cycle(conn: sqlite3.Connection, source: str, destination: str) -> bool:
        current = destination
        seen = set()
        while current not in seen:
            if current == source:
                return True
            seen.add(current)
            row = conn.execute("SELECT target_story_id FROM story_lineage WHERE source_story_id = ? AND relationship = 'merged_into' LIMIT 1", (current,)).fetchone()
            if row is None:
                return False
            current = row[0]
        return True

    @staticmethod
    def _create_story_tx(conn: sqlite3.Connection, data: Mapping[str, Any]) -> str:
        headline = str(data.get("headline") or "").strip()
        if not headline:
            raise DomainValidation("Story headline is required")
        identifier = new_id("st")
        now = utc_now()
        conn.execute("INSERT INTO stories(id, lifecycle, created_at, updated_at) VALUES (?, ?, ?, ?)", (identifier, data.get("lifecycle", "developing"), now, now))
        conn.execute("INSERT INTO story_revisions(id, story_id, revision_number, headline, headline_normalized, summary, why_it_matters, material_change, claim_set_hash, created_at) VALUES (?, ?, 1, ?, ?, ?, ?, 0, ?, ?)", (new_id("rev"), identifier, headline, " ".join(headline.split()).casefold(), str(data.get("summary") or ""), str(data.get("why_it_matters") or ""), data.get("claim_set_hash"), now))
        conn.execute("INSERT INTO story_review(story_id, updated_at) VALUES (?, ?)", (identifier, now))
        for topic_id in data.get("topic_ids") or []:
            conn.execute("INSERT INTO story_topics(story_id, topic_id) VALUES (?, ?)", (identifier, topic_id))
        for subject_id in data.get("subject_ids") or []:
            conn.execute("INSERT INTO story_subjects(story_id, subject_id) VALUES (?, ?)", (identifier, subject_id))
        return identifier

    @staticmethod
    def _merge_metadata_tx(conn: sqlite3.Connection, source: str, destination: str, decisions: Mapping[str, Any]) -> None:
        if decisions.get("copy_topics"):
            conn.execute("INSERT OR IGNORE INTO story_topics(story_id, topic_id, match_score) SELECT ?, topic_id, match_score FROM story_topics WHERE story_id = ?", (destination, source))
        if decisions.get("copy_subjects"):
            conn.execute("INSERT OR IGNORE INTO story_subjects(story_id, subject_id) SELECT ?, subject_id FROM story_subjects WHERE story_id = ?", (destination, source))
        if decisions.get("copy_tags"):
            StoryCorrectionService._copy_story_tags_tx(conn, source, destination)
        if decisions.get("copy_manual_entities"):
            conn.execute("INSERT OR IGNORE INTO story_entities(story_id, entity_id, origin, authority, created_at) SELECT ?, entity_id, origin, 'manual', created_at FROM story_entities WHERE story_id = ? AND authority = 'manual'", (destination, source))

    @staticmethod
    def _retarget_watch_tx(conn: sqlite3.Connection, source: str, destination: str) -> None:
        for table in ("watches", "monitors"):
            rows = conn.execute(f"SELECT id FROM {table} WHERE target_type = 'story' AND target_id = ?", (source,)).fetchall()
            for row in rows:
                if table == "monitors":
                    conflict = conn.execute(
                        """
                        SELECT id FROM monitors
                        WHERE target_type = 'story' AND target_id = ? AND id <> ?
                          AND COALESCE(need_type, '') = COALESCE((SELECT need_type FROM monitors WHERE id = ?), '')
                          AND COALESCE(need_id, '') = COALESCE((SELECT need_id FROM monitors WHERE id = ?), '')
                        """,
                        (destination, row[0], row[0], row[0]),
                    ).fetchone()
                else:
                    conflict = conn.execute(
                        "SELECT id FROM watches WHERE target_type = 'story' AND target_id = ? AND id <> ?",
                        (destination, row[0]),
                    ).fetchone()
                if conflict is not None:
                    if table == "monitors":
                        conn.execute("UPDATE monitors SET historical_target_id = COALESCE(historical_target_id, target_id), enabled = 0, resolution_state = 'merged_into_existing', resolution_options_json = ?, updated_at = ? WHERE id = ?", (_json([destination]), utc_now(), row[0]))
                    else:
                        conn.execute("UPDATE watches SET historical_target_id = COALESCE(historical_target_id, target_id), status = 'disabled', resolution_state = 'merged_into_existing', resolution_options_json = ?, updated_at = ? WHERE id = ?", (_json([destination]), utc_now(), row[0]))
                else:
                    conn.execute(f"UPDATE {table} SET target_id = ?, historical_target_id = ?, resolution_state = 'active', resolution_options_json = '[]', updated_at = ? WHERE id = ?", (destination, source, utc_now(), row[0]))
                    if table == "monitors":
                        from .monitoring import MonitorService, _scope_for_target
                        MonitorService._write_scope_history(
                            conn,
                            row[0],
                            _scope_for_target(conn, "story", destination),
                            change_type="manual",
                            changed_by=None,
                            created_at=utc_now(),
                        )

    @staticmethod
    def _copy_story_tags_tx(conn: sqlite3.Connection, source: str, destination: str) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO story_tags(story_id, tag_id, created_at) SELECT ?, tag_id, created_at FROM story_tags WHERE story_id = ?",
            (destination, source),
        )
        if not _table_exists(conn, "tag_assignments"):
            return
        rows = conn.execute(
            "SELECT tag_id, origin, confidence, reason, created_at FROM tag_assignments WHERE object_type = 'story' AND object_id = ? ORDER BY tag_id, id",
            (source,),
        ).fetchall()
        for row in rows:
            conn.execute(
                "INSERT OR IGNORE INTO tag_assignments(id, tag_id, object_type, object_id, origin, confidence, reason, created_at) VALUES (?, ?, 'story', ?, ?, ?, ?, ?)",
                (new_id("ta"), row["tag_id"], destination, row["origin"], row["confidence"], row["reason"], row["created_at"]),
            )

    @staticmethod
    def _resolve_story_ids_tx(
        conn: sqlite3.Connection,
        story_id: str,
        path: list[dict[str, Any]],
        seen: set[str],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        if story_id in seen:
            raise DomainConflict("Story lineage contains a cycle")
        next_seen = set(seen)
        next_seen.add(story_id)
        merged = conn.execute(
            "SELECT * FROM story_lineage WHERE source_story_id = ? AND relationship = 'merged_into' ORDER BY created_at DESC, id DESC LIMIT 1",
            (story_id,),
        ).fetchone()
        if merged is not None:
            return StoryCorrectionService._resolve_story_ids_tx(
                conn,
                merged["target_story_id"],
                [*path, {"edge": dict(merged), "from_story_id": story_id}],
                next_seen,
            )
        children = conn.execute(
            "SELECT * FROM story_lineage WHERE source_story_id = ? AND relationship = 'split_into' ORDER BY target_story_id, id",
            (story_id,),
        ).fetchall()
        if not children:
            return [story_id], [*path, {"story_id": story_id, "resolution": "active"}]
        resolved: list[str] = []
        resolved_path = [*path, {"story_id": story_id, "resolution": "split", "children": [row["target_story_id"] for row in children]}]
        for child in children:
            child_ids, child_path = StoryCorrectionService._resolve_story_ids_tx(
                conn,
                child["target_story_id"],
                [*resolved_path, {"edge": dict(child), "from_story_id": story_id}],
                next_seen,
            )
            for identifier in child_ids:
                if identifier not in resolved:
                    resolved.append(identifier)
            resolved_path = child_path
        return sorted(resolved), resolved_path

    @staticmethod
    def _mark_split_watch_review_tx(conn: sqlite3.Connection, source: str, children: list[str]) -> None:
        for table in ("watches", "monitors"):
            conn.execute(f"UPDATE {table} SET historical_target_id = COALESCE(historical_target_id, target_id), resolution_state = 'needs_review', resolution_options_json = ?, updated_at = ? WHERE target_type = 'story' AND target_id = ?", (_json(children), utc_now(), source))

    def resolve_split_target(
        self,
        target_kind: str,
        target_id: str,
        target_story_ids: Iterable[str] | None = None,
        *,
        disable: bool = False,
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Resolve one split Watch/Monitor without erasing the historical target."""
        if target_kind not in {"watch", "monitor"}:
            raise DomainValidation("target_kind must be watch or monitor")
        selected = list(dict.fromkeys(str(item).strip() for item in (target_story_ids or []) if str(item).strip()))
        if not disable and len(selected) != 1:
            raise DomainValidation("existing Story targeting supports exactly one split child")
        table = "watches" if target_kind == "watch" else "monitors"
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (target_id,)).fetchone()
                if row is None:
                    raise DomainNotFound(f"{target_kind} not found")
                options = json.loads(row["resolution_options_json"] or "[]")
                if not isinstance(options, list):
                    raise DomainConflict("split resolution options are malformed")
                historical = row["historical_target_id"] or row["target_id"]
                if disable:
                    if table == "watches":
                        conn.execute("UPDATE watches SET status = 'disabled', resolution_state = 'active', resolution_options_json = '[]', updated_at = ? WHERE id = ?", (utc_now(), target_id))
                    else:
                        conn.execute("UPDATE monitors SET enabled = 0, resolution_state = 'active', resolution_options_json = '[]', updated_at = ? WHERE id = ?", (utc_now(), target_id))
                    resolution = "disabled"
                else:
                    selected_story_id = selected[0]
                    if selected_story_id not in options:
                        raise DomainConflict("selected Story is not a current split child")
                    self._require_story(conn, selected_story_id, active=True)
                    if table == "watches":
                        conn.execute("UPDATE watches SET target_id = ?, status = 'active', resolution_state = 'active', resolution_options_json = '[]', updated_at = ? WHERE id = ?", (selected_story_id, utc_now(), target_id))
                    else:
                        conn.execute("UPDATE monitors SET target_id = ?, enabled = 1, resolution_state = 'active', resolution_options_json = '[]', updated_at = ? WHERE id = ?", (selected_story_id, utc_now(), target_id))
                        from .monitoring import MonitorService, _scope_for_target
                        MonitorService._write_scope_history(conn, target_id, _scope_for_target(conn, "story", selected_story_id), change_type="manual", changed_by=actor, created_at=utc_now())
                    resolution = "selected"
                conn.execute(
                    "INSERT INTO story_target_resolution_history(id, target_kind, target_id, historical_story_id, selected_story_ids_json, resolution, actor, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_id("str"), target_kind, target_id, historical, _json(selected), resolution, actor, utc_now()),
                )
                return dict(conn.execute(f"SELECT * FROM {table} WHERE id = ?", (target_id,)).fetchone())
        finally:
            conn.close()


class StoryCorrectionReconciliationService:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def handlers(self) -> dict[str, Any]:
        return {STORY_CORRECTION_RECONCILIATION_JOB_TYPE: self.handle}

    @staticmethod
    def _reconcile_story_revision_tx(conn: sqlite3.Connection, story_id: str) -> str | None:
        """Materialize one idempotent current Claim-set revision if it changed."""
        story = conn.execute("SELECT * FROM stories WHERE id = ? AND deleted_at IS NULL", (story_id,)).fetchone()
        if story is None:
            return None
        claim_ids = [row[0] for row in conn.execute("SELECT id FROM claims WHERE story_id = ? ORDER BY created_at, id", (story_id,))]
        claim_hash = hashlib.sha256(_json(claim_ids).encode("utf-8")).hexdigest()
        latest = conn.execute(
            "SELECT * FROM story_revisions WHERE story_id = ? ORDER BY revision_number DESC, id DESC LIMIT 1",
            (story_id,),
        ).fetchone()
        if latest is not None and latest["claim_set_hash"] == claim_hash:
            return None
        now = utc_now()
        revision_id = new_id("rev")
        revision_number = conn.execute(
            "SELECT COALESCE(MAX(revision_number), 0) + 1 FROM story_revisions WHERE story_id = ?",
            (story_id,),
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO story_revisions
                (id, story_id, revision_number, headline, headline_normalized,
                 summary, why_it_matters, material_change, claim_set_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                revision_id,
                story_id,
                revision_number,
                latest["headline"] if latest else story_id,
                latest["headline_normalized"] if latest else story_id.casefold(),
                latest["summary"] if latest else "",
                latest["why_it_matters"] if latest else "",
                claim_hash,
                now,
            ),
        )
        for position, claim_id in enumerate(claim_ids):
            conn.execute(
                "INSERT INTO story_revision_claims(revision_id, claim_id, position) VALUES (?, ?, ?)",
                (revision_id, claim_id, position),
            )
        from .story_context import current_story_document_ids
        for document_id in current_story_document_ids(conn, story_id):
            conn.execute(
                "INSERT OR IGNORE INTO story_revision_documents(revision_id, document_id, role, created_at) VALUES (?, ?, 'provenance', ?)",
                (revision_id, document_id, now),
            )
        conn.execute("UPDATE stories SET updated_at = ? WHERE id = ?", (now, story_id))
        return revision_id

    @staticmethod
    def _verify_transition_chain_tx(conn: sqlite3.Connection, claim_id: str) -> None:
        claim = conn.execute("SELECT story_id FROM claims WHERE id = ?", (claim_id,)).fetchone()
        if claim is None:
            raise DomainNotFound("claim not found while reconciling Story correction")
        sentinel = object()
        previous = sentinel
        for row in conn.execute(
            "SELECT from_story_id, to_story_id FROM claim_story_assignment_history WHERE claim_id = ? ORDER BY occurred_at, created_at, id",
            (claim_id,),
        ):
            if previous is not sentinel and row["from_story_id"] != previous:
                raise DomainConflict("Story correction transition chain is inconsistent")
            previous = row["to_story_id"]
        if previous is not sentinel and previous != claim["story_id"]:
            raise DomainConflict("Story correction pointer does not match transition history")

    def handle(self, job: Mapping[str, Any]) -> dict[str, Any]:
        payload = job.get("payload") or {}
        correction_id = str(payload.get("correction_id") or "").strip()
        if not correction_id:
            raise DomainValidation("correction reconciliation Job is missing correction_id")
        story_ids = [str(item) for item in payload.get("story_ids") or []]
        unique_story_ids = sorted(set(story_ids))
        affected_claim_ids: list[str] = []
        report_ids: list[str] = []
        result: dict[str, Any]
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                correction = conn.execute("SELECT * FROM story_corrections WHERE id = ?", (correction_id,)).fetchone()
                if correction is None:
                    raise DomainNotFound("Story correction not found")
                affected_claim_ids = [row[0] for row in conn.execute(
                    "SELECT DISTINCT claim_id FROM claim_story_assignment_history WHERE correction_id = ? ORDER BY claim_id",
                    (correction_id,),
                )]
                for claim_id in affected_claim_ids:
                    self._verify_transition_chain_tx(conn, claim_id)
                counts = {story_id: reconcile_story_entity_projection_tx(conn, story_id) for story_id in unique_story_ids}
                revisions = {
                    story_id: revision_id
                    for story_id in unique_story_ids
                    if (revision_id := self._reconcile_story_revision_tx(conn, story_id)) is not None
                }
                report_ids = [row[0] for row in conn.execute(
                    """
                    SELECT lr.id
                    FROM living_reports lr
                    JOIN stories s ON s.id = lr.target_id
                    WHERE lr.target_type = 'story'
                      AND lr.target_id IN ({})
                      AND s.lifecycle <> 'archived'
                    ORDER BY lr.id
                    """.format(",".join("?" for _ in unique_story_ids)),
                    unique_story_ids,
                )] if unique_story_ids and _table_exists(conn, "living_reports") else []
                result = {
                    "correction_id": correction_id,
                    "operation_type": correction["operation_type"],
                    "story_ids": unique_story_ids,
                    "derived_entity_counts": counts,
                    "story_revision_ids": revisions,
                    "report_targets_reconciled": len(report_ids),
                    "research_question_targets_reconciled": 0,
                    "reconciled": True,
                }
        finally:
            conn.close()

        # Downstream systems remain isolated from the committed correction
        # transaction, but failures are durable retry obligations. Successful
        # work is idempotent on replay; a correction Job may not report success
        # while a required report or Question target was skipped.
        report_results: list[dict[str, Any]] = []
        alert_results: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for report_id in report_ids:
            try:
                from .reports import LivingReportService
                generated = LivingReportService(self.db_path).generate(report_id)
                generation = generated.get("generation", {})
                report_results.append({"report_id": report_id, "status": generation.get("status", "completed")})
                revision_id = generation.get("revision_id")
                if revision_id:
                    from .reports import AlertService
                    emitted = AlertService(self.db_path).emit_for_report_revision(report_id, revision_id)
                    alert_results.append({"report_id": report_id, "created_count": emitted.get("created_count", 0), "alert_ids": emitted.get("alert_ids", [])})
            except Exception as exc:  # downstream failure must not invalidate the correction
                failures.append({"kind": "report", "id": report_id, "error": type(exc).__name__})
                report_results.append({"report_id": report_id, "status": "retryable", "error": type(exc).__name__})
        question_results: list[dict[str, Any]] = []
        for claim_id in affected_claim_ids:
            try:
                from .research_questions import ResearchQuestionService
                question_results.append(ResearchQuestionService(self.db_path).reevaluate_for_claim(claim_id))
            except Exception as exc:  # downstream failure is recoverable on the next normal evaluation
                failures.append({"kind": "research_question", "id": claim_id, "error": type(exc).__name__})
                question_results.append({"claim_id": claim_id, "status": "retryable", "error": type(exc).__name__})
        result["report_results"] = report_results
        result["alert_results"] = alert_results
        result["question_results"] = question_results
        result["research_question_targets_reconciled"] = sum(
            int(item.get("evaluated_count", 0)) for item in question_results
        )
        if failures:
            raise RetryableJobFailure(
                _json({"correction_id": correction_id, "downstream_failures": failures})
            )
        return result


__all__ = ["CAUSE_CLASSES", "STORY_CORRECTION_RECONCILIATION_JOB_TYPE", "StoryCorrectionReconciliationService", "StoryCorrectionService"]
