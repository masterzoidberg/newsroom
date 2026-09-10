# Newsroom completion plan rework

Prepared 2026-09-09 for adoption after the active backend-acceptance task finishes. This directory is a proposed successor execution plan. Until the transition checklist is completed, `plan/astra/TASKS.md` remains the status authority.

## Purpose

Move Newsroom to completion with fewer artificial dependencies and clearer definitions of “done.” The existing Astra plan correctly protects safety and evidence, but mixes implementation, design decisions, optional enhancements, external validation and final qualification in one 46-record future ledger. That makes the app appear farther from completion and forces independent capabilities into a mostly serial queue.

This rework:

- preserves earned AST-01–24 evidence and IDs;
- starts only after the current backend fix reports an exact head and retained result;
- defines a usable local release before optional expansion;
- removes dependencies that do not represent technical prerequisites;
- treats cross-surface audits and release qualification as checkpoints, not open-ended feature work;
- keeps paid work, trial contact, deployment and human claims behind their existing authorization gates.

## Documents

- [REWORKED_COMPLETION_PLAN](REWORKED_COMPLETION_PLAN.md): scope, dependency changes, execution lanes and release gates.
- [AUTONOMOUS_EXECUTION_RUNBOOK](AUTONOMOUS_EXECUTION_RUNBOOK.md): the minimum-handoff sequence for Codex to execute multiple bounded tasks per run.
- [TRANSITION_CHECKLIST](TRANSITION_CHECKLIST.md): how to adopt the rework safely after backend acceptance finishes.

## Authority rule

Do not execute from this directory while the current backend task is still running. After transition, create one canonical status ledger from this plan and archive or clearly supersede conflicting `NEXT` instructions. Historical evidence must remain unchanged.
