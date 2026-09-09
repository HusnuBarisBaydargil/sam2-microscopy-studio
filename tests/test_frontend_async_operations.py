"""Run actual UI handlers against deferred responses to reproduce navigation races."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const noop = () => {};
const context = {window: {confirm: () => true}, console, Map, Set, JSON};
vm.createContext(context);
for (const name of ['frontendConfig', 'stateStore', 'fileUtils', 'imageController']) {
    vm.runInContext(fs.readFileSync(`static/${name}.js`, 'utf8'), context);
}
const store = context.window.SAM2StateStore;
const state = store.createAppState();
const a = {id: 'a', name: 'a.png', width: 30, height: 20};
const b = {id: 'b', name: 'b.png', width: 30, height: 20};
state.images = [a, b];
state.currentImage = a;
for (const image of state.images) store.initializeImageState(state, image.id);
const loaderState = {hidden: true};
Object.assign(context, {
    appState: state, stateStore: store, imageController: context.window.SAM2ImageController, apiWorkflows: {},
    annotationSavePending: false, annotationDirectoryChangePending: false,
    annotationWorkflowController: {}, loadingRequests: new Map(),
    loader: {classList: {toggle: (_, hidden) => {loaderState.hidden = hidden;}}},
    loaderText: {}, keepAnnotationsInput: {checked: true},
    classificationSelect: {value: 'cell'},
    currentAnnotationFormat: () => 'csv', currentSamSettingsPayload: () => ({}),
    samPreprocessPayload: () => ({method: 'original', params: {}}),
    currentSamPresetLabel: () => 'default', annotationMaskMetadata: value => value,
    publicImageName: image => image.name, publicAnnotationPath: value => value,
    imageDimensions: image => ({width: image.width, height: image.height}),
    annotationMatchModeForImage: () => 'path', annotationMatchDisplay: () => ({}),
    normalizeAnnotation: value => value, applySamSettings: noop,
    ensureClassesForAnnotations: () => 0, scheduleProjectClassesSave: noop,
    confirmReplaceUnsavedAnnotations: () => true, formatLabel: value => value,
    formatFromFileName: () => 'csv', parseAnnotationFile: noop, phiSafeMode: () => false,
    applyLoadedClasses: noop, renderClassControls: noop,
    selectedPreprocessMethod: () => 'clahe', preprocessLabel: value => value,
    currentPreprocessParams: () => ({}),
});
for (const name of ['updateStatus', 'showToast', 'renderImageBrowser', 'updateAnnotationLog',
    'draw', 'updateButtonStates', 'updateMatchSummaryDisplay', 'updateCurrentImageDisplay',
    'resizeCanvasToContainer', 'fitImageToView', 'resetInteractionState']) context[name] = noop;
// Select complete top-level declarations; run production handler bodies unchanged.
const source = fs.readFileSync('static/script.js', 'utf8');
const starts = [...source.matchAll(/^    (?:async )?function (\w+)\(/gm)];
const selected = new Set(['beginAnnotationOperation', 'handleRunSam', 'setLoader',
    'currentCandidates', 'currentAnnotations', 'currentImageId', 'initializeImageState',
    'loadServerAnnotationsForCurrentImage', 'saveImageAnnotationsToServer',
    'applyLoadedAnnotations', 'setAnnotationsForImage', 'selectImageByIndex',
    'handleApplyPreprocess', 'loadImageRecord', 'handleLoadAnnotationFile',
    'handleSaveAllServerAnnotations', 'handleSetAnnotationDir', 'handleReviewImage',
    'handleLoadMatchedAnnotations']);
for (let index = 0; index < starts.length; index++) {
    if (selected.has(starts[index][1])) {
        vm.runInContext(source.slice(starts[index].index, starts[index + 1].index), context);
    }
}
context.annotationWorkflowController.setAnnotationsForImage = (s, image, values, options) => {
    s.annotationsByImage.set(image.id, values);
    image.reviewStatus = options.markDirty ? 'in_progress' : context.imageController.normalizeReviewStatus(options.reviewStatus, values.length);
    return values;
};
function deferred() {
    let resolve;
    const promise = new Promise(r => {resolve = r;});
    return {promise, resolve};
}
function samReply(x) {
    return {ok: true, json: async () => ({masks: [{bbox: [x, 0, 4, 4]}]})};
}
function nextTurn() {return new Promise(resolve => setImmediate(resolve));}
async function main() {
"""

