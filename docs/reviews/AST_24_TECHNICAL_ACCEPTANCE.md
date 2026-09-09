# AST-24 Technical Acceptance

Status: **technically accepted on the stacked implementation branch; not canonically DONE**

AST-24 remains downstream of the still-open AST-05 owner-machine physical wake/sign-in gate. This note records only the bounded technical evidence for AST-24 and does not merge, deploy, promote the trial runtime, or advance the canonical Astra ledger.

## Exact head

- Branch: `astra/AST-24-welcome-interest`
- Parent AST-23 head: `2ab4715ff1c267d8476a88bcd997380d16976d9d`
- Accepted AST-24 head before this evidence-only note: `30028d3cb8344f85d6acd05f54412a17a32833a7`
- Exact-head CI run: `34230880064`
- CI conclusion: success

## Product contract proved

The ordinary first-Watch path now:

1. Presents an empty-workspace Welcome experience.
2. Accepts an interest in ordinary language without Topic IDs, policy IDs, or other internal identifiers.
3. Provides an editable Watch name.
4. Visibly seeds an editable primary-term field from the interest.
5. Requires explicit user confirmation of at least one primary term before save.
6. Uses the AST-23 paused Watch setup contract.
7. Retains the form and exact request identity after an unreachable save and browser reload.
8. Reuses that same request identity on retry, preventing duplicate canonical setup.
9. Returns a visibly paused zero-source Watch after save.
10. Makes `Add Sources` the truthful next step and does not begin collection.
11. Reads the confirmed canonical Topic scope back from Topic vocabulary.
12. Keeps the legacy raw-ID creation path behind an explicit Advanced disclosure.

## Interactive browser qualification

Artifact: `astra24-browser-onboarding`, artifact ID `10057731090` from run `34230880064`.

The isolated fixture used only an ephemeral `127.0.0.1` port. Evidence records:

- `trial_contacted=false`
- `paid_calls=0`
- `external_discovery_requests=0`
- `setup_attempt_count=2`
- `same_retry_identity=true`
- `server_watch_count=1`

Captured states:

1. `01-welcome-desktop.png`
2. `02-loading-watches.png`
3. `03-populated-setup.png`
4. `04-api-unreachable.png`
5. `05-reload-recovery.png`
6. `06-paused-success.png`
7. `07-paused-reload.png`
8. `08-returning-home.png`
9. `09-mobile-390.png`
10. `10-zoom-200.png`

Keyboard traversal reached the natural-language setup fields. The 390 CSS-pixel viewport had no horizontal overflow.

GitHub-hosted headless Chrome did not apply desktop `Ctrl+=` zoom. The qualification therefore used Chromium DevTools `Emulation.setDeviceMetricsOverride` to exercise an effective 200% rendering environment: CSS viewport `1440 -> 720` while device pixel ratio progressed to `2.0`. The manifest records both the method and that the literal keyboard shortcut was unsupported, rather than claiming a keyboard zoom occurred.

## CI evidence

At `30028d3cb8344f85d6acd05f54412a17a32833a7`:

- frontend lint: pass
- TypeScript typecheck: pass
- frontend production build: pass
- AST-04 browser regression: pass
- AST-24 onboarding browser qualification: pass
- Ruff: pass
- mypy baseline step: pass/informational
- full backend pytest: pass
- hosted Windows AST-05 lifecycle regression: pass

An earlier hosted Windows run produced a transient duplicate-launch PID failure. The exact accepted head subsequently passed the complete Windows lifecycle smoke. This does not close AST-05's separate owner-machine physical wake/sign-in evidence requirement.

## Boundary

This acceptance does **not**:

- mark AST-05 DONE;
- erase the outstanding owner-machine wake/sign-in qualification;
- mark the canonical AST-24 ledger entry DONE;
- merge AST-24 or its parent stack;
- start AST-25;
- contact the Phase 29 trial runtime or port 8127;
- authorize paid provider calls.
