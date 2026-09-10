# Data safety QA — 9 September 2026

This pass focused on project startup and saving, with regression coverage for the existing annotation workflow. Changes remain uncommitted on `fix/stale-mask-metadata`.

## Findings addressed

1. **Duplicate startup could replace the active project before discovering an occupied port.** The launcher now binds Waitress before creating a fresh project. A binding failure therefore leaves project startup untouched. If fresh-project creation fails, the bound server closes. Regression tests cover successful order, occupied port, and project initialization failure.
2. **Class autosave failure did not protect edits on page close.** Class edits now stay pending until a successful matching save response. The footer identifies unsaved class edits, failed saves show class-manager feedback, and browser close/reload requests a warning while edits remain pending. Editing a class retries autosave. Tests cover failure, successful retry, and an older response arriving after a newer edit.
3. **The editor could become usable without successfully loading its project state.** The refined workspace stays inert during initialization. Manifest, settings, or class loading failure keeps editing disabled and shows reload guidance. Tests cover each failure and successful startup.

Only `app.py` and the refined script changed in application code during this pass. The original UI files match the preserved hash baseline. Pre-edit copies are under `.tmp/data-safety-qa-backup/`.

## Verification and limits

- Regression checks use isolated settings, manifests, and annotations with SAM model loading disabled.
- Final full-suite rerun: **282 passed in 24.31 seconds**.
- Ruff, JavaScript syntax, and Git whitespace checks pass.
- One full-suite attempt returned HTTP 500 in the CSV annotation save round trip (281 other tests passed). Its focused API rerun passed all six tests. The initial failure's cause was not established; it should not be represented as a confirmed application fix or a confirmed Windows issue.
- The first sandboxed attempt also encountered a Windows temporary-directory access error; subsequent test runs used the isolated environment outside that sandbox.
- This pass did not perform browser interaction tests or GPU inference. Native unload warnings remain subject to browser behavior.
- Multiple server processes sharing project files, or concurrent editors of the same project, still require separate concurrency design. Binding first protects duplicate launches on the same address, not all multi-process scenarios.
