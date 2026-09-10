# Refined annotation workspace

The normal app URL now opens the refined workspace. Add `?ui=original` to the
same URL to open the previous layout, for example `http://127.0.0.1:5000/?ui=original`.
Save pending edits before switching layouts: switching reloads the page.

The original `static/index.html` and `static/style.css` are retained unchanged
by this refinement. The new presentation uses `static/index-refined.html` and
`static/style-refined.css`, copied from those originals. Both layouts share the
existing annotation and SAM2 controllers. The interaction refinement uses separate
`script-refined.js` and `classUiController-refined.js` copies to preserve the original
layout's behavior. `manualClassPicker.js` provides the native, keyboard-accessible
box classification popup. The copied main script retains the image-loading,
orientation, asynchronous-operation, and review fixes.
`static/refinedUi.js` only handles panel visibility, keyboard activation of file
pickers, and canvas resizing after layout changes.

## Where the controls are

| Task | Location |
| --- | --- |
| Load an image or folder | Header |
| Draw a new annotation (Manual Box) or generate SAM2 candidates | Toolbar above the image |
| Presets, device, advanced SAM2 settings, preprocessing, clear candidates | Left panel, SAM2 settings |
| Assign a class, one-click acceptance, undo/redo | Right panel, Class Assignment |
| Create a named class | Right panel, Classes → Add class; or Create class… in the box popup |
| Change class names, colors, hotkeys, delete a class | Right panel, Classes → Edit beside a class |
| Inspect annotations, precise box editing, current-image import | Right panel, below Class Assignment |
| Match/import annotation files for a batch | Left panel, Batch annotation matching |
| Save the current image, review/confirm empty/reopen, navigate images | Bottom bar |
| Save all, export current, validate project, export project COCO | Header, Project & export |

Use the panel icons at the left and right edges of the image toolbar to collapse
or restore the side panels. Tooltips and accessible names identify each action.
The image queue shows a filename, review state, and an unsaved indicator when needed.
All, Needs review, and Completed are the primary filters; Completed includes reviewed
images and confirmed-empty images. More filters retains the other existing filters.
Matching details remain available for the selected image and in batch matching.
Narrow windows place the panels below the canvas. Model settings,
annotation formats, review rules, and shortcuts retain their existing behavior.
This remains a bounding-box annotation application; mask editing is future work.


### Class behavior refinement

The refined UI asks for a name immediately when drawing the first box in a project with no classes. Its guidance follows the current class count after creation, project loading, annotation import, and removal. The class list persists when opening another image folder; folder selection does not create a separate project.

Use **Edit > Remove class** to remove an unwanted class. Removal is blocked when any loaded annotation uses the class; reassign those annotations first. Removal never deletes annotations or rewrites saved annotation files. A class referenced by a subsequently loaded file can be restored. Class saves are serialized so delayed responses cannot overwrite newer edits.

The original UI remains available at `/?ui=original`. Files from before this class refinement are copied under `.tmp/class-behavior-backup/`. No runtime project classes or annotations were cleared.


### Project separation

New/Open project now preserves and restores separate manifests, classes, and annotation output folders. New classes are empty unless reuse is explicitly checked. Source images must be selected again on opening a project. `apiClient-refined.js` attaches the project's identity to requests; stale tabs cannot mutate the newly active project. The original client file is unchanged. Pre-change files are in `.tmp/project-separation-backup/`.


### Canvas visibility

The lower-left **View overlays** menu controls candidates, annotation boxes, and annotation IDs. **Image only** temporarily hides every overlay and restores the previous choices when unchecked. These session-local settings affect display and hit-testing only; save/export and review status are unchanged. Hiding a layer clears its selection. Visibility controls are disabled while drawing, choosing a class for a pending box, or editing box geometry. Entering Manual Box mode restores annotation visibility and exits image-only view.

The refined page loads `canvasRenderer-refined.js`; the original renderer is preserved. The files from before this change are in `.tmp/canvas-visibility-backup/`.


### Working state

A compact strip above the canvas shows the current tool, active class, review/save state, and selection counts, including when the side panels are collapsed. It distinguishes manual drawing, pending class assignment, box movement/resizing, one-click acceptance, and image-only inspection. Dirty images display in-progress/unsaved status; completion color is reserved for clean reviewed or confirmed-empty images. The strip derives its text from existing state without modifying annotation data and only updates changed text for screen readers. Pre-change files are in `.tmp/working-state-backup/`.


### Usability verification

See `USABILITY_VERIFICATION.md` for the 250-image/40-class browser checks, responsive widths, exposed issues, fixes, and limits.


### Fresh launch behavior

Running `python app.py` now archives the previous active project and starts a fresh project without classes. Existing annotation files are untouched. Use New / Open project to restore prior work explicitly. Browser refreshes retain the current session. Startup fails if the archive or active-manifest write fails. The pre-change launcher is backed up in `.tmp/fresh-start-backup/app.py`.


### Class shortcuts

The refined UI uses `classManager-refined.js`. B is reserved for Manual Box and U for Undo; class creation skips both and the editor rejects them. Existing conflicting assignments show a reserved marker and can be cleared or replaced in Edit. Modifier combinations are not interpreted as class keys. Originals are preserved; pre-change refined files are in `.tmp/class-shortcut-backup/`.
