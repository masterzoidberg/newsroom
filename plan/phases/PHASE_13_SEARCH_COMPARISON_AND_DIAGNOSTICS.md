# Phase 13 — Search, Comparison, and Diagnostics

## Objective

Add the mature local research workbench and make information/operational gaps
visible.

## Required work

- Add bounded SQLite full-text search across Monitors, Sources, Documents,
  Stories, Subjects, Claims, Evidence, tags, Questions, and notes.
- Add typed filters, deterministic ranking/pagination, and semantic retrieval
  only if benchmarks demonstrate material value.
- Implement article comparison for shared/unique Claims, contradictions,
  dates/numbers, interpretations, primary-source use, and lineage.
- Add namespaced smart tags, user tags, notes, hypotheses, Subject pages and
  timelines, historical context, Monitor coverage diagnostics, and health.
- Clearly distinguish no meaningful change from failed acquisition/processing.

## Boundaries

No generic graph editor or unbounded semantic index. Comparison conclusions and
historical context must resolve to Newsroom evidence, not model memory.

## Verification and exit gate

- Search correctness, permissions, escaping, pagination, ranking stability,
  deletion/update indexing, and representative-scale tests.
- Comparison and context conclusions link to exact supporting/conflicting data.
- Coverage/health diagnostics derive from recorded state; full checks pass.

## Completion Record

Completed 2026-08-16.

- Added migrations 0011–0012 with namespaced user/smart tags, bounded generic
  notes, a SQLite FTS5 projection, and dirty-state triggers so updates and
  deletions rebuild the projection only when authoritative data changes.
- Added authenticated typed search with escaped terms, deterministic BM25
  ranking/pagination, entity/object filters, and update/deletion correctness.
- Added evidence-bound Document comparison for shared/unique Claims,
  contradictions, dates/numbers, interpretations, primary-source use, and
  Document lineage.
- Added bounded notes/hypotheses, Subject pages with timelines and historical
  Evidence context, Monitor coverage diagnostics, and health distinctions for
  no meaningful change vs acquisition/processing failure.
- Added the responsive Research Workbench UI with search, comparison,
  Subject-context, and Monitor-health surfaces.
- Verification: Phase 13 tests, full `pytest`, frontend typecheck/build, and
  `git diff --check` pass. Optional semantic retrieval remains disabled because
  no benchmark has demonstrated material value.
