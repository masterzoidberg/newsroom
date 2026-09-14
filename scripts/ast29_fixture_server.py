from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"
WATCH_ID = "watch-1"


class FixtureHandler(SimpleHTTPRequestHandler):
    vocabulary = [
        {"id": "suggestion-1", "watch_id": WATCH_ID, "term": "unidentified flying object", "kind": "alias", "origin": "ai", "status": "suggested", "enabled": 0, "expansion_of": "UAP", "rationale": "Common alternate wording for the approved term."},
        {"id": "approved-1", "watch_id": WATCH_ID, "term": "official reports", "kind": "include", "origin": "user", "status": "approved", "enabled": 1, "expansion_of": None, "rationale": "Owner-selected monitoring language."},
        {"id": "rejected-1", "watch_id": WATCH_ID, "term": "fictional sightings", "kind": "exclude", "origin": "deterministic", "status": "rejected", "enabled": 0, "expansion_of": None, "rationale": "Not part of this Watch."},
    ]
    fail_suggestions = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def _json(self, body, status=200):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    @staticmethod
    def _watch():
        return {"id": WATCH_ID, "name": "UAP reporting", "target_type": "topic", "target_id": "topic-1", "policy_id": "policy-1", "status": "paused", "discovery_enabled": False}

    @classmethod
    def _health(cls):
        pending = sum(item["status"] == "suggested" for item in cls.vocabulary)
        return {"status": "paused", "discovery_enabled": False, "active_source_count": 0, "pending_source_candidate_count": 0, "pending_vocabulary_suggestion_count": pending, "review": {"interest": "UAP reporting", "approved_terms": ["UAP"], "excluded_terms": [], "sources": [], "cadence": {"base_cadence_seconds": 3600, "min_cadence_seconds": 900, "max_cadence_seconds": 86400}, "supported_channels": ["direct_http"], "paid_budget_usd": 0, "paid_mode": "zero-paid", "ready_to_start": False, "blockers": ["Approve at least one usable Source"]}, "progress": {"state": "paused", "label": "Paused", "detail": "Waiting for setup.", "last_attempt": None, "last_result": None, "last_error": None, "retryable": False, "results": []}}

    @staticmethod
    def _ai_status():
        local = {"provider_route": "local", "provider": "local", "model": "local", "reason": "default_local"}
        managed = {"provider_route": "connection", "provider": "openai_compatible", "model": "vocabulary-model", "connection_id": "connection-1", "reason": "configured_connection"}
        routes = [{"capability": "article_analysis", "provider_route": "local", "connection_id": None, "fallback_policy": "local", "revision": 0, "config_generation": 1, "generation": 1, "effective": local}, {"capability": "vocabulary", "provider_route": "connection", "connection_id": "connection-1", "fallback_policy": "local", "revision": 1, "config_generation": 1, "generation": 1, "effective": managed}]
        return {"generation": 1, "supported_capabilities": ["article_analysis", "vocabulary"], "items": [], "providers": [], "routes": routes, "effective_routes": {"article_analysis": local, "vocabulary": managed}, "paid_enabled": False, "budget_limits": []}

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/api/v1/auth/me": return self._json({"username": "admin"})
        if path == "/api/v1/runtime/status":
            component = {"status": "healthy", "detail": "Fixture component", "managed": True}
            return self._json({"managed": True, "overall": "idle", "supervisor": component, "components": {"api": component, "worker": component, "scheduler": component}, "work": {"state": "idle", "queued_jobs": 0, "running_jobs": 0}, "controls": {"available": False, "actions": []}, "request_id": "fixture-request"})
        if path == "/api/v1/watches" and query.get("page_size") == ["1"]: return self._json({"items": [{"id": WATCH_ID}], "total": 1, "page": 1, "page_size": 1})
        if path == "/api/v1/watches": return self._json({"items": [self._watch()], "total": 1, "page": 1, "page_size": 100})
        if path == f"/api/v1/watches/{WATCH_ID}": return self._json(self._watch())
        if path == f"/api/v1/watches/{WATCH_ID}/health": return self._json(self._health())
        if path == f"/api/v1/watches/{WATCH_ID}/vocabulary": return self._json({"items": self.vocabulary, "total": len(self.vocabulary), "page": 1, "page_size": 100})
        if path == f"/api/v1/watches/{WATCH_ID}/source-candidates": return self._json({"items": [], "total": 0, "page": 1, "page_size": 100})
        if path == f"/api/v1/watches/{WATCH_ID}/sources": return self._json({"items": [], "total": 0, "page": 1, "page_size": 100})
        if path == "/api/v1/topics/topic-1/vocabulary": return self._json({"items": [{"id": "primary-1", "term": "UAP", "term_type": "include", "concept_kind": "acronym"}], "total": 1, "page": 1, "page_size": 100})
        if path == "/api/v1/monitoring-policies": return self._json({"items": [{"id": "policy-1", "name": "Private hourly", "paid_budget_usd": 0, "base_cadence_seconds": 3600, "min_cadence_seconds": 900, "max_cadence_seconds": 86400, "allowed_channels": ["direct_http"]}], "total": 1, "page": 1, "page_size": 100})
        if path == "/api/v1/monitoring-policies/policy-1": return self._json({"id": "policy-1", "name": "Private hourly", "paid_budget_usd": 0, "base_cadence_seconds": 3600, "min_cadence_seconds": 900, "max_cadence_seconds": 86400, "allowed_channels": ["direct_http"]})
        if path == "/api/v1/ai/status": return self._json(self._ai_status())
        return super().do_GET()

    def do_POST(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if path == f"/api/v1/watches/{WATCH_ID}/vocabulary/suggest":
            if self.fail_suggestions: return self._json({"error": {"message": "Vocabulary provider is unavailable."}}, status=503)
            return self._json({"items": self.vocabulary}, status=201)
        if path == f"/api/v1/watches/{WATCH_ID}/vocabulary":
            item = {"id": f"manual-{len(self.vocabulary)}", "watch_id": WATCH_ID, "term": payload["term"], "kind": payload["kind"], "origin": "user", "status": "approved", "enabled": 1, "expansion_of": payload.get("expansion_of"), "rationale": payload.get("rationale")}
            self.vocabulary.append(item)
            return self._json(item, status=201)
        prefix = f"/api/v1/watches/{WATCH_ID}/vocabulary/"
        if path.startswith(prefix) and path.endswith("/review"):
            identifier = path[len(prefix):-len("/review")]
            for item in self.vocabulary:
                if item["id"] == identifier:
                    item["status"] = payload["status"]
                    item["enabled"] = 1 if payload["status"] == "approved" else 0
                    return self._json(item)
            return self._json({"error": {"message": "Vocabulary term not found."}}, status=404)
        return self._json({"items": []})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=4182)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), FixtureHandler)
    print(f"AST-29 fixture listening on http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
