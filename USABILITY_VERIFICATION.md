# Usability verification — 9 September 2026

Tested the refined UI against isolated synthetic data: 250 images (640 × 480), 40 long class names, long image filenames, and a long project name. The test server used port 5095 with SAM disabled and all settings/annotations under `.tmp/usability-check/`. User project data was not changed.

| Check | Result |
| --- | --- |
| Load folder containing 250 images | All 250 appeared; navigation reached image 250 |
| Search filename `0249` | Exactly one result; selection retained keyboard focus |
| Search class `category 40` | Exactly one of 40 classes visible |
| Clear searches | All 250 images and 40 classes restored |
| Manual annotation with 40 classes | Three quick choices and all 40 classes in dropdown; correct active-class assignment |
| Undo, redo, save | Annotation removed, restored, and saved to isolated output |
| Layout widths 1280, 1024, 768, 360 | No document horizontal overflow with the full queue and class list |
| Many classes | Class list limited to 320 px; later controls remain accessible |
| Image-only view | Working state changed to inspection; prior overlay settings restored |
| Collapse both panels | Panels hidden; working-state strip remained visible |
| Browser console | No error entries during the checked flows |

## Fixes made

- Added filename and class search fields.
- Limited queue filenames to two visible lines; full names remain in the DOM and row tooltips.
- Bounded the class-list height with independent scrolling.
- Preserved image-row keyboard focus after rerendering the queue.
- Allowed long project names to wrap within the header.

Original UI files are preserved. Pre-change refined files are copied under `.tmp/usability-backup/`. Changes remain uncommitted.

## Limits

The original 250-BMP fixture transferred about 230 MB through the browser automation file chooser and took several minutes. An equivalent compressed PNG fixture transferred quickly. This is not a formal performance benchmark or a guarantee for arbitrary dataset sizes. Source images are synthetic; GPU inference, real mask accuracy, touch gestures, and a full human annotation study were not tested. The model-loading bypass was active throughout this check.


Follow-up correction: the file-chooser automation also delayed a single small PNG in the next QA pass. The earlier timing difference does not establish file size as the cause; see `USABILITY_QA_FOLLOWUP.md`.
