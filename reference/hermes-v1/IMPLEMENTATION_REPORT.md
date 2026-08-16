# Implementation Report

## Product

Newsroom v1 implements the native Hermes architecture defined by the v1.1 product specification: profile-local SQLite, deterministic ingestion and deduplication, model-callable collection tools, a theme-aware Dashboard UI, and one Hermes Cron job.

## Runtime paths

- Source: `G:\Projects\hermes-newsroom`
- Development: `C:\Users\nicol\AppData\Local\hermes\profiles\newsroom-dev`
- Production: `C:\Users\nicol\AppData\Local\hermes\profiles\newsroom`

No Hermes core files are modified. Development and production code installs, databases, backups, sessions, and Cron records are isolated.

## Development Cron

- Job ID: `569e4603a089`
- Name: `Newsroom Collector`
- Schedule: `0 8,17 * * *`
- Timezone verification: next run `2026-08-15T08:00:00-04:00` (America/New_York)
- Skill: `newsroom:collect-news`
- Toolsets: `web`, `newsroom`
- Delivery: local
- Model/provider: `MiniMax-M2.7` / `minimax`

## Production Cron

- Job ID: `fc1690e1088a`
- Name: `Newsroom Collector`
- Schedule: `0 8,17 * * *`
- Verified next run: `2026-08-15T08:00:00-04:00`
- Skill/toolsets/delivery/model: identical to the accepted development contract

## Verification

Automated coverage includes migrations, seeding, CRUD, stable slugs, PATCH null semantics, canonical API errors, transactional feedback, filtering/pagination, ingestion/deduplication, scheduler adapter behavior, backup, and export. Live development checks cover plugin doctor, authenticated route mounting, dashboard workflows, explicit profile isolation, online backup, Cron status, Run Now, Pause/Resume, and Eastern next-run interpretation.

The scale gate generated 100,000 Stories and 500,000 Sources in a temporary SQLite database. A fully hydrated 50-Story Inbox page completed in 0.14 seconds on the acceptance machine. A development online backup was restored into an isolated directory, passed integrity/migration/count verification, and contained no WAL/SHM sidecars. The logical export was parsed successfully and contained exactly the required sections.

## Operations

Installation/update and verification require an explicit profile. Production mutations require an additional `-Production` acknowledgement. Backups use SQLite online backup and retain ten files. Restore excludes historical WAL/SHM sidecars. Export is streamed and omits secrets and article bodies.

## Deliberate deviations and deferrals

- `runs.config_snapshot_json` is deferred; it is not required for v1 Runs behavior.
- Topic terms are hard-deleted; Categories and Topics are soft-deleted.
- Taxonomy undelete UI, transition-only feedback redesign, enhanced telemetry export, and curated starter terms are deferred.
- Formal WCAG certification and a formal latency SLA are not claimed; keyboard access, focus, semantics, contrast, and representative scale checks remain release requirements.

## Release record

Stage-A accepted commit: `2620fe0e94dc73b935bbc61697dbbc7c0fb0c22e`.

Production was installed from that clean commit into the explicit `newsroom` profile. The pre-deployment profile contained no Newsroom plugin, database, or Cron job. A pre-smoke online backup was created at `plugin-data\newsroom\backups\newsroom-20260815T035918Z.db`.

Production Cron execution `3e918a3f152d455ca3aa2e24c4227106` completed successfully with three real web searches and zero qualifying Stories, which is a valid collection outcome. A separate controlled factual ingestion through Newsroom's start/submit/finish boundary created one Story with one primary Source; the Inbox and Open Original path were verified in the production Dashboard. All 17 seeded Topics are enabled after the smoke. Final integrity, profile verification, Cron status, and online backup (`newsroom-20260815T040306Z.db`) passed with the production scheduler active for the next 08:00 Eastern run.

Rollback is uninstalling plugin code while retaining data, or restoring the clean pre-smoke online backup using the documented writer-stop procedure.
