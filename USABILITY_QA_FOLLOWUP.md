# Usage QA follow-up — 9 September 2026

Application code was not modified in this pass. Browser testing used a fresh server on port 5096, a synthetic image, and isolated runtime files under `.tmp/usage-qa2/`. SAM loading was disabled.

## Confirmed findings

### 1. Fixed: project dialog allowed background editing shortcuts

Reproduction: create and select an annotation, open New / Open project, focus Cancel, press Escape, then Delete. Escape leaves the dialog open; Delete removes the selected annotation behind it. Confirmed in the browser. The synthetic annotation was restored using Undo.

`static/script-refined.js:1934` recognizes the SAM, preprocessing, and help modals but not the native project dialog. Exclude workspace shortcuts while that dialog is open and allow its native Escape handling. Add a regression case covering Delete, B, Undo, and arrow keys with dialog focus.

### 2. Fixed: class shortcuts conflicted with editing shortcuts

Creating Background automatically assigns B, but with an annotation selected, B enters Manual Box mode and leaves its class unchanged. Confirmed in the browser. The same source-level conflict exists for U/Undo. See `static/classManager.js:30` and `static/script-refined.js:1975` / `2004`.

Reserve application shortcut keys when assigning or editing class hotkeys, and explain any existing conflicting assignments instead of silently advertising nonfunctional shortcuts.

### 3. Fixed: a newly created class could be hidden by the class search

With the class search set to Background, create Target. The working strip shows Target as active while the class list still shows only Background. Confirmed in the browser. See `static/script-refined.js:362` and `1272`.

Clear the search after successful creation, or explicitly reveal the new class. Existing search behavior should remain unchanged when merely selecting/editing a class.

### 4. Fixed: stale first-class guidance

After creating multiple classes, the class-source hint still says to start by creating the first class. Confirmed in the browser. Update onboarding text after creation, removal, and loading rather than treating it as a startup-only message.

## Optional refinement

Fresh launches are all named New project (`app.py:575`). Archived sessions are distinguished by UUID fragments, which are difficult to recognize. Offer a project name/rename action when the user begins saving work. This is an organization improvement, not a data-loss finding.

## Checks that passed

- Fresh server session began with no classes and displayed New project.
- The first manual box immediately opened the focused class-name field.
- Class creation and manual annotation worked.
- Undo restored the synthetic annotation after the dialog-keyboard reproduction.
- Saving did not mark the image reviewed automatically.
- The 360-pixel-wide layout had no document horizontal overflow.

## Limits and timing correction

The browser review action reached overwrite confirmation and was cancelled; successful review completion was not verified in this browser pass. Review persistence is checked separately by API regression tests. GPU inference, touch gestures, and multi-user behavior were not tested.

The browser file chooser again took several minutes for a single small PNG. This contradicts attributing the earlier delay solely to the 250-BMP transfer size. File-chooser automation timings are inconclusive and must not be used as application performance measurements.


Project-dialog keyboard fix: the workspace handler now returns immediately while the native dialog is open. Browser checks confirmed text editing, Escape closing, and focus returning to the opener. The regression check covers Delete, B, Undo/Redo, arrow keys, normal shortcuts after closure, and the existing pending-switch cancellation guard. 57 focused tests passed; Ruff and JavaScript syntax checks passed. Other findings remain open.


Class-shortcut fix: the refined class manager reserves B and U, rejects manual reassignment to them, and skips them in automatic assignment. Existing conflicts are retained but marked reserved in the class editor/list; the manual popup does not advertise those keys. Class hotkeys require an unmodified key, leaving Ctrl+Z/Ctrl+Y to Undo/Redo. Names, IDs, and annotations are preserved. 64 focused tests passed, including key exhaustion, legacy conflicts, manual validation, and pending-box shortcut routing. Other open findings remain unchanged.


Class-search creation fix: successful creation clears the class search and scrolls the class list to the appended class, without scrolling the page. Blank or duplicate names leave the query unchanged. This shared creation path covers sidebar and manual-box popup creation. Four focused tests passed, including the previous shortcut and popup checks.


Onboarding fix: class-control rendering now owns the guidance text and derives it from the current class count. It switches between first-class guidance and selection/editing guidance after creation, loading/import, and removal. Startup/import messages no longer overwrite it with stale snapshots. Five focused tests passed, including unchanged-text updates and returning to an empty list.
