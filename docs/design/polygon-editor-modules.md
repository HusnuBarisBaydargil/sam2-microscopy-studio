# Polygon editor modules

The refined page loads the plain scripts under `static/polygon/` before
`static/polygonEditor.js`. There is no bundler or ES-module migration in this pass.

| File | Responsibility |
| --- | --- |
| `state.js` | Annotation/proposal snapshots, dirty tracking, review state, monotonic IDs and undo/redo. |
| `geometry.js` | Boundary splicing, shape hit testing and duplicate-point detection. Pure geometry only. |
| `persistence.js` | Folder-file matching and the existing folder/server autosave protocol. |
| `viewport.js` | Image coordinates, fit/zoom, camera panning and listener binding/removal. |
| `localTools.js` | Redraw edge and Cut line sessions, anchors, draft input, controls, previews and validated Apply. |
| `polygonEditor.js` | UI assembly, operation locking, rendering saved objects/suggestions, drawing/dragging, classes, SAM2 and image/review navigation. |

`localTools` owns uncommitted local-tool state. Committed history belongs to
`state`; Apply calls the editor's existing operation/save functions. The editor
retains the common keyboard guards before forwarding local-tool keys.

Viewport callbacks read current editor state when events occur. Persistence uses
live accessors for state/revision/save flags, preserving asynchronous save timing.
The coordinator retains mounting/disposal order and calls each module's cleanup
at the original points. Folder conflict/permission handling remains in
`static/projectFolder.js`; server validation and annotation formats are unchanged.

Tests load the actual modules. Geometry/history/folder tests call their exported
functions; the editor interaction test mounts the composed editor and exercises
autosave, failures/retry, undo/redo, panning, correction, splitting and disposal.
The refined-UI test checks script order and asset presence.

This is a bounded extraction. Saved-object rendering, SAM2 interactions, class
administration and image/review workflows remain in the coordinator for later passes.
