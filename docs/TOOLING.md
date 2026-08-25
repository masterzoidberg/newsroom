# Development tooling baseline

The repository baseline is:

- `ruff check newsroom tests` with the scoped E4/E7/E9 rules in `pyproject.toml`;
- `pytest -q` for the backend suite;
- `npm run lint`, `npm run typecheck`, and `npm run build` in `frontend`;
- `mypy newsroom` recorded as informational until the existing annotation
  backlog is reduced. The Phase 28.875 run reports the existing informational
  baseline; this is not a Phase 28.875 acceptance gate.

CI runs Ruff, pytest, frontend lint/typecheck/build, and uploads the Mypy output
as an informational artifact. No new service or runtime dependency is added by
the tooling baseline; Pydantic is declared directly because application code
imports it directly.