SCENARIOS = {
    "image_load_displays_server_validation_error": r"""
        context.apiWorkflows.loadImage = async () => ({ok: false, status: 400,
            statusText: 'BAD REQUEST', json: async () => ({error: 'Export a single 2D image first.'})});
        let message;
        context.updateStatus = text => {message = text;};
        assert.equal(await context.loadImageRecord(a), false);
        assert.equal(message, 'Error loading image: Export a single 2D image first.');
        assert.equal(a.originalImage, undefined);
        assert.equal(loaderState.hidden, true);
    """,
    "image_load_non_json_error_keeps_http_fallback": r"""
        context.apiWorkflows.loadImage = async () => ({ok: false, status: 502,
            statusText: 'Bad Gateway', json: async () => {throw new Error('Not JSON');}});
        let message;
        context.updateStatus = text => {message = text;};
        assert.equal(await context.loadImageRecord(a), false);
        assert.equal(message, 'Error loading image: Server error: 502 Bad Gateway');
    """,
    "bulk_review_restore_drops_replaced_project_during_dimension_check": r"""
        const request = deferred();
        context.ensureProjectImageDimensions = () => request.promise;
        let imported = false;
        context.annotationWorkflowController.loadServerMatchedAnnotations = async () => {imported = true;};
        const pending = context.handleLoadMatchedAnnotations();
        store.resetProjectState(state);
        const replacement = {...a};
        state.images = [replacement];
        state.currentImage = replacement;
        request.resolve(true);
        await pending;
        assert.equal(imported, false);
        assert.equal(state.currentImage, replacement);
    """,
    "review_completion_waits_for_save_then_advances": r"""
        a.reviewStatus = 'in_progress';
        state.annotationsByImage.set(a.id, [{id: 1, bbox: [1, 1, 4, 4]}]);
        const request = deferred();
        let payload, nextIndex;
        context.annotationWorkflowController.saveImageAnnotationsToServer = (s, options) => {payload = options; return request.promise;};
        context.selectImageByIndex = async index => {nextIndex = index;};
        const pending = context.handleReviewImage('reviewed');
        assert.equal(a.reviewStatus, 'in_progress');
        assert.equal(payload.reviewStatus, 'reviewed');
        request.resolve({review_status: 'reviewed'});
        await pending;
        assert.equal(a.reviewStatus, 'reviewed');
        assert.equal(a.reviewClassSignature, store.reviewClassSignature(state));
        assert.equal(nextIndex, 1);
    """,
    "confirmed_empty_is_explicit_and_can_be_reopened": r"""
        a.reviewStatus = 'unreviewed';
        let savedStatus;
        context.annotationWorkflowController.saveImageAnnotationsToServer = async (s, options) => {
            savedStatus = options.reviewStatus;
            return {review_status: options.reviewStatus};
        };
        await context.handleReviewImage('confirmed_empty', false);
        assert.equal(savedStatus, 'confirmed_empty');
        assert.equal(a.reviewStatus, 'confirmed_empty');
        await context.handleReviewImage('in_progress', false);
        assert.equal(a.reviewStatus, 'in_progress');
        assert.equal(savedStatus, 'in_progress');
    """,
    "review_failure_or_edits_do_not_complete_or_advance": r"""
        a.reviewStatus = 'in_progress';
        state.annotationsByImage.set(a.id, [{id: 1, bbox: [1, 1, 4, 4]}]);
        let advances = 0;
        context.selectImageByIndex = async () => {advances++;};
        context.annotationWorkflowController.saveImageAnnotationsToServer = async () => {throw new Error('offline');};
        await context.handleReviewImage('reviewed');
        assert.equal(a.reviewStatus, 'in_progress');
        assert.equal(advances, 0);
        const request = deferred();
        context.annotationWorkflowController.saveImageAnnotationsToServer = () => request.promise;
        const pending = context.handleReviewImage('reviewed');
        state.annotationsByImage.get(a.id)[0].bbox[0] = 2;
        store.markCurrentImageDirty(state);
        request.resolve({review_status: 'reviewed'});
        await pending;
        assert.equal(a.reviewStatus, 'in_progress');
        assert.ok(state.dirtyImages.has(a.id));
        assert.equal(advances, 0);
    """,
    "review_completion_does_not_override_user_navigation": r"""
        state.annotationsByImage.set(a.id, [{id: 1, bbox: [1, 1, 4, 4]}]);
        const request = deferred();
        context.annotationWorkflowController.saveImageAnnotationsToServer = () => request.promise;
        let advances = 0;
        context.selectImageByIndex = async () => {advances++;};
        const pending = context.handleReviewImage('reviewed');
        state.currentImage = b;
        request.resolve({review_status: 'reviewed'});
        await pending;
        assert.equal(a.reviewStatus, 'reviewed');
        assert.equal(state.currentImage, b);
        assert.equal(advances, 0);
    """,
    "review_reopens_on_edits_and_class_definitions_not_colors": r"""
        state.classes = [{id: 1, name: 'cell', color: 'red'}];
        a.reviewStatus = 'reviewed';
        b.reviewStatus = 'confirmed_empty';
        a.reviewClassSignature = b.reviewClassSignature = store.reviewClassSignature(state);
        state.classes[0].color = 'blue';
        store.invalidateReviewsForClassChanges(state);
        assert.equal(a.reviewStatus, 'reviewed');
        store.markCurrentImageDirty(state);
        assert.equal(a.reviewStatus, 'in_progress');
        state.classes[0].name = 'nucleus';
        store.invalidateReviewsForClassChanges(state);
        assert.equal(b.reviewStatus, 'in_progress');
        assert.ok(state.dirtyImages.has(b.id));
    """,
    "empty_confirmation_cannot_discard_annotations_or_unconfirmed_candidates": r"""
        let saves = 0;
        context.annotationWorkflowController.saveImageAnnotationsToServer = async () => {saves++; return {};};
        state.annotationsByImage.set(a.id, [{id: 1, bbox: [1, 1, 4, 4]}]);
        await context.handleReviewImage('confirmed_empty', false);
        assert.equal(saves, 0);
        state.annotationsByImage.set(a.id, []);
        state.candidateAnnotationsByImage.set(a.id, [{id: 'candidate'}]);
        context.window.confirm = () => false;
        await context.handleReviewImage('confirmed_empty', false);
        assert.equal(saves, 0);
        assert.equal(a.reviewStatus, undefined);
    """,
    "sam_targets_original_image": r"""
        const request = deferred();
        context.apiWorkflows.runSam = () => request.promise;
        const pending = context.handleRunSam();
        state.currentImage = b;
        state.selectedCandidateIds.add('b-selection');
        request.resolve(samReply(1));
        await pending;
        assert.equal(state.candidateAnnotationsByImage.get(a.id)[0].bbox[0], 1);
        assert.equal(state.candidateAnnotationsByImage.get(b.id).length, 0);
        assert.ok(state.selectedCandidateIds.has('b-selection'));
    """,
    "sam_rejects_replaced_session_with_same_id": r"""
        const request = deferred();
        context.apiWorkflows.runSam = () => request.promise;
        const pending = context.handleRunSam();
        store.resetProjectState(state);
        const replacement = {...a};
        state.images = [replacement];
        state.currentImage = replacement;
        store.initializeImageState(state, a.id);
        request.resolve(samReply(1));
        await pending;
        assert.equal(state.candidateAnnotationsByImage.get(a.id).length, 0);
        assert.equal(replacement.samHasRun, undefined);
    """,
    "sam_latest_request_wins": r"""
        const first = deferred(), second = deferred();
        const requests = [first, second];
        context.apiWorkflows.runSam = () => requests.shift().promise;
        const oldRun = context.handleRunSam();
        const newRun = context.handleRunSam();
        second.resolve(samReply(2));
        await newRun;
        first.resolve(samReply(1));
        await oldRun;
        assert.equal(state.candidateAnnotationsByImage.get(a.id)[0].bbox[0], 2);
    """,
    "sam_preserves_edits_during_request": r"""
        const request = deferred();
        context.keepAnnotationsInput.checked = false;
        context.apiWorkflows.runSam = () => request.promise;
        const pending = context.handleRunSam();
        const edited = [{id: 1, bbox: [3, 3, 4, 4]}];
        state.annotationsByImage.set(a.id, edited);
        state.dirtyImages.add(a.id);
        request.resolve(samReply(1));
        await pending;
        assert.strictEqual(state.annotationsByImage.get(a.id), edited);
        assert.equal(state.candidateAnnotationsByImage.get(a.id).length, 0);
        assert.ok(state.dirtyImages.has(a.id));
    """,
    "load_targets_original_image_and_preserves_other_dirty_state": r"""
        const request = deferred();
        context.annotationWorkflowController.loadServerAnnotationsForImage = () => request.promise;
        state.dirtyImages.add(a.id);
        state.dirtyImages.add(b.id);
        const pending = context.loadServerAnnotationsForCurrentImage({silentWhenMissing: false});
        state.currentImage = b;
        request.resolve({exists: true, annotations: [{id: 7}], path: 'a.csv'});
        assert.equal(await pending, true);
        assert.equal(state.annotationsByImage.get(a.id)[0].id, 7);
        assert.equal(state.annotationsByImage.get(b.id).length, 0);
        assert.ok(!state.dirtyImages.has(a.id));
        assert.ok(state.dirtyImages.has(b.id));
    """,
    "save_clears_only_original_unchanged_image": r"""
        const request = deferred();
        context.annotationWorkflowController.saveImageAnnotationsToServer = () => request.promise;
        state.dirtyImages.add(a.id);
        state.dirtyImages.add(b.id);
        const pending = context.saveImageAnnotationsToServer(a);
        state.currentImage = b;
        request.resolve({path: 'a.csv'});
        await pending;
        assert.ok(!state.dirtyImages.has(a.id));
        assert.ok(state.dirtyImages.has(b.id));

        const next = deferred();
        context.annotationWorkflowController.saveImageAnnotationsToServer = () => next.promise;
        state.dirtyImages.add(a.id);
        const saving = context.saveImageAnnotationsToServer(a);
        state.annotationsByImage.get(a.id).push({id: 8});
        next.resolve({path: 'a.csv'});
        assert.equal((await saving).stale, true);
        assert.ok(state.dirtyImages.has(a.id));
    """,
    "import_targets_original_image": r"""
        const request = deferred();
        context.annotationWorkflowController.importAnnotationFile = () => request.promise;
        const pending = context.handleLoadAnnotationFile({target: {files: [{name: 'a.csv'}]}});
        state.currentImage = b;
        request.resolve({annotations: [{id: 9}], usedMatchedRows: true});
        await pending;
        assert.equal(state.annotationsByImage.get(a.id)[0].id, 9);
        assert.equal(state.annotationsByImage.get(b.id).length, 0);
    """,
    "import_preserves_newer_edits": r"""
        const request = deferred();
        context.annotationWorkflowController.importAnnotationFile = () => request.promise;
        const pending = context.handleLoadAnnotationFile({target: {files: [{name: 'a.csv'}]}});
        state.annotationsByImage.get(a.id).push({id: 10});
        request.resolve({annotations: [{id: 9}], usedMatchedRows: true});
        await pending;
        assert.equal(state.annotationsByImage.get(a.id)[0].id, 10);
    """,
    "import_rejects_replaced_session_with_same_id": r"""
        const request = deferred();
        context.annotationWorkflowController.importAnnotationFile = () => request.promise;
        const pending = context.handleLoadAnnotationFile({target: {files: [{name: 'a.csv'}]}});
        store.resetProjectState(state);
        const replacement = {...a};
        state.images = [replacement];
        state.currentImage = replacement;
        store.initializeImageState(state, a.id);
        request.resolve({annotations: [{id: 9}], usedMatchedRows: true});
        await pending;
        assert.equal(state.annotationsByImage.get(a.id).length, 0);
        assert.equal(state.dirtyImages.size, 0);
    """,
    "save_all_stops_dispatch_after_session_reset": r"""
        const request = deferred();
        const dispatched = [];
        context.annotationWorkflowController.saveImageAnnotationsToServer = (s, options) => {
            dispatched.push(options.imageRecord);
            return request.promise;
        };
        state.dirtyImages.add(a.id);
        state.dirtyImages.add(b.id);
        const pending = context.handleSaveAllServerAnnotations();
        assert.equal(dispatched.length, 1);
        assert.strictEqual(dispatched[0], a);
        store.resetProjectState(state);
        const replacement = {...a};
        state.images = [replacement];
        state.currentImage = replacement;
        store.initializeImageState(state, a.id);
        state.dirtyImages.add(a.id);
        const replacementMatch = {status: 'matched', path: 'replacement.csv'};
        state.annotationMatchesByImage.set(a.id, replacementMatch);
        request.resolve({path: 'a.csv'});
        await pending;
        assert.equal(dispatched.length, 1);
        assert.ok(state.dirtyImages.has(a.id));
        assert.strictEqual(state.annotationMatchesByImage.get(a.id), replacementMatch);
        assert.equal(loaderState.hidden, true);
    """,
    "overlapping_saves_never_dispatch_second_write": r"""
        const request = deferred();
        let dispatchCount = 0;
        context.annotationWorkflowController.saveImageAnnotationsToServer = () => {
            dispatchCount++;
            return request.promise;
        };
        const pending = context.saveImageAnnotationsToServer(a);
        await assert.rejects(context.saveImageAnnotationsToServer(a), /Wait for/);
        await assert.rejects(context.saveImageAnnotationsToServer(b), /Wait for/);
        assert.equal(dispatchCount, 1);
        request.resolve({path: 'a.csv'});
        await pending;
        assert.equal(context.annotationSavePending, false);
    """,
    "session_reset_does_not_release_pending_server_write": r"""
        const request = deferred();
        let dispatchCount = 0;
        context.annotationWorkflowController.saveImageAnnotationsToServer = () => {
            dispatchCount++;
            return request.promise;
        };
        const pending = context.saveImageAnnotationsToServer(a);
        store.resetProjectState(state);
        const replacement = {...a};
        state.images = [replacement];
        state.currentImage = replacement;
        store.initializeImageState(state, a.id);
        await assert.rejects(context.saveImageAnnotationsToServer(replacement), /Wait for/);
        assert.equal(dispatchCount, 1);
        request.resolve({path: 'a.csv'});
        assert.equal((await pending).stale, true);
        await context.saveImageAnnotationsToServer(replacement);
        assert.equal(dispatchCount, 2);
    """,
    "failed_save_releases_server_write_guard": r"""
        let dispatchCount = 0;
        context.annotationWorkflowController.saveImageAnnotationsToServer = async () => {
            dispatchCount++;
            if (dispatchCount === 1) throw new Error('Save failed');
            return {path: 'a.csv'};
        };
        state.dirtyImages.add(a.id);
        await assert.rejects(context.saveImageAnnotationsToServer(a), /Save failed/);
        assert.ok(state.dirtyImages.has(a.id));
        assert.equal(context.annotationSavePending, false);
        await context.saveImageAnnotationsToServer(a);
        assert.equal(dispatchCount, 2);
        assert.ok(!state.dirtyImages.has(a.id));
    """,
    "folder_change_prevents_server_write_dispatch": r"""
        let dispatchCount = 0;
        context.annotationWorkflowController.saveImageAnnotationsToServer = async () => {
            dispatchCount++;
            return {path: 'a.csv'};
        };
        context.annotationDirectoryChangePending = true;
        await assert.rejects(context.saveImageAnnotationsToServer(a), /Wait for/);
        assert.equal(dispatchCount, 0);
        assert.equal(context.annotationSavePending, false);
        context.annotationDirectoryChangePending = false;
        await context.saveImageAnnotationsToServer(a);
        assert.equal(dispatchCount, 1);
    """,
    "pending_save_prevents_directory_change_dispatch": r"""
        const request = deferred();
        let directoryRequests = 0;
        context.annotationWorkflowController.saveImageAnnotationsToServer = () => request.promise;
        context.apiWorkflows.saveProjectSettings = () => {directoryRequests++;};
        const pending = context.saveImageAnnotationsToServer(a);
        await context.handleSetAnnotationDir();
        assert.equal(directoryRequests, 0);
        assert.equal(context.annotationDirectoryChangePending, false);
        request.resolve({path: 'a.csv'});
        await pending;
    """,
    "navigation_latest_selection_wins": r"""
        const first = deferred(), second = deferred();
        context.loadImageRecord = image => image === a ? first.promise : second.promise;
        const oldSelection = context.selectImageByIndex(0, {autoLoadAnnotations: false});
        const newSelection = context.selectImageByIndex(1, {autoLoadAnnotations: false});
        second.resolve(true);
        await newSelection;
        first.resolve(true);
        await oldSelection;
        assert.strictEqual(state.currentImage, b);
    """,
    "preprocess_rejects_decode_after_project_reset": r"""
        const decode = deferred();
        context.apiWorkflows.preprocessImage = async () => ({ok: true,
            json: async () => ({image: 'processed'})});
        context.loadImageElement = () => decode.promise;
        const pending = context.handleApplyPreprocess();
        await nextTurn();
        store.resetProjectState(state);
        decode.resolve({width: 30, height: 20});
        await pending;
        assert.equal(a.processedImage, undefined);
    """,
    "image_decode_rejects_replaced_session": r"""
        const decode = deferred();
        context.apiWorkflows.loadImage = async () => ({ok: true,
            json: async () => ({image_url: 'original', width: 30, height: 20})});
        context.loadImageElement = () => decode.promise;
        const pending = context.loadImageRecord(a);
        await nextTurn();
        store.resetProjectState(state);
        decode.resolve({width: 30, height: 20});
        assert.equal(await pending, false);
        assert.equal(a.originalImage, undefined);
    """,
    "older_completion_does_not_hide_active_loader": r"""
        const first = deferred(), second = deferred();
        const requests = [first, second];
        context.apiWorkflows.runSam = () => requests.shift().promise;
        const oldRun = context.handleRunSam();
        const newRun = context.handleRunSam();
        assert.equal(loaderState.hidden, false);
        first.resolve(samReply(1));
        await oldRun;
        assert.equal(loaderState.hidden, false);
        second.resolve(samReply(2));
        await newRun;
        assert.equal(loaderState.hidden, true);
    """,
}


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("script_name", ["script.js", "script-refined.js"])
def test_async_handler_races(scenario, script_name):
    node = shutil.which("node")
    if node is None:
        bundled = (
            Path.home() / ".cache/codex-runtimes/codex-primary-runtime"
            / "dependencies/node/bin/node.exe"
        )
        if bundled.exists():
            node = str(bundled)
    if node is None:
        pytest.skip("Node.js is not available to execute frontend handlers")
    harness = HARNESS.replace("'static/script.js'", f"'static/{script_name}'")
    script = harness + SCENARIOS[scenario] + r"""
}
main().catch(error => {console.error(error); process.exit(1);});
"""
    subprocess.run([node, "-e", script], cwd=REPO_ROOT, check=True)
