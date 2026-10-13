import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_completed_polygon_pointer_editing_and_failure_recovery():
    subprocess.run([_node_executable(), '-'], input=r"""
const assert = require('assert');
const fs = require('fs');
class Element {
    constructor() { this.attrs = {}; this.style = {}; this.children = []; this.value = ''; this.tagName = 'DIV'; }
    setAttribute(k, v) { this.attrs[k] = String(v); }
    getAttribute(k) { return this.attrs[k]; }
    hasAttribute(k) { return k in this.attrs; }
    removeAttribute(k) { delete this.attrs[k]; }
    appendChild(child) { this.children.push(child); }
    replaceChildren(...children) { this.children = children; }
    querySelectorAll() { return []; }
    querySelector(selector) { return this.children.find(child => child.getAttribute('data-proposal-id') === selector.match(/"(\d+)"/)[1]); }
    getBoundingClientRect() { return this.bounds || {left:300,top:200,bottom:230,width:250,height:180}; }
    focus() { this.focused = true; }
    click() { if (!this.disabled) return this.onclick(); }
}
const elements = new Map();
const el = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
const listeners = {};
global.document = { getElementById: el, createElementNS: () => new Element(), createElement: () => new Element(),
    querySelector: () => null, addEventListener: (name, fn) => listeners[name] = fn, removeEventListener() {} };
global.Option = function(text, value) { this.text = text; this.value = value; };
global.ResizeObserver = class { observe() {} disconnect() {} };
let discard = true, unload;
global.window = { innerWidth:1200, innerHeight:800, addEventListener(name, fn) { if(name === 'beforeunload') unload = fn; }, removeEventListener() {}, confirm: () => discard,
    SAM2FrontendConfig: { SCROLL_SENSITIVITY: 0.001, MAX_ZOOM: 10 } };
eval(fs.readFileSync('static/frontendConfig.js','utf8'));
eval(fs.readFileSync('static/fileUtils.js','utf8'));
eval(fs.readFileSync('static/canvasInteractionController.js','utf8'));
eval(fs.readFileSync('static/classManager-refined.js','utf8'));
window.SAM2ClassUiController={renderClassControls(refs,classes,preferred){
    refs.classificationSelect.replaceChildren(...classes.map(cls=>new Option(cls.name,cls.name)));
    refs.classificationSelect.value=preferred;
},getClassRowIndex:input=>input.rowIndex};

const gammaInput = {dataset:{param:'gamma'},value:'1.2',parentElement:{hidden:false},reportValidity:()=>true};
el('polygonPreprocessParams').querySelectorAll = selector => selector === 'input[data-param]' ? [gammaInput] : [];
let processHold = null, processFailure = false, badDimensions = false, processingCalls = [];
window.SAM2ApiWorkflows = { async preprocessImage(payload) {
    processingCalls.push(payload);
    if(processHold) await new Promise(resolve => processHold.resolve = resolve);
    return {ok:!processFailure,json:async()=>({image:'processed-preview',params:payload.params,error:'Processing failed'})};
} };
global.Image = class { set src(value) { this.naturalWidth = badDimensions ? 99 : 100; this.naturalHeight = 100; queueMicrotask(()=>this.onload()); } };
const svg = el('polygonCanvas');
svg.style = {};
let wheelHandler;
svg.parentElement = { style: {}, clientWidth: 200, clientHeight: 200, scrollLeft: 0, scrollTop: 0,
    addEventListener(name, handler, options) { assert.equal(name,'wheel'); assert.equal(options.passive,false); wheelHandler = handler; },
    removeEventListener() { wheelHandler = null; } };
const offset = () => (svg.style.transform?.match(/-?[\d.]+/g) || [0,0]).map(Number);
svg.getBoundingClientRect = () => ({ left: 100 + offset()[0] - svg.parentElement.scrollLeft, top: 50 + offset()[1] - svg.parentElement.scrollTop,
    width: parseFloat(svg.style.width), height: parseFloat(svg.style.width) });
// Two screen pixels per image pixel, with a translated/scrolled canvas.
svg.getScreenCTM = () => ({ a: 2, b: 0, inverse: () => ({}) });
svg.createSVGPoint = () => ({ x: 0, y: 0, matrixTransform() { return { x: (this.x - 100) / 2, y: (this.y - 50) / 2 }; } });
let captured;
svg.setPointerCapture = id => captured = id;
svg.hasPointerCapture = id => captured === id;
svg.releasePointerCapture = () => { captured = null; };
const original = { next_object_id: 2, image: { width: 100, height: 100 }, annotations: [
    { id: 1, class_id: 4, source: 'manual', edited: false, geometry: { type: 'polygon', points: [[10,10],[80,10],[80,80],[10,80]] } }
] };
let saved = structuredClone(original), reject = false, hold = null, validations = 0;
let saveHold = null, saveFailure = null, saves = 0, loads = 0, serverRevision = 'r1';
let importCalls = 0, importFailure = null, exportedPayload = null;
let classFailure=null,classPayload=null,mergeHold=null,mergeError=null;
let classRestorePayload=null,classRestoreMismatch=false;
window.SAM2ApiClient = { async apiFetch(path, options) {
    if (path === 'api/load_image') return { ok: true, json: async () => ({width:100,height:100,image_url:'data:image/png;base64,'}) };
    const data = JSON.parse(options.body);
    if(path==='api/classes'){
        classPayload=data.classes;classRestorePayload=data.restore_class_id;
        if(classFailure)return {ok:false,json:async()=>({error:classFailure})};
        const restored=data.classes.map((cls,i)=>({...cls,id:cls.id||Math.max(100,...data.classes.map(item=>item.id||0))+i+1}));
        return {ok:true,json:async()=>({classes:classRestoreMismatch?restored.filter(cls=>cls.id!==data.restore_class_id):restored})};
    }
    if (data.action === 'load') { loads++; return { ok: true, json: async () => ({document:structuredClone(saved),revision:serverRevision}) }; }
    if (data.action === 'import_labelme') {
        importCalls++;
        if (importFailure) return {ok:false,json:async()=>({error:importFailure})};
        const document={...structuredClone(saved),next_object_id:data.next_object_id+1,
            labelme:{flags:{reviewed:true}},annotations:[{id:data.next_object_id,class_id:9,source:'imported',edited:false,
            geometry:{type:'polygon',points:[[5,5],[25,5],[25,25],[5,25]]},labelme:{group_id:7}}]};
        return {ok:true,json:async()=>({document,classes:[{id:4,name:'Cell'},{id:8,name:'Other'},{id:9,name:'Imported'}]})};
    }
    if (data.action === 'export_labelme') {
        exportedPayload=data;
        return {ok:true,json:async()=>({labelme:{imagePath:'image.png',shapes:[]}})};
    }
    if (data.action === 'merge_preview') {
        if(mergeHold) await new Promise(resolve=>mergeHold.resolve=resolve);
        return {ok:!mergeError,json:async()=>({geometry:data.geometries[0],error:mergeError})};
    }
    if (data.action === 'validate') {
        validations++;
        if (hold) await new Promise(resolve => hold.resolve = resolve);
        if (reject) return { ok: false, json: async () => ({error:'Invalid outline'}) };
    }
    if (data.action === 'save') {
        saves++;
        assert.equal(data.revision,serverRevision);
        if (saveHold) await new Promise(resolve => saveHold.resolve = resolve);
        if (saveFailure) return {ok:false,json:async () => ({error:saveFailure})};
        saved = structuredClone(data.document); serverRevision = `r${saves+1}`;
    }
    return { ok:true, json:async () => ({document:data.document, revision:serverRevision}) };
} };
for (const module of ['state', 'geometry', 'persistence', 'viewport', 'localTools']) {
    eval(fs.readFileSync(`static/polygon/${module}.js`, 'utf8'));
}
eval(fs.readFileSync('static/polygonEditor.js', 'utf8'));
const editor = window.SAM2PolygonEditor.mount({classes:[{id:4,name:'Cell'},{id:8,name:'Other'}]});
const tick = () => new Promise(resolve => setImmediate(resolve));
const waitFor = async condition => {
    for(let attempt=0;attempt<100&&!condition();attempt++)await new Promise(resolve=>setTimeout(resolve,1));
    assert(condition());
};
const find = (attr, value) => el('polygonShapes').children.find(child => child.getAttribute(attr) === String(value));
const event = (target, x, y) => ({target,clientX:100+2*x,clientY:50+2*y,pointerId:7,button:0,preventDefault(){}});
const select = () => svg.onclick(event(find('data-object-id',1),40,40));
const begin = (index, x, y) => svg.onpointerdown(event(find('data-vertex-index',index),x,y));
const move = (x,y) => svg.onpointermove(event(svg,x,y));
const end = async (x,y) => { await svg.onpointerup(event(svg,x,y)); svg.onclick(event(svg,x,y)); };
const points = () => find('data-object-id',1).getAttribute('points');
(async () => {
    await el('polygonFiles').onchange({target:{files:[new Blob(['image'])],value:''}});
    // Selection has one action group; Delete is an autosaved, reversible edit.
    assert.equal(el('polygonModeState').textContent,'Select');assert(el('polygonSelectionActions').hidden);
    const beforeKeyboardDelete=structuredClone(saved),deleteSaves=saves;
    await listeners.keydown({key:'Delete',target:svg,preventDefault(){}});
    assert.equal(saves,deleteSaves);
    select();assert(!el('polygonSelectionActions').hidden);assert.equal(el('polygonModeState').textContent,'Object #1');
    assert.equal(el('polygonRelabel').textContent,'Cell');assert(!el('polygonCorrect').disabled);
    for(const target of [{tagName:'INPUT'},{tagName:'TEXTAREA'},{tagName:'SELECT'},{tagName:'DIV',isContentEditable:true}]) {
        await listeners.keydown({key:'Delete',target,preventDefault(){throw new Error('Typing must remain untouched');}});
    }
    await listeners.keydown({key:'Delete',ctrlKey:true,target:svg,preventDefault(){}});
    el('projectDialog').open=true;
    await listeners.keydown({key:'Delete',target:svg,preventDefault(){throw new Error('Dialog must keep keyboard focus');}});
    el('projectDialog').open=false;
    assert.equal(saves,deleteSaves);assert.deepEqual(saved,beforeKeyboardDelete);
    let deletePrevented=false;
    await listeners.keydown({key:'Delete',target:svg,preventDefault(){deletePrevented=true;}});
    assert(deletePrevented);assert.equal(saved.annotations.length,0);assert(el('polygonSelectionActions').hidden);
    await listeners.keydown({key:'z',ctrlKey:true,target:svg,preventDefault(){}});
    assert.deepEqual(saved,beforeKeyboardDelete);
    await listeners.keydown({key:'z',ctrlKey:true,shiftKey:true,target:svg,preventDefault(){}});
    assert.equal(saved.annotations.length,0);
    await el('polygonUndo').click();assert.deepEqual(saved,beforeKeyboardDelete);
    const afterKeyboardDeleteSaves=saves;
    assert(el('polygonStatus').hidden);assert.equal(el('polygonStatus').textContent,'');
    select();
    assert.equal(find('data-vertex-index',0).getAttribute('r'),'2.5');
    begin(0,10,10); move(15,20); move(20,25);
    assert(points().startsWith('20,25'));
    assert(el('polygonSave').disabled); assert(!editor.canLeave());
    await end(20,25);
    assert.equal(validations,1); assert(el('polygonSave').disabled); assert.equal(saves,afterKeyboardDeleteSaves+1);
    await el('polygonUndo').click(); assert(points().startsWith('10,10')); assert.equal(el('polygonSaveState').textContent,'Saved');
    await el('polygonRedo').click(); assert(points().startsWith('20,25'));
    select();
    // Closing edge insertion is projected onto the actual edge, including at zoom.
    await svg.onclick(event(find('data-edge-index',3),12,50));
    assert.equal(points().split(' ').length,5);
    assert.equal(saves,afterKeyboardDeleteSaves+4); // move, undo, redo and insertion autosaved without a Save click
    assert.equal(saved.annotations[0].geometry.points.length,5);
    assert.equal(saved.annotations[0].edited,true); assert.equal(saved.next_object_id,2);
    const before = points();
    const duplicateSaves=saves, duplicateValidations=validations;
    begin(0,20,25);await end(80,10);
    assert.equal(points(),before);assert.equal(saves,duplicateSaves);assert.equal(validations,duplicateValidations);
    assert.equal(find('data-invalid-points','1,2').getAttribute('stroke'),'#ff62cb');
    assert.equal(find('data-vertex-index',0).getAttribute('stroke'),'#ff62cb');
    assert(el('polygonStatus').textContent.includes('Object #1: points 1, 2 would overlap'));
    assert(el('polygonStatus').textContent.includes('The move was not saved'));

    begin(0,20,25); move(30,30);
    listeners.keydown({key:'Escape',target:svg,preventDefault(){}});
    svg.onclick(event(svg,30,30)); assert.equal(points(),before);
    begin(0,20,25); move(30,30); svg.onpointercancel({pointerId:7});
    svg.onclick(event(svg,30,30)); assert.equal(points(),before);
    reject = true; hold = {};
    begin(0,20,25); move(100,100);
    const pending = end(100,100); await tick();
    assert(el('polygonSave').disabled); assert(!editor.canLeave());
    hold.resolve(); await pending; hold = null;
    assert.equal(points(),before); assert.equal(el('polygonSaveState').textContent,'Saved');
    assert.equal(el('polygonStatus').textContent,'Invalid outline');
    assert.equal(el('polygonStatus').hidden,false);
    // Rejected edit did not add a history step: undo removes the inserted vertex.
    await el('polygonUndo').click(); assert.equal(points().split(' ').length,4);
    reject = false; select();
    begin(0,20,25); await end(-20,-30);
    assert(points().startsWith('0,0')); // out-of-canvas drag clamps to image bounds
    const count = validations;
    begin(0,0,0); await end(0,0); assert.equal(validations,count); // no-op
    // Vertex deletion validates, autosaves, and supports undo/redo.
    const beforeRemoval=points();
    const removeEvent={preventDefault(){},stopPropagation(){}};
    await find('data-vertex-index',1).oncontextmenu(removeEvent);
    assert.equal(saved.annotations[0].geometry.points.length,3);
    const triangleValidations=validations, triangleSaves=saves;
    await find('data-vertex-index',0).onkeydown({...removeEvent,key:'Delete'});
    assert.equal(validations,triangleValidations);assert.equal(saves,triangleSaves);
    await el('polygonUndo').click();assert.equal(points(),beforeRemoval);
    await el('polygonRedo').click();assert.equal(points().split(' ').length,3);
    await el('polygonUndo').click();select();
    reject=true;
    await find('data-vertex-index',1).oncontextmenu(removeEvent);
    assert.equal(points(),beforeRemoval);reject=false;
    await find('data-vertex-index',1).onkeydown({...removeEvent,key:'Backspace'});
    assert.equal(points().split(' ').length,3);
    await el('polygonUndo').click();select();
    const geometry = points();
    let prevented = false;
    wheelHandler({clientX:200,clientY:150,deltaY:-100,deltaMode:0,preventDefault(){prevented=true;}});
    assert(prevented); assert.equal(el('polygonZoomLabel').textContent,'110%');
    assert(Math.abs(offset()[0] + 10) < 1e-9);
    assert(Math.abs(offset()[1] + 10) < 1e-9);
    assert.equal(points(),geometry); // view-only change
    wheelHandler({clientX:200,clientY:150,deltaY:-10000,deltaMode:0,preventDefault(){}});
    assert.equal(el('polygonZoomLabel').textContent,'1000%');
    el('polygonFit').click(); assert.equal(svg.parentElement.scrollLeft,0);
    assert.equal(svg.parentElement.scrollTop,0); assert.equal(el('polygonZoomLabel').textContent,'100%');
    wheelHandler({clientX:200,clientY:150,deltaY:100,deltaMode:1,preventDefault(){}});
    assert.equal(el('polygonZoomLabel').textContent,'100%');
    // Background pan reuses detection's controller and never changes annotations.
    const stage=svg.parentElement, beforePanSaves=saves;
    stage.onpointerdown(event(svg,10,10));assert.equal(stage.style.cursor,'grabbing');assert(!editor.canLeave());
    stage.onpointermove(event(svg,30,40));stage.onpointerup(event(svg,30,40));
    assert.deepEqual(offset(),[40,60]);assert.equal(stage.style.cursor,'grab');
    svg.onclick(event(svg,30,40));assert.equal(points(),geometry);assert.equal(saves,beforePanSaves);
    // Zoom stays anchored under the pointer even after panning.
    const beforeZoom=svg.getBoundingClientRect();
    const anchorX=(200-beforeZoom.left)/beforeZoom.width,anchorY=(150-beforeZoom.top)/beforeZoom.height;
    wheelHandler({clientX:200,clientY:150,deltaY:-100,deltaMode:0,preventDefault(){}});
    const afterZoom=svg.getBoundingClientRect();
    assert(Math.abs(afterZoom.left+anchorX*afterZoom.width-200)<1e-9);
    assert(Math.abs(afterZoom.top+anchorY*afterZoom.height-150)<1e-9);
    el('polygonFit').click();assert.deepEqual(offset(),[0,0]);
    stage.onpointerdown(event(svg,10,10));stage.onpointermove(event(svg,30,30));
    stage.onpointercancel({pointerId:7});assert.deepEqual(offset(),[0,0]);
    stage.onpointerdown(event(svg,10,10));stage.onpointermove(event(svg,30,30));
    listeners.keydown({key:'Escape',target:svg,preventDefault(){}});assert.deepEqual(offset(),[0,0]);
    stage.onpointerdown(event(find('data-object-id',1),20,20));assert.equal(stage.style.cursor,'grab');
    assert.equal(saves,beforePanSaves);
    // Drafts and view changes never write; completing a polygon does.
    const priorSaves = saves;
    el('polygonClass').value = '4';
    assert(el('polygonFinish').hidden);assert(el('polygonCancel').hidden);
    listeners.keydown({key:'1',target:svg,preventDefault(){}});
    assert(el('polygonUndo').disabled);
    assert(!el('polygonFinish').hidden);assert(!el('polygonCancel').hidden);
    svg.onpointerdown(event(svg,10,10));stage.onpointerdown(event(svg,10,10));assert.equal(stage.style.cursor,'crosshair');
    assert.deepEqual(offset(),[0,0]);
    svg.onclick(event(svg,30,30)); svg.onclick(event(svg,50,30)); svg.onclick(event(svg,40,50));
    assert(!el('polygonUndo').disabled);
    await el('polygonUndo').click();assert(el('polygonFinish').disabled);
    listeners.keydown({key:'z',ctrlKey:true,target:svg,preventDefault(){}});
    listeners.keydown({key:'z',ctrlKey:true,target:svg,preventDefault(){}});
    assert(el('polygonUndo').disabled);assert.deepEqual(points(),geometry);
    assert.equal(saves,priorSaves);
    // Empty draft undo must not reach completed annotation history.
    listeners.keydown({key:'z',ctrlKey:true,target:svg,preventDefault(){}});
    assert.deepEqual(points(),geometry);
    svg.onclick(event(svg,30,30));svg.onclick(event(svg,50,30));svg.onclick(event(svg,40,50));
    assert.equal(saves,priorSaves); assert.equal(el('polygonSaveState').textContent,'Draft not saved');
    saveHold = {};
    const finishing = el('polygonFinish').click(); await tick();
    assert.equal(el('polygonSaveState').textContent,'Saving…');
    assert(el('polygonDraw').disabled); assert(!editor.canLeave());
    let warned = false; unload({preventDefault(){warned=true;}}); assert(warned);
    const oldLoads = loads;
    await el('polygonFiles').onchange({target:{files:[new Blob(['other'])],value:''}});
    assert.equal(loads,oldLoads); // no image switch during outstanding save
    saveHold.resolve(); await finishing; saveHold = null;
    assert.equal(saved.annotations.length,2); assert.equal(el('polygonSaveState').textContent,'Saved');
    assert(editor.canLeave());
    // Failed saves keep geometry/history and block navigation when discard is declined.
    const disk = structuredClone(saved);
    saveFailure = 'Disk unavailable';
    await el('polygonDelete').click();
    assert.deepEqual(saved,disk); assert.equal(el('polygonObjectList').children.length,1);
    assert.equal(el('polygonSaveState').textContent,'Save failed — unsaved changes');
    assert.equal(el('polygonSave').textContent,'Retry save'); assert(!el('polygonSave').disabled);
    discard = false; assert(!editor.canLeave());
    await el('polygonFiles').onchange({target:{files:[new Blob(['other'])],value:''}});
    assert.equal(loads,oldLoads);
    // Revision conflict is not overwritten or retried in a loop.
    saveFailure = 'Annotations changed elsewhere';
    await el('polygonSave').click(); assert(el('polygonStatus').textContent.includes(saveFailure));
    const attempts = saves; await tick(); assert.equal(saves,attempts);
    saveFailure = null; await el('polygonSave').click();
    assert.equal(saved.annotations.length,1); assert.equal(el('polygonSaveState').textContent,'Saved');
    await el('polygonUndo').click(); assert.equal(saved.annotations.length,2);
    await el('polygonRedo').click(); assert.equal(saved.annotations.length,1);
    select(); await el('polygonRelabel').click(); await el('polygonLabelChoices').children[1].click();
    assert.equal(saved.annotations[0].class_id,8);
    await el('polygonFiles').onchange({target:{files:[new Blob(['image'])],value:''}});
    assert.equal(loads,oldLoads+1); assert.equal(el('polygonSaveState').textContent,'Saved');
    const originalHref = el('polygonImage').getAttribute('href');
    const originalGeometry = points(), originalSaves = saves;
    const originalWidth = svg.style.width;
    el('polygonPreprocessMethod').value = 'gamma'; gammaInput.value = '2';
    processHold = {};
    const applying = el('polygonPreprocessApply').click(); await tick();
    assert(!editor.canLeave()); assert(el('polygonDraw').disabled);
    assert.equal(el('polygonImage').getAttribute('href'),originalHref);
    processHold.resolve(); await applying; processHold = null;
    assert.equal(el('polygonImage').getAttribute('href'),'processed-preview');
    assert.equal(el('polygonPreprocessActive').textContent,'Active: Gamma');
    assert.equal(processingCalls[0].params.gamma,2);
    await el('polygonPreprocessApply').click();
    assert.strictEqual(processingCalls[0].file,processingCalls[1].file); // original file every time
    assert.equal(points(),originalGeometry); assert.equal(saves,originalSaves); assert.equal(svg.style.width,originalWidth);
    processFailure = true; el('polygonPreprocessMethod').value = 'clahe';
    await el('polygonPreprocessApply').click();
    assert.equal(el('polygonPreprocessActive').textContent,'Active: Gamma');
    assert.equal(el('polygonImage').getAttribute('href'),'processed-preview');
    processFailure = false; badDimensions = true; await el('polygonPreprocessApply').click();
    assert(el('polygonStatus').textContent.includes('dimensions')); badDimensions = false;
    el('polygonPreprocessRestore').click(); assert.equal(el('polygonImage').getAttribute('href'),originalHref);
    assert.equal(points(),originalGeometry); assert.equal(saves,originalSaves);
    el('polygonPreprocessMethod').value = 'gamma'; await el('polygonPreprocessApply').click();
    await el('polygonFiles').onchange({target:{files:[new Blob(['next image'])],value:''}});
    assert.equal(el('polygonPreprocessActive').textContent,'Original image');
    assert.equal(el('polygonPreprocessMethod').value,'original');
    // Labelme import replaces in one undoable step, preserves metadata, and
    // failed parsing/validation leaves current annotations and saved data intact.
    const importFile=raw=>el('polygonLabelmeFile').onchange({target:{files:[new Blob([raw])],value:'file'}});
    const beforeImport=structuredClone(saved);
    discard=true;
    await importFile('{broken');assert.equal(importCalls,0);assert.deepEqual(saved,beforeImport);
    importFailure='Unsupported Labelme shapes: circle';await importFile('{}');
    assert.deepEqual(saved,beforeImport);assert.equal(el('polygonStatus').textContent,importFailure);
    importFailure=null;discard=false;await importFile('{}');assert.equal(importCalls,1);
    discard=true;await importFile('{}');
    assert.equal(saved.annotations.length,1);assert.equal(saved.annotations[0].class_id,9);
    assert.equal(saved.annotations[0].labelme.group_id,7);assert(saved.labelme.flags.reviewed);
    await el('polygonUndo').click();assert.deepEqual(saved.annotations,beforeImport.annotations);assert(!saved.labelme);
    await el('polygonRedo').click();assert(saved.labelme.flags.reviewed);
    let downloadedName=null;
    const oldCreate=document.createElement;
    document.createElement=tag=>{const node=new Element();if(tag==='a'){node.click=()=>{downloadedName=node.download;};node.remove=()=>{};}return node;};
    document.body={appendChild(){}};
    await el('polygonExportLabelme').click();assert.equal(downloadedName,'image.json');
    assert.deepEqual(exportedPayload.document,saved);
    document.createElement=oldCreate;
    await el('polygonUndo').click();
    saveFailure='Disk unavailable';await importFile('{}');
    assert.equal(el('polygonSaveState').textContent,'Save failed — unsaved changes');
    assert(!el('polygonSave').disabled);
    saveFailure=null;await el('polygonUndo').click();assert.deepEqual(saved.annotations,beforeImport.annotations);
    // Real API contract: pending proposals are never saved, acceptance is one
    // history step, and a failed autosave cannot duplicate accepted objects.
    const proposal = (id, size) => ({id,area:size*size,bbox:[10,10,size,size],geometry:{type:'polygon',points:[[10,10],[10+size,10],[10+size,10+size],[10,10+size]]}});
    let samResults = [proposal(1,20),proposal(2,30),proposal(3,60)];
    let samCalls = [], samHold = null, samError = null, samMismatch = false;
    window.SAM2ApiWorkflows.runSam = async payload => {
        samCalls.push(payload);
        if (samHold) await new Promise(resolve => samHold.resolve = resolve);
        return {ok:!samError,json:async()=>({error:samError,image:{...saved.image,width:samMismatch?99:100},proposals:samResults,skipped:1})};
    };
    el('polygonSamPreset').value='fast_preview';
    el('polygonPreprocessMethod').value='gamma'; gammaInput.value='2';
    await el('polygonPreprocessApply').click();
    gammaInput.value='3'; // unapplied controls must NOT change inference input
    const beforeSamSaves=saves;
    samHold={}; const pendingSam=el('polygonSamRun').click(); await tick();
    assert(el('polygonSamAccept').disabled); assert(!editor.canLeave());
    samHold.resolve(); await pendingSam; samHold=null;
    assert.equal(samCalls[0].preprocessParams.gamma,2);assert.equal(samCalls[0].imageName,'image.png');
    assert.equal(samCalls[0].preprocessMethod,'gamma'); assert.equal(samCalls[0].output,'polygons');
    assert.equal(saves,beforeSamSaves); assert.equal(el('polygonSamInfo').textContent,'3 suggestions');assert(el('polygonSamDetails').textContent.includes('1 masks skipped'));
    await el('polygonUndo').click();assert.equal(el('polygonProposals').children.length,0);
    await el('polygonRedo').click();assert.equal(el('polygonProposals').children.length,3);
    assert.equal(samCalls.length,1);assert.equal(saves,beforeSamSaves);
    samResults=[proposal(99,25)];await el('polygonSamRun').click();
    assert.equal(el('polygonProposals').children.length,1);
    await el('polygonUndo').click();assert.equal(el('polygonProposals').children.length,3);
    await el('polygonRedo').click();assert.equal(el('polygonProposals').children.length,1);
    assert.equal(samCalls.length,2);assert.equal(saves,beforeSamSaves);
    await el('polygonUndo').click();
    samResults=[proposal(1,20),proposal(2,30),proposal(3,60)];
    assert(!el('polygonSamReview').hidden);assert(el('polygonSamAccept').hidden);
    const pick=id=>el('polygonProposalBadges').children.find(row=>row.getAttribute('data-proposal-id')===String(id)).onclick({stopPropagation(){}});
    const badge=id=>el('polygonProposalBadges').children.find(row=>row.getAttribute('data-proposal-id')===String(id));
    const beforeViewSaves=saves;
    assert.equal(svg.getAttribute('data-outlineonly'),'true');
    el('polygonShowObjects').checked=false;el('polygonShowObjects').onchange();
    assert.equal(svg.getAttribute('data-showobjects'),'false');
    const overlapEvent={...event(svg,20,20),altKey:true};
    svg.onpointerdown(overlapEvent);assert(!captured);
    svg.onclick(overlapEvent);svg.onclick(overlapEvent);svg.onclick(overlapEvent);
    assert.equal(el('polygonSamAccept').textContent,'Accept 3 selected');assert(!el('polygonSamReview').hidden);
    svg.onclick(overlapEvent);assert.equal(el('polygonSamAccept').textContent,'Accept 2 selected');
    el('polygonShowSuggestions').checked=false;el('polygonShowSuggestions').onchange();
    assert(el('polygonSamReview').hidden);assert(el('polygonSamAccept').disabled);
    assert.equal(el('polygonProposals').children.length,3); // hidden, never deleted
    el('polygonShowSuggestions').checked=true;el('polygonShowSuggestions').onchange();
    el('polygonShowObjects').checked=true;el('polygonShowObjects').onchange();
    el('polygonShowNumbers').checked=false;el('polygonShowNumbers').onchange();
    assert.equal(svg.getAttribute('data-shownumbers'),'false');
    el('polygonOutlineOnly').checked=false;el('polygonOutlineOnly').onchange();
    assert.equal(svg.getAttribute('data-outlineonly'),'false');
    el('polygonShowNumbers').checked=true;el('polygonShowNumbers').onchange();
    el('polygonOutlineOnly').checked=true;el('polygonOutlineOnly').onchange();
    assert.equal(saves,beforeViewSaves);
    badge(1).onkeydown({key:'Enter',preventDefault(){},stopPropagation(){}});
    assert.equal(badge(1).getAttribute('aria-pressed'),'true');assert(badge(1).focused);
    badge(1).onkeydown({key:' ',preventDefault(){},stopPropagation(){}});
    assert.equal(badge(1).getAttribute('aria-pressed'),'false');
    pick(1);pick(2);assert.equal(el('polygonSamAccept').textContent,'Accept 2 selected');
    pick(2);assert.equal(el('polygonSamAccept').textContent,'Accept 1 selected');pick(2);
    reject=true; await el('polygonSamAccept').click(); reject=false;
    assert.equal(el('polygonProposals').children.length,3);assert.equal(saves,beforeSamSaves);
    el('polygonClass').value='4';
    el('polygonSamClass').value='8';el('polygonSamClass').onchange();
    assert.equal(el('polygonClass').value,'8');
    el('polygonSamClass').value='4';el('polygonSamClass').onchange();
    assert.equal(el('polygonClass').value,'4');
    const beforeBatch=saved.annotations.length;
    saveFailure='Disk unavailable';await el('polygonSamAccept').click();
    assert.equal(saved.annotations.length,beforeBatch); assert.equal(el('polygonProposals').children.length,1);
    assert(el('polygonSamAccept').disabled);assert.equal(el('polygonSaveState').textContent,'Save failed — unsaved changes');
    saveFailure=null;await el('polygonSave').click();
    assert.equal(saved.annotations.length,beforeBatch+2);assert(saved.annotations.slice(-2).every(o=>o.source==='sam2'));
    // Clearing pending masks preserves accepted objects, is reversible, and never reruns inference.
    const acceptedBeforeClear=structuredClone(saved.annotations), callsBeforeClear=samCalls.length, savesBeforeClear=saves;
    assert(!el('polygonSamClearSuggestions').disabled);
    el('polygonSamClearSuggestions').click();
    assert.equal(el('polygonProposals').children.length,0);assert(el('polygonSamClearSuggestions').disabled);
    assert.equal(el('polygonSamInfo').textContent,'');assert(el('polygonSamReview').hidden);
    assert.deepEqual(saved.annotations,acceptedBeforeClear);assert.equal(saves,savesBeforeClear);
    await el('polygonUndo').click();assert.equal(el('polygonProposals').children.length,1);
    assert.deepEqual(saved.annotations,acceptedBeforeClear);assert(!el('polygonSamClearSuggestions').disabled);
    await el('polygonRedo').click();assert.equal(el('polygonProposals').children.length,0);
    await el('polygonUndo').click();assert.equal(el('polygonProposals').children.length,1);
    assert.equal(samCalls.length,callsBeforeClear);
    await el('polygonUndo').click();assert.equal(saved.annotations.length,beforeBatch);assert.equal(el('polygonProposals').children.length,3);
    await el('polygonRedo').click();assert.equal(saved.annotations.length,beforeBatch+2);assert.equal(el('polygonProposals').children.length,1);
    await el('polygonUndo').click();pick(1);pick(2);
    const beforeReject=saves;el('polygonSamReject').click();assert.equal(saves,beforeReject);assert.equal(el('polygonProposals').children.length,1);
    await el('polygonUndo').click();assert.equal(el('polygonProposals').children.length,3);
    samError='Model unavailable';await el('polygonSamRun').click();assert.equal(el('polygonProposals').children.length,3);assert.equal(el('polygonStatus').textContent,samError);
    samError=null;samMismatch=true;await el('polygonSamRun').click();assert(el('polygonStatus').textContent.includes('do not match'));samMismatch=false;
    pick(1);listeners.keydown({key:'Escape',target:svg});assert(el('polygonSamAccept').disabled);
    await el('polygonFiles').onchange({target:{files:[new Blob(['new'])],value:''}});assert.equal(el('polygonProposals').children.length,0);

    // Folder opening: sorted recursive queue, lazy sidecars, existing saves win.
    const folderFile=(name,path,contents='image')=>Object.assign(new Blob([contents]),{name,webkitRelativePath:path});
    const first=folderFile('cell2.TIFF','study/a/cell2.TIFF');
    const second=folderFile('cell10.png','study/b/cell10.png');
    const sidecar=folderFile('cell2.json','study/a/cell2.json','{}');
    const openFolder=files=>el('polygonFolder').onchange({target:{files,value:''}});
    const beforeFolderImports=importCalls;
    saved={...structuredClone(original),annotations:[]};serverRevision=null;
    await openFolder([second,sidecar,first,folderFile('notes.txt','study/notes.txt')]);
    assert.equal(importCalls,beforeFolderImports+1);assert.equal(saved.annotations.length,1);
    assert.equal(el('polygonPosition').textContent,'1 / 2');assert(el('polygonPrevious').disabled);
    assert.equal(el('polygonImageList').children.length,2);assert(!el('polygonNext').disabled);
    await el('polygonNext').click();assert.equal(el('polygonPosition').textContent,'2 / 2');assert(el('polygonNext').disabled);
    await el('polygonPrevious').click();assert.equal(importCalls,beforeFolderImports+1);
    // Even deliberately empty saved annotations must not be replaced.
    saved.annotations=[];await openFolder([first,sidecar]);assert.equal(importCalls,beforeFolderImports+1);
    const beforeEmptyFolderLoads=loads;
    await openFolder([sidecar]);assert.equal(loads,beforeEmptyFolderLoads);assert(el('polygonStatus').textContent.includes('No supported images'));
    await openFolder([]);assert.equal(loads,beforeEmptyFolderLoads);
    // A bad sidecar leaves the image accessible, without creating or saving annotations.
    serverRevision=null;const beforeBadSave=saves;
    await openFolder([first,folderFile('cell2.json','study/a/cell2.json','{broken')]);
    assert.equal(saves,beforeBadSave);assert.equal(saved.annotations.length,0);assert.equal(el('polygonPosition').textContent,'1 / 1');
    importFailure='Unsupported shape type';await openFolder([first,sidecar]);importFailure=null;
    assert.equal(saves,beforeBadSave);assert(el('polygonStatus').textContent.includes('Unsupported shape'));
    await openFolder([first,sidecar,folderFile('cell2.png','study/a/cell2.png')]);
    assert(el('polygonStatus').textContent.includes('Multiple files'));assert.equal(saves,beforeBadSave);
    // Failed autosave remains recoverable and blocks navigation unless discarded.
    saveFailure='Disk unavailable';await openFolder([first,sidecar,second]);discard=false;
    const failedFolderLoads=loads;await el('polygonNext').click();assert.equal(loads,failedFolderLoads);
    assert.equal(el('polygonPosition').textContent,'1 / 2');assert(!editor.canLeave());
    saveFailure=null;discard=true;await el('polygonSave').click();assert(editor.canLeave());
    // Shared class UI changes persist through the API without changing polygon IDs.
    el('polygonClassForm').hidden=true;
    el('polygonAddClass').click();assert(!el('polygonClassForm').hidden);
    el('polygonClassName').value=' New   type ';
    await el('polygonClassForm').onsubmit({preventDefault(){}});
    assert(el('polygonClassForm').hidden);assert.equal(classPayload.at(-1).name,'New type');
    const newId=el('polygonClass').value;
    const classInput=(field,value,rowIndex)=>({value,rowIndex,classList:{contains:name=>name===field}});
    const editClass=(field,value,rowIndex)=>el('polygonClassManager').onchange({target:classInput(field,value,rowIndex)});
    const originalIds=saved.annotations.map(item=>item.class_id);
    await editClass('class-name-input','Renamed type',classPayload.length-1);
    assert.equal(el('polygonClass').value,newId);assert.equal(classPayload.at(-1).name,'Renamed type');
    await editClass('class-color-input','#123456',classPayload.length-1);
    assert.equal(classPayload.at(-1).color,'#123456');
    await editClass('class-hotkey-input','Q',classPayload.length-1);
    el('polygonClass').value='4';listeners.keydown({key:'q',target:svg,preventDefault(){}});
    assert.equal(el('polygonClass').value,newId);
    const failedInput=classInput('class-name-input','Unsaved rename',classPayload.length-1);
    classFailure='Class save failed';await el('polygonClassManager').onchange({target:failedInput});classFailure=null;
    assert.equal(failedInput.value,'Renamed type');assert(el('polygonStatus').textContent.includes('Class save failed'));
    assert.deepEqual(saved.annotations.map(item=>item.class_id),originalIds);
    for (const key of ['1','2','3']) {
        const input={rowIndex:0,value:key,classList:{contains:name=>name==='class-hotkey-input'}};
        const before=structuredClone(classPayload);
        await el('polygonClassManager').onchange({target:input});
        assert.deepEqual(classPayload,before);assert(el('polygonStatus').textContent.includes('reserved'));
    }
    // Class deletion counts this image only, confirms, autosaves, and shares Undo.
    await editClass('class-color-input','#123456',classPayload.length-1);
    const beforeClassDelete=structuredClone(saved),beforeClasses=structuredClone(classPayload);
    const deletionId=beforeClassDelete.annotations[0].class_id;
    const deletionIndex=beforeClasses.findIndex(cls=>cls.id===deletionId);
    const deleteClick={target:{closest:selector=>selector==='.class-delete-btn'?{rowIndex:deletionIndex}:null}};
    discard=false;await el('polygonClassManager').onclick(deleteClick);discard=true;
    assert.deepEqual(saved,beforeClassDelete);assert.deepEqual(classPayload,beforeClasses);
    classFailure='Classes unavailable';await el('polygonClassManager').onclick(deleteClick);classFailure=null;
    assert.deepEqual(saved,beforeClassDelete);assert(el('polygonStatus').textContent.includes('Classes unavailable'));
    await el('polygonClassManager').onclick(deleteClick);
    assert(!classPayload.some(cls=>cls.id===deletionId));assert(!saved.annotations.some(item=>item.class_id===deletionId));
    assert.deepEqual(saved.annotations,beforeClassDelete.annotations.filter(item=>item.class_id!==deletionId));
    const afterClassDelete=structuredClone(saved);
    classFailure='Classes unavailable';await el('polygonUndo').click();classFailure=null;
    assert.deepEqual(saved,afterClassDelete);assert(el('polygonStatus').textContent.includes('Classes unavailable'));
    await el('polygonUndo').click();assert.deepEqual(saved,beforeClassDelete);assert.deepEqual(classPayload,beforeClasses);
    await el('polygonRedo').click();assert(!classPayload.some(cls=>cls.id===deletionId));assert(!saved.annotations.some(item=>item.class_id===deletionId));
    await el('polygonUndo').click();assert.deepEqual(saved,beforeClassDelete);
    // A failed disk save leaves edits recoverable through Undo and keeps classes consistent.
    saveFailure='Disk unavailable';await el('polygonClassManager').onclick(deleteClick);saveFailure=null;
    assert(el('polygonStatus').textContent.includes('Save failed'));
    await el('polygonUndo').click();assert.deepEqual(saved,beforeClassDelete);assert.deepEqual(classPayload,beforeClasses);
    // Undoing a deletion must keep classes created afterward.
    await el('polygonClassManager').onclick(deleteClick);
    el('polygonClassName').value='Later class';
    await el('polygonClassForm').onsubmit({preventDefault(){}});
    await el('polygonUndo').click();assert.deepEqual(saved,beforeClassDelete);
    assert(classPayload.some(cls=>cls.name==='Later class'));assert(classPayload.some(cls=>cls.id===deletionId));
    await el('polygonRedo').click();assert(classPayload.some(cls=>cls.name==='Later class'));
    assert(!classPayload.some(cls=>cls.id===deletionId));
    await el('polygonUndo').click();assert.deepEqual(saved,beforeClassDelete);
    // Undo of class deletion must reject a reused name without touching data/history.
    await el('polygonClassManager').onclick(deleteClick);
    const beforeConflictUndo=structuredClone(saved);
    const originalDeletedClass=beforeClasses.find(cls=>cls.id===deletionId);
    const conflictIndex=classPayload.findIndex(cls=>cls.id!==deletionId);
    const conflictingClass=structuredClone(classPayload[conflictIndex]);
    await editClass('class-name-input',originalDeletedClass.name,conflictIndex);
    const conflictedClasses=structuredClone(classPayload),beforeConflictSaves=saves;
    assert(!el('polygonUndo').disabled);assert(el('polygonRedo').disabled);
    // Renames now have their own chronological Undo step before the earlier deletion.
    await el('polygonUndo').click();
    assert.deepEqual(saved,beforeConflictUndo);
    assert.equal(classPayload.find(cls=>cls.id===conflictingClass.id).name,conflictingClass.name);
    assert.notDeepEqual(classPayload,conflictedClasses);
    assert.equal(saves,beforeConflictSaves+1);assert.equal(el('polygonSaveState').textContent,'Saved');
    assert(!el('polygonUndo').disabled);assert(!el('polygonRedo').disabled);
    classRestoreMismatch=true;await el('polygonUndo').click();classRestoreMismatch=false;
    assert.equal(classRestorePayload,deletionId);assert.deepEqual(saved,beforeConflictUndo);
    assert.equal(saves,beforeConflictSaves+1);assert(el('polygonStatus').textContent.includes('original class ID'));
    assert(!el('polygonClass').children.some(option=>String(option.value)===String(deletionId)));
    assert(!el('polygonUndo').disabled);assert(!el('polygonRedo').disabled);
    await el('polygonUndo').click();assert.deepEqual(saved,beforeClassDelete);
    assert.equal(classRestorePayload,deletionId);
    assert(classPayload.some(cls=>cls.id===deletionId));
    await el('polygonRedo').click();assert.deepEqual(saved,beforeConflictUndo);
    assert.equal(classRestorePayload,undefined);
    await el('polygonUndo').click();assert.deepEqual(saved,beforeClassDelete);
    // Native rectangle/circle tools complete after two clicks and retain editable handles.
    for (const [key, kind] of [['2','rectangle'],['3','circle']]) {
        const countBefore=saved.annotations.length;
        listeners.keydown({key,target:svg,preventDefault(){}});
        await svg.onclick(event(svg,40,40));
        svg.onpointermove(event(svg,50,50));
        await svg.onclick(event(svg,50,50));
        assert.equal(saved.annotations.length,countBefore+1);
        assert.equal(saved.annotations.at(-1).geometry.type,kind);
        assert.deepEqual(saved.annotations.at(-1).geometry.points,[[40,40],[50,50]]);
        begin(1,50,50);await end(55,55);
        assert.equal(saved.annotations.at(-1).geometry.type,kind);
        assert.deepEqual(saved.annotations.at(-1).geometry.points,[[40,40],[55,55]]);
        await el('polygonUndo').click();assert.deepEqual(saved.annotations.at(-1).geometry.points,[[40,40],[50,50]]);
        await el('polygonUndo').click();assert.equal(saved.annotations.length,countBefore);
        await el('polygonRedo').click();assert.equal(saved.annotations.at(-1).geometry.type,kind);
        const moving=saved.annotations.at(-1), initial=structuredClone(moving.geometry.points), beforeMoveSaves=saves;
        const target=find('data-object-id',moving.id);
        // Redo clears selection; select first, then drag the interior.
        svg.onclick(event(target,45,45));
        svg.onpointerdown(event(find('data-object-id',moving.id),45,45));
        move(50,52);await end(50,52);
        assert.deepEqual(saved.annotations.at(-1).geometry.points,initial.map(p=>[p[0]+5,p[1]+7]));
        assert.equal(saves,beforeMoveSaves+1);
        await el('polygonUndo').click();assert.deepEqual(saved.annotations.at(-1).geometry.points,initial);
        svg.onclick(event(find('data-object-id',moving.id),45,45));
        svg.onpointerdown(event(find('data-object-id',moving.id),45,45));move(70,70);
        listeners.keydown({key:'Escape',target:svg,preventDefault(){}});
        svg.onclick(event(svg,70,70));assert.deepEqual(saved.annotations.at(-1).geometry.points,initial);

    }
    const beforeLabel=structuredClone(saved.annotations);
    const labelRow=el('polygonObjectList').children.at(-1);
    labelRow.oncontextmenu({preventDefault(){}});
    assert.equal(el('polygonLabelPicker').hidden,false);
    assert.equal(el('polygonLabelPicker').style.left,'300px');
    assert.equal(el('polygonLabelPicker').style.top,'238px');
    el('polygonLabelClose').click();
    labelRow.children[1].bounds={left:1150,top:750,bottom:780,width:30,height:30};
    labelRow.oncontextmenu({preventDefault(){}});
    assert.equal(el('polygonLabelPicker').style.left,'942px');
    assert.equal(el('polygonLabelPicker').style.top,'562px');
    await el('polygonLabelChoices').children[0].click();
    assert.equal(el('polygonLabelPicker').hidden,true);
    assert.equal(saved.annotations.at(-1).class_id,4);
    await el('polygonUndo').click();assert.deepEqual(saved.annotations,beforeLabel);
    // Click-assisted preview is temporary; accept/new/correct each forms one edit.
    svg.onclick(event(svg,95,95));
    let beforePromptSaves=saves, beforePromptCount=saved.annotations.length;
    el('polygonPromptStart').click();assert(!el('polygonPromptBar').hidden);
    assert(el('polygonSamRun').disabled);assert(el('polygonPreprocessApply').disabled);
    await svg.onclick(event(svg,20,20));assert(!el('polygonPromptAccept').disabled);
    assert.deepEqual(samCalls.at(-1).points,[[20,20,1]]);assert.equal(saves,beforePromptSaves);
    await svg.oncontextmenu(event(svg,40,40));assert.deepEqual(samCalls.at(-1).points,[[20,20,1],[40,40,0]]);
    await el('polygonPromptUndo').click();assert.deepEqual(samCalls.at(-1).points,[[20,20,1]]);
    samError='Prediction failed';await svg.onclick(event(svg,21,21));assert(el('polygonPromptAccept').disabled);
    samError=null;await el('polygonPromptUndo').click();assert(!el('polygonPromptAccept').disabled);
    await el('polygonPromptAccept').click();assert.equal(saved.annotations.length,beforePromptCount+1);
    assert.equal(saves,beforePromptSaves+1);assert(el('polygonPromptBar').hidden);
    const addedId=saved.annotations.at(-1).id;
    await el('polygonUndo').click();assert.equal(saved.annotations.length,beforePromptCount);
    await el('polygonRedo').click();assert.equal(saved.annotations.length,beforePromptCount+1);
    svg.onclick(event(find('data-object-id',addedId),20,20));
    el('polygonCorrect').click();assert.equal(el('polygonPromptAccept').textContent,'Apply correction');
    await listeners.keydown({key:'Delete',target:svg,preventDefault(){}});
    assert.equal(saved.annotations.length,beforePromptCount+1);
    assert.equal(el('polygonModeState').textContent,`Correct #${addedId}`);
    assert(el('polygonPromptLayer').children.some(node=>node.getAttribute('class')==='prompt-original'));
    await svg.onclick(event(svg,22,22));
    const compareSaves=saves;
    el('polygonPromptCompare').click();assert.equal(svg.getAttribute('data-original'),'true');
    assert.equal(el('polygonPromptCompare').getAttribute('aria-pressed'),'true');
    el('polygonPromptCompare').click();assert.equal(svg.getAttribute('data-original'),'false');assert.equal(saves,compareSaves);
    await el('polygonPromptAccept').click();
    assert.equal(saved.annotations.length,beforePromptCount+1);assert.equal(saved.annotations.at(-1).id,addedId);
    assert.equal(saved.annotations.at(-1).edited,true);
    await el('polygonUndo').click();assert.equal(saved.annotations.at(-1).edited,false);
    // Click segment always creates; Correct is the explicit replacement action.
    svg.onclick(event(find('data-object-id',addedId),20,20));
    const beforeNewPreview=structuredClone(saved),newPreviewSaves=saves;
    el('polygonPromptStart').click();assert.equal(el('polygonPromptAccept').textContent,'Accept preview');
    assert(el('polygonPromptCompare').hidden);assert.equal(el('polygonModeState').textContent,'Click segment');
    await svg.onclick(event(svg,22,22));el('polygonPromptCancel').click();
    assert.deepEqual(saved,beforeNewPreview);assert.equal(saves,newPreviewSaves);
    await el('polygonSamRun').click();pick(1);el('polygonCorrect').click();
    await svg.onclick(event(svg,23,23));await el('polygonPromptAccept').click();
    assert.equal(el('polygonProposals').children.length,2);
    await el('polygonUndo').click();assert.equal(el('polygonProposals').children.length,3);
    el('polygonSamClearSuggestions').click();
    beforePromptSaves=saves;
    el('polygonPromptStart').click();samHold={};const pendingPrompt=svg.onclick(event(svg,20,20));await tick();
    el('polygonPromptCancel').click();assert(el('polygonPromptBar').hidden);
    samHold.resolve();await pendingPrompt;samHold=null;
    assert.equal(saves,beforePromptSaves);assert.equal(el('polygonPromptLayer').children.length,0);
    // Split leaves its parent untouched until all preview pieces are accepted.
    const beforeSplit = structuredClone(saved.annotations), splitSaves = saves, beforeSplitResults = samResults;
    samResults = samResults.slice(0,2);
    const splitParent = saved.annotations.at(-1);
    svg.onclick(event(find('data-object-id',splitParent.id),20,20));
    el('polygonSplit').click();assert.equal(el('polygonPromptHint').textContent,'Click once per cell');
    const beforeSeedCalls=samCalls.length;
    await svg.onclick(event(svg,15,15));assert.equal(samCalls.length,beforeSeedCalls);assert(el('polygonPromptAccept').disabled);
    await svg.onclick(event(svg,20,20));assert.equal(samCalls.at(-1).splitGeometry.type,'polygon');
    assert.equal(saves,splitSaves);assert.deepEqual(saved.annotations,beforeSplit);
    await el('polygonPromptUndo').click();assert(el('polygonPromptAccept').disabled);
    await svg.onclick(event(svg,21,21));await el('polygonPromptAccept').click();
    assert.equal(saved.annotations.length,beforeSplit.length-1+samResults.length);
    assert(!saved.annotations.some(item=>item.id===splitParent.id));assert.equal(saves,splitSaves+1);
    await el('polygonUndo').click();assert.deepEqual(saved.annotations,beforeSplit);
    await el('polygonRedo').click();samResults = beforeSplitResults;
    // Merge selection is reversible and accepting replaces only selected objects.
    const beforeMerge=structuredClone(saved.annotations), mergeSaves=saves;
    await el('polygonMerge').click();assert.equal(el('polygonPromptHint').textContent,'Select objects to merge');
    await el('polygonObjectList').children[0].children[0].click();assert(el('polygonPromptAccept').disabled);
    await el('polygonObjectList').children[1].children[0].click();assert(!el('polygonPromptAccept').disabled);
    assert.equal(saves,mergeSaves);
    await el('polygonObjectList').children[1].children[0].click();assert(el('polygonPromptAccept').disabled);
    mergeError='Disconnected regions';
    await el('polygonObjectList').children[1].children[0].click();assert(el('polygonPromptAccept').disabled);
    assert.deepEqual(saved.annotations,beforeMerge);mergeError=null;
    await el('polygonObjectList').children[1].children[0].click();
    await el('polygonObjectList').children[1].children[0].click();
    await el('polygonPromptAccept').click();assert.equal(saved.annotations.length,beforeMerge.length-1);
    assert.equal(saves,mergeSaves+1);
    await el('polygonUndo').click();assert.deepEqual(saved.annotations,beforeMerge);
    const beforeCancelMerge=saves;
    await el('polygonMerge').click();
    await el('polygonObjectList').children[0].children[0].click();
    mergeHold={};const pendingMerge=el('polygonObjectList').children[1].children[0].click();await tick();
    el('polygonPromptCancel').click();mergeHold.resolve();await pendingMerge;mergeHold=null;
    assert(el('polygonPromptBar').hidden);assert.equal(saves,beforeCancelMerge);
    // Candidate merge removes the selected proposals only; Undo restores them.
    await el('polygonSamRun').click();pick(1);pick(2);
    await el('polygonMerge').click();await el('polygonPromptAccept').click();
    assert.equal(el('polygonProposals').children.length,1);
    await el('polygonUndo').click();assert.equal(el('polygonProposals').children.length,3);
    const duplicateDraftSaves=saves;
    el('polygonDraw').click();
    for(const [x,y] of [[10,10],[50,10],[50,50],[10,10]]) svg.onclick(event(svg,x,y));
    assert(find('data-invalid-points','1,4')); // warning appears before Finish
    const draftCoordinates = () => el('polygonShapes').children.filter(node=>node.hasAttribute('data-draft-index')).map(node=>[node.getAttribute('cx'),node.getAttribute('cy')]);
    const beforeDraftPan=draftCoordinates();
    const middle={...event(find('data-draft-index',3),10,10),button:1};
    svg.onpointerdown(middle);stage.onpointerdown(middle);
    assert.equal(stage.style.cursor,'grabbing');
    stage.onpointermove({...middle,clientX:middle.clientX+40,clientY:middle.clientY+20});
    stage.onpointerup({...middle,clientX:middle.clientX+40,clientY:middle.clientY+20});
    assert.deepEqual(draftCoordinates(),beforeDraftPan);assert.equal(saves,duplicateDraftSaves);
    // Drag a duplicate in the unfinished outline; Escape restores the draft.
    svg.onpointerdown(event(find('data-draft-index',3),10,10));move(15,40);
    listeners.keydown({key:'Escape',target:svg,preventDefault(){}});svg.onclick(event(svg,15,40));
    assert.deepEqual(draftCoordinates(),beforeDraftPan);assert(find('data-invalid-points','1,4'));
    svg.onpointerdown(event(find('data-draft-index',3),10,10));await end(15,40);
    assert(!find('data-invalid-points','1,4'));assert.equal(draftCoordinates().length,4);
    assert.deepEqual(draftCoordinates()[3],['15','40']);assert.equal(saves,duplicateDraftSaves);
    svg.onpointerdown(event(find('data-draft-index',3),15,40));await end(10,10);
    assert(find('data-invalid-points','1,4'));
    await el('polygonFinish').click();
    assert.equal(saves,duplicateDraftSaves);assert(!el('polygonCancel').hidden);
    assert(find('data-invalid-points','1,4'));assert(el('polygonStatus').textContent.includes('press Enter'));
    const duplicateDraftPoint=find('data-draft-index',3);
    duplicateDraftPoint.oncontextmenu({preventDefault(){},stopPropagation(){}});
    assert(!find('data-invalid-points','1,4'));assert(el('polygonStatus').hidden);
    el('polygonCancel').click();
    // A long unfinished outline survives navigation and a local point repair.
    el('polygonDraw').click();
    for(let i=0;i<140;i++) svg.onclick(event(svg,50+35*Math.cos(i*2*Math.PI/140),50+35*Math.sin(i*2*Math.PI/140)));
    const longDraft=draftCoordinates();assert.equal(longDraft.length,140);
    const longPan={...event(svg,20,20),button:1};stage.onpointerdown(longPan);
    stage.onpointermove({...longPan,clientX:longPan.clientX+25});stage.onpointerup({...longPan,clientX:longPan.clientX+25});
    assert.deepEqual(draftCoordinates(),longDraft);
    svg.onpointerdown(event(find('data-draft-index',99),...longDraft[99].map(Number)));await end(45,45);
    assert.equal(draftCoordinates().length,140);
    assert.deepEqual(draftCoordinates().filter((_,i)=>i!==99),longDraft.filter((_,i)=>i!==99));
    assert.equal(saves,duplicateDraftSaves);el('polygonCancel').click();
    // Folder-backed autosave writes LabelMe beside the image, never the server store.
    let folderWrites=[],folderFailure=false;
    window.SAM2ProjectFolder={write:async(file,name,text)=>{
        if(folderFailure)throw Error('Folder permission denied');
        folderWrites.push({file,name,data:JSON.parse(text)});
    }};
    const serverSavesBeforeFolder=saves;
    el('polygonDraw').click();
    svg.onclick(event(svg,10,10));svg.onclick(event(svg,30,10));svg.onclick(event(svg,30,30));
    await el('polygonFinish').click();
    assert.equal(saves,serverSavesBeforeFolder);assert.equal(folderWrites.length,1);
    assert.equal(folderWrites[0].name,'cell2.json');assert.equal(folderWrites[0].data.imagePath,'cell2.TIFF');
    folderFailure=true;await el('polygonUndo').click();
    assert.equal(el('polygonSaveState').textContent,'Save failed — unsaved changes');assert(!el('polygonSave').disabled);
    folderFailure=false;await el('polygonSave').click();assert.equal(folderWrites.length,2);
    assert.equal(el('polygonSaveState').textContent,'Saved');assert.equal(saves,serverSavesBeforeFolder);
    window.SAM2ProjectFolder.has=()=>true;
    window.SAM2ProjectFolder.read=async()=>JSON.stringify({shapes:[]});
    const beforeReopenWrites=folderWrites.length;
    await el('polygonFolder').onchange({target:{files:[new File(['pixels'],'reopened.png')],value:''}});
    assert.equal(folderWrites.length,beforeReopenWrites);assert(el('polygonUndo').disabled);
    assert.equal(el('polygonSaveState').textContent,'Saved');
    assert.equal(el('polygonObjectList').children.length,1);
    // Native folder files must reach the native load path, never the external importer.
    const nativeFile=new File(['native pixels'],'native.png');
    const nativeHash=await crypto.subtle.digest('SHA-256',await nativeFile.arrayBuffer());
    const nativeIdentity=Array.from(new Uint8Array(nativeHash),byte=>byte.toString(16).padStart(2,'0')).join('');
    let nativeDocument={...structuredClone(original),next_object_id:12,image:{identity:nativeIdentity,width:100,height:100},
        review_status:'reviewed',labelme:{flags:{checked:true},custom:'keep'},annotations:[
            {...structuredClone(original.annotations[0]),id:2,edited:true,labelme:{group_id:42,flags:{occluded:true}}},
            {...structuredClone(original.annotations[0]),id:7,class_id:77,source:'sam2',edited:false}]};
    let nativeClasses=[{id:4,name:'Cell'},{id:8,name:'Other'},{id:9,name:'Imported'},{id:77,name:'Restored class'}];
    const encodeNative=document=>({imagePath:'native.png',imageWidth:100,imageHeight:100,
        ...document.labelme,microscopy_studio:{...document,annotations:undefined,labelme:undefined,labelme_keys:Object.keys(document.labelme)},
        shapes:document.annotations.map(item=>({...item.labelme,label:nativeClasses.find(cls=>cls.id===item.class_id).name,shape_type:item.geometry.type,points:item.geometry.points,
            microscopy_studio:{id:item.id,class_id:item.class_id,source:item.source,edited:item.edited,labelme_keys:Object.keys(item.labelme||{})}}))});
    let nativeRaw=encodeNative(nativeDocument),nativeRequests=0,nativeWrites=0,nativeFolderFailure=false;
    const nativeBefore=structuredClone(nativeDocument),nativeImportsBefore=importCalls;
    const previousApi=window.SAM2ApiClient;
    window.SAM2ApiClient={async apiFetch(path,options){
        const data=path==='api/project/segmentation'?JSON.parse(options.body):null;
        if(path==='api/classes'){
            const result=await previousApi.apiFetch(path,options),body=await result.json();
            if(result.ok)nativeClasses=structuredClone(body.classes);
            return {ok:result.ok,json:async()=>structuredClone(body)};
        }
        if(data?.action==='load' && data.labelme){
            nativeRequests++;assert.deepEqual(data.labelme,JSON.parse(JSON.stringify(nativeRaw)));
            assert.equal(data.image_name,'native.png');assert.equal(data.restore_classes,true);
            if(data.labelme.microscopy_studio===null)return {ok:false,json:async()=>({error:'Invalid native autosave metadata'})};
            return {ok:true,json:async()=>({document:structuredClone(nativeDocument),revision:null,
                classes:structuredClone(nativeClasses)})};
        }
        if(data?.action==='export_labelme'){
            exportedPayload=data;
            return {ok:true,json:async()=>({labelme:encodeNative(data.document)})};
        }
        return previousApi.apiFetch(path,options);
    }};
    window.SAM2ProjectFolder={has:()=>true,read:async()=>JSON.stringify(nativeRaw),write:async(file,name)=>{
        if(nativeFolderFailure)throw Error('Folder permission denied');
        assert.strictEqual(file,nativeFile);assert.equal(name,'native.json');nativeWrites++;
        nativeDocument=structuredClone(exportedPayload.document);nativeRaw=encodeNative(nativeDocument);
    }};
    const reopenNative=()=>el('polygonFolder').onchange({target:{files:[nativeFile],value:''}});
    await reopenNative();assert.equal(nativeRequests,1);assert.equal(importCalls,nativeImportsBefore);
    assert.equal(nativeWrites,0);assert(el('polygonUndo').disabled);
    assert(el('polygonClass').children.some(option=>option.value===77 || option.value==='77'));
    assert(find('data-object-id',2));assert(find('data-object-id',7));
    const nativePan={...event(svg,5,5),button:1};stage.onpointerdown(nativePan);
    const nativePanEnd={...nativePan,clientX:nativePan.clientX+30,clientY:nativePan.clientY-20};
    stage.onpointermove(nativePanEnd);stage.onpointerup(nativePanEnd);
    assert.deepEqual(offset(),[30,-20]);assert.equal(nativeWrites,0);
    svg.onclick(event(svg,5,5)); // Consume the click suppressed after a pan.
    await svg.onclick(event(find('data-object-id',2),20,20));
    await listeners.keydown({key:'Delete',target:svg,preventDefault(){}});
    assert.equal(nativeWrites,1);assert.deepEqual(nativeDocument.annotations.map(item=>item.id),[7]);
    assert.equal(nativeDocument.next_object_id,12);
    await el('polygonUndo').click();assert.equal(nativeWrites,2);assert.deepEqual(nativeDocument,nativeBefore);
    await el('polygonRedo').click();assert.equal(nativeWrites,3);assert.deepEqual(nativeDocument.annotations.map(item=>item.id),[7]);
    await el('polygonUndo').click();
    await reopenNative();assert.equal(nativeRequests,2);assert.equal(nativeWrites,4);assert(el('polygonUndo').disabled);
    el('polygonDraw').click();svg.onclick(event(svg,5,5));svg.onclick(event(svg,20,5));svg.onclick(event(svg,20,20));
    await el('polygonFinish').click();assert.equal(nativeWrites,5);
    assert.deepEqual(nativeDocument.annotations.map(item=>item.id),[2,7,12]);assert.equal(nativeDocument.next_object_id,13);
    assert.deepEqual(nativeDocument.annotations.slice(0,2),nativeBefore.annotations);
    await el('polygonUndo').click();assert.equal(nativeDocument.next_object_id,13);
    await reopenNative();assert.equal(nativeRequests,3);assert.equal(nativeDocument.next_object_id,13);
    assert.deepEqual(nativeDocument.annotations,nativeBefore.annotations);assert.equal(importCalls,nativeImportsBefore);
    const beforeInvalidNativeWrites=nativeWrites;
    nativeRaw.microscopy_studio=null;await reopenNative();
    assert(el('polygonStatus').textContent.includes('Invalid native autosave'));
    assert(el('polygonReviewNext').disabled);assert.equal(nativeWrites,beforeInvalidNativeWrites);
    assert.equal(importCalls,nativeImportsBefore);
    nativeRaw=encodeNative(nativeDocument);await reopenNative();assert.equal(el('polygonReviewState').textContent,'Reviewed');
    // Rename is a saved, reversible label edit, even when geometry and IDs do not change.
    const beforeRename=structuredClone(nativeDocument),beforeRenameRaw=structuredClone(nativeRaw),beforeRenameWrites=nativeWrites;
    await editClass('class-name-input','Renamed cell',0);
    assert.equal(nativeWrites,beforeRenameWrites+1);assert.equal(nativeRaw.shapes[0].label,'Renamed cell');
    assert.equal(nativeRaw.shapes[1].label,'Restored class');assert.equal(nativeRaw.microscopy_studio.review_status,'in_progress');
    assert.deepEqual(nativeDocument.annotations,beforeRename.annotations);assert.equal(nativeDocument.next_object_id,beforeRename.next_object_id);
    assert.equal(el('polygonSaveState').textContent,'Saved');assert.equal(el('polygonReviewState').textContent,'In progress');
    const renamePan={...event(svg,5,5),button:1},renamePanEnd={...event(svg,5,5),button:1,clientX:145,clientY:35};
    stage.onpointerdown(renamePan);stage.onpointermove(renamePanEnd);stage.onpointerup(renamePanEnd);
    assert.deepEqual(offset(),[35,-25]);assert.equal(nativeWrites,beforeRenameWrites+1);
    await editClass('class-color-input','#abcdef',0);
    await el('polygonUndo').click();
    assert.equal(nativeWrites,beforeRenameWrites+2);assert.deepEqual(nativeDocument,beforeRename);
    assert.deepEqual(nativeRaw,beforeRenameRaw);assert.equal(nativeClasses[0].color,'#abcdef');
    assert.equal(el('polygonReviewState').textContent,'Reviewed');assert.deepEqual(offset(),[35,-25]);
    await el('polygonRedo').click();assert.equal(nativeWrites,beforeRenameWrites+3);
    assert.equal(nativeRaw.shapes[0].label,'Renamed cell');assert.equal(nativeClasses[0].color,'#abcdef');
    // A second rename while already in progress must still save; failures cannot look clean.
    const beforeFailedRename=structuredClone(nativeRaw);
    nativeFolderFailure=true;await editClass('class-name-input','Pending rename',0);
    assert.equal(nativeWrites,beforeRenameWrites+3);assert.deepEqual(nativeRaw,beforeFailedRename);
    assert.equal(el('polygonSaveState').textContent,'Save failed — unsaved changes');
    discard=false;assert(!editor.canLeave());discard=true;
    nativeFolderFailure=false;await el('polygonSave').click();assert.equal(nativeWrites,beforeRenameWrites+4);
    assert.equal(nativeRaw.shapes[0].label,'Pending rename');assert.equal(el('polygonSaveState').textContent,'Saved');
    await el('polygonUndo').click();assert.equal(nativeWrites,beforeRenameWrites+5);assert.equal(nativeRaw.shapes[0].label,'Renamed cell');
    await el('polygonUndo').click();assert.equal(nativeWrites,beforeRenameWrites+6);assert.deepEqual(nativeRaw,beforeRenameRaw);
    assert(el('polygonUndo').disabled);assert(!el('polygonRedo').disabled);
    classFailure='Class save failed';await editClass('class-name-input','Rejected rename',0);classFailure=null;
    assert.equal(nativeWrites,beforeRenameWrites+6);assert.deepEqual(nativeRaw,beforeRenameRaw);
    assert.equal(nativeClasses[0].name,'Cell');assert(el('polygonUndo').disabled);assert(!el('polygonRedo').disabled);
    await editClass('class-name-input','Cell',0);assert.equal(nativeWrites,beforeRenameWrites+6);
    assert.equal(el('polygonReviewState').textContent,'Reviewed');
    await reopenNative();assert.equal(nativeWrites,beforeRenameWrites+6);assert.deepEqual(nativeDocument,beforeRename);
    nativeDocument={...nativeDocument,annotations:[],review_status:'confirmed_empty'};
    nativeRaw=encodeNative(nativeDocument);await reopenNative();
    await editClass('class-name-input','Renamed cell',0);
    assert.equal(nativeWrites,beforeRenameWrites+7);assert.equal(nativeRaw.microscopy_studio.review_status,'unreviewed');
    await el('polygonUndo').click();assert.equal(nativeWrites,beforeRenameWrites+8);
    assert.equal(nativeRaw.microscopy_studio.review_status,'confirmed_empty');assert.equal(nativeClasses[0].name,'Cell');
    window.SAM2ApiClient=previousApi;
    // Review is an explicit saved decision, independent of autosave. Reopening
    // a folder restores its queue, including reviewed images not yet visited.
    const reviewFiles=['a.png','b.png','c.png'].map(name=>new File([name],name));
    const reviewDocs=new Map(),reviewDisk=new Map();let reviewFail=false,reviewWrites=0,finishQueueScan;
    for(const [index,file] of reviewFiles.entries()) {
        const hash=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());
        const identity=Array.from(new Uint8Array(hash),byte=>byte.toString(16).padStart(2,'0')).join('');
        reviewDocs.set(identity,{...structuredClone(original),image:{identity,width:100,height:100},
            annotations:index===1?[]:structuredClone(original.annotations),review_status:index===2?'reviewed':index===1?'unreviewed':'in_progress'});
        if(index!==1)reviewDisk.set(file.name.replace('.png','.json'),{document:reviewDocs.get(identity),imageWidth:100,imageHeight:100});
    }
    const reviewClasses=[{id:4,name:'Cell'},{id:8,name:'Other'},{id:9,name:'Imported'}];
    const response=data=>({ok:true,json:async()=>structuredClone(data)});
    window.SAM2ApiClient={async apiFetch(path,options){
        if(path==='api/load_image')return response({width:100,height:100,image_url:'fixture'});
        const data=JSON.parse(options.body);
        if(data.action==='load')return response({document:reviewDocs.get(data.image.identity),revision:null});
        if(data.action==='import_labelme')return response({document:data.labelme.document,classes:reviewClasses});
        if(data.action==='inspect_labelme')return response({review_status:data.labelme.document.review_status,count:data.labelme.document.annotations.length});
        if(data.action==='export_labelme')return response({labelme:{imagePath:data.image_name,imageWidth:100,imageHeight:100,document:data.document,shapes:data.document.annotations}});
        return response({document:data.document});
    }};
    window.SAM2ProjectFolder={has:()=>true,
        read:async(file,name)=>reviewDisk.has(name)?JSON.stringify(reviewDisk.get(name)):null,
        peek:async(file,name)=>{if(name==='c.json')await new Promise(resolve=>finishQueueScan=resolve);return reviewDisk.has(name)?JSON.stringify(reviewDisk.get(name)):null;},
        write:async(file,name,text)=>{if(reviewFail)throw Error('Disk full');reviewWrites++;reviewDisk.set(name,JSON.parse(text));}};
    await el('polygonFolder').onchange({target:{files:reviewFiles,value:''}});await tick();await tick();
    assert(!el('polygonReviewNext').disabled); // A large folder's background scan must not block reviewing this image.
    finishQueueScan();await waitFor(()=>el('polygonReviewCount').textContent==='1 / 3 reviewed');
    assert.equal(el('polygonReviewCount').textContent,'1 / 3 reviewed');
    assert.equal(el('polygonReviewState').textContent,'In progress');assert(!el('polygonReviewNext').disabled);
    assert.equal(el('polygonImageQueue').children.length,3);
    const filter=value=>el('polygonQueueFilters').onclick({target:{closest:()=>({dataset:{filter:value}})}});
    filter('completed');assert.equal(el('polygonImageQueue').children.length,1);
    filter('needs_review');assert.equal(el('polygonImageQueue').children.length,2);filter('all');
    el('polygonDraw').click();assert(el('polygonReviewNext').disabled);el('polygonCancel').click();
    await el('polygonPromptStart').click();assert(el('polygonReviewNext').disabled);el('polygonPromptCancel').click();
    reviewFail=true;await el('polygonReviewNext').click();
    assert.equal(el('polygonImageList').value,'0');assert.equal(el('polygonReviewCount').textContent,'1 / 3 reviewed');
    assert(el('polygonReviewNext').disabled);assert(!el('polygonSave').hidden);
    reviewFail=false;await el('polygonSave').click();
    assert.equal(reviewDisk.get('a.json').document.review_status,'reviewed');assert.equal(el('polygonReviewCount').textContent,'2 / 3 reviewed');
    await el('polygonReviewNext').click();assert.equal(el('polygonImageList').value,'1');
    assert.equal(el('polygonReviewNext').textContent,'Confirm empty & next');
    await el('polygonReviewNext').click();
    assert.equal(reviewDisk.get('b.json').document.review_status,'confirmed_empty');
    assert.equal(el('polygonReviewCount').textContent,'3 / 3 reviewed');assert.equal(el('polygonImageList').value,'1');
    assert(el('polygonReviewNext').disabled);
    await el('polygonPrevious').click();assert.equal(el('polygonReviewState').textContent,'Reviewed');
    select();await listeners.keydown({key:'Delete',target:svg,preventDefault(){}});
    assert.equal(reviewDisk.get('a.json').document.review_status,'unreviewed');assert.equal(el('polygonReviewCount').textContent,'2 / 3 reviewed');
    await el('polygonUndo').click();assert.equal(reviewDisk.get('a.json').document.review_status,'reviewed');
    await el('polygonReopenReview').click();assert.equal(reviewDisk.get('a.json').document.review_status,'in_progress');
    await el('polygonUndo').click();assert.equal(el('polygonReviewCount').textContent,'3 / 3 reviewed');
    const beforeCompareReviewWrites=reviewWrites;
    saved.image=reviewDisk.get('a.json').document.image; // Keep the simulated SAM response tied to this source.
    await el('polygonSamRun').click();assert(el('polygonReviewNext').disabled);
    discard=false;assert(!editor.canLeave());discard=true;
    await el('polygonSamClearSuggestions').click();assert.equal(reviewWrites,beforeCompareReviewWrites);
    samHold={};const staleRun=el('polygonSamRun').click();await tick();editor.dispose();samHold.resolve();await staleRun;
    assert.equal(el('polygonProposals').children.length,0);assert(el('polygonSamReview').hidden);assert.equal(wheelHandler,null);

    // Resume opens the bookmarked image, reloads its saved review and restores
    // the queue filter without writing annotations or accepting suggestions.
    const bookmarks=[];
    window.SAM2ProjectFolder.imagePath=file=>file.name;
    window.SAM2ProjectFolder.remember=async(...args)=>{bookmarks.push(args);return true;};
    window.SAM2ProjectFolder.peek=window.SAM2ProjectFolder.read;
    const resumedEditor=window.SAM2PolygonEditor.mount({project_id:'resume-project',classes:reviewClasses});
    const bookmark={files:reviewFiles,lastPath:'b.png',identity:reviewDisk.get('b.json').document.image.identity,filter:'completed'};
    const beforeResumeWrites=reviewWrites;
    assert(await resumedEditor.resume(bookmark));await waitFor(()=>el('polygonReviewCount').textContent==='3 / 3 reviewed');
    assert.equal(el('polygonImageList').value,'1');assert.equal(el('polygonReviewState').textContent,'Confirmed empty');
    assert.equal(el('polygonImageQueue').children.length,3);assert.equal(reviewWrites,beforeResumeWrites);
    assert.equal(bookmarks.at(-1)[0],'resume-project');assert.equal(bookmarks.at(-1)[2].name,'b.png');
    assert.equal(bookmarks.at(-1)[3].filter,'completed');assert.equal(bookmarks.at(-1)[3].identity,bookmark.identity);
    await el('polygonPrevious').click();assert.equal(bookmarks.at(-1)[2].name,'a.png');
    assert.equal(await resumedEditor.resume(bookmark),false); // A user-opened queue wins over an old resume.
    resumedEditor.dispose();
    const changedEditor=window.SAM2PolygonEditor.mount({project_id:'resume-project',classes:reviewClasses});
    const beforeChangedBookmarks=bookmarks.length;
    assert.equal(await changedEditor.resume({...bookmark,identity:'changed source'}),false);
    assert.equal(reviewWrites,beforeResumeWrites);assert.equal(bookmarks.length,beforeChangedBookmarks);
    assert(el('polygonStatus').textContent.includes('saved image changed'));changedEditor.dispose();
    const missingEditor=window.SAM2PolygonEditor.mount({project_id:'resume-project',classes:reviewClasses});
    assert(await missingEditor.resume({...bookmark,lastPath:'removed.png'}));
    assert.equal(el('polygonImageList').value,'0');assert.equal(bookmarks.at(-1)[2].name,'a.png');
    assert(el('polygonStatus').textContent.includes('first available image'));missingEditor.dispose();

    // Local correction never asks SAM to redraw the object. Preview and Cancel
    // preserve disk/state; Apply retains the other vertices, IDs and metadata.
    const localBase=structuredClone(reviewDisk.get('a.json').document);
    localBase.annotations[0].geometry=structuredClone(original.annotations[0].geometry);
    localBase.annotations[0].labelme={group_id:7,flags:{keep:true}};
    localBase.annotations.push({id:10,class_id:8,source:'imported',edited:false,
        geometry:{type:'rectangle',points:[[85,85],[95,95]]},labelme:{group_id:9}});
    localBase.next_object_id=11;localBase.review_status='reviewed';
    reviewDisk.set('a.json',{document:localBase,imageWidth:100,imageHeight:100});
    const priorApi=window.SAM2ApiClient;let localReject=false,localHold=null;
    window.SAM2ApiClient={async apiFetch(path,options){
        if(path==='api/project/segmentation'&&JSON.parse(options.body).action==='validate'){
            if(localHold)await new Promise(resolve=>localHold.resolve=resolve);
            if(localReject)return {ok:false,json:async()=>({error:'Invalid local outline'})};
        }
        return priorApi.apiFetch(path,options);
    }};
    const localEditor=window.SAM2PolygonEditor.mount({project_id:'resume-project',classes:reviewClasses});
    assert(await localEditor.resume({files:[reviewFiles[0]],lastPath:'a.png',identity:localBase.image.identity,filter:'all'}));
    const localWrites=reviewWrites;
    svg.onclick(event(find('data-object-id',10),90,90));assert(el('polygonLocalCorrect').disabled);
    select();el('polygonLocalCorrect').click();assert(!el('polygonLocalBar').hidden);
    assert(el('polygonSelectionActions').hidden);assert(el('polygonReviewNext').disabled);
    el('polygonObjectList').children[1].oncontextmenu({preventDefault(){}});
    assert(el('polygonLabelPicker').hidden);assert(!el('polygonLocalBar').hidden);
    svg.onclick(event(svg,40,40));assert(el('polygonStatus').textContent.includes('selected outline'));
    const localClick=(x,y)=>svg.onclick(event(svg,x,y));
    localClick(20,10);assert(el('polygonLocalApply').disabled);
    discard=false;assert(!localEditor.canLeave());discard=true;
    let unfinished=false;unload({preventDefault(){unfinished=true;}});assert(unfinished);
    localClick(20,10);assert(el('polygonStatus').textContent.includes('different end point'));
    localClick(70,10);localClick(40,5);localClick(60,5);
    const localLayer=()=>el('polygonPromptLayer').children;
    const localPath=()=>localLayer().find(node=>node.getAttribute('class')==='local-replacement').getAttribute('points');
    assert.equal(localPath(),'20,10 40,5 60,5 70,10');assert.equal(reviewWrites,localWrites);
    assert.deepEqual(reviewDisk.get('a.json').document,localBase);
    await el('polygonLocalCompare').click();assert(!localLayer().some(node=>node.getAttribute('class')==='local-replacement'));
    await el('polygonLocalCompare').click();assert.equal(localPath(),'20,10 40,5 60,5 70,10');
    const retained=localLayer().find(node=>node.getAttribute('class')==='local-retained').getAttribute('points');
    assert.equal(retained,'70,10 80,10 80,80 10,80 10,10 20,10');
    await el('polygonLocalSide').click();assert.equal(el('polygonLocalSide').getAttribute('aria-pressed'),'true');
    assert.equal(localLayer().find(node=>node.getAttribute('class')==='local-retained').getAttribute('points'),'20,10 70,10');
    assert.equal(reviewWrites,localWrites);await el('polygonLocalSide').click();
    const localOffset=svg.style.transform;
    const pan={...event(svg,40,40),pointerId:45,button:1};
    svg.parentElement.onpointerdown(pan);
    svg.parentElement.onpointermove({...pan,clientX:pan.clientX+25,clientY:pan.clientY+10});
    svg.parentElement.onpointerup({...pan,clientX:pan.clientX+25,clientY:pan.clientY+10});
    svg.onclick({...pan,button:1});assert.notEqual(svg.style.transform,localOffset);
    assert.equal(localPath(),'20,10 40,5 60,5 70,10');assert.equal(reviewWrites,localWrites);
    await listeners.keydown({key:'z',ctrlKey:true,target:{tagName:'INPUT'},preventDefault(){throw Error('Typing was intercepted');}});
    el('projectDialog').open=true;
    await listeners.keydown({key:'Escape',target:svg,preventDefault(){throw Error('Dialog was intercepted');}});
    el('projectDialog').open=false;assert(!el('polygonLocalBar').hidden);
    await listeners.keydown({key:'z',ctrlKey:true,target:svg,preventDefault(){}});
    assert.equal(localPath(),'20,10 40,5 70,10');assert.deepEqual(reviewDisk.get('a.json').document,localBase);
    await listeners.keydown({key:'Escape',target:svg,preventDefault(){}});
    assert(el('polygonLocalBar').hidden);assert.equal(reviewWrites,localWrites);
    el('polygonLocalCorrect').click();localClick(20,10);localClick(70,10);localClick(40,5);localClick(60,5);
    localReject=true;await el('polygonLocalApply').click();assert(!el('polygonLocalBar').hidden);
    assert.equal(reviewWrites,localWrites);assert.deepEqual(reviewDisk.get('a.json').document,localBase);
    assert(el('polygonStatus').textContent.includes('Invalid local outline'));localReject=false;
    await listeners.keydown({key:'Enter',target:svg,preventDefault(){}});
    assert(el('polygonLocalBar').hidden);assert.equal(reviewWrites,localWrites+1);
    const localApplied=structuredClone(reviewDisk.get('a.json').document),target=localApplied.annotations[0];
    assert.deepEqual(target.geometry.points,[[20,10],[40,5],[60,5],[70,10],[80,10],[80,80],[10,80],[10,10]]);
    assert.deepEqual({...target,geometry:localBase.annotations[0].geometry,edited:localBase.annotations[0].edited},localBase.annotations[0]);
    assert.deepEqual(localApplied.annotations[1],localBase.annotations[1]);assert.equal(localApplied.next_object_id,11);
    assert.equal(localApplied.review_status,'in_progress');assert.equal(el('polygonSaveState').textContent,'Saved');
    await listeners.keydown({key:'z',ctrlKey:true,target:svg,preventDefault(){}});
    assert.deepEqual(reviewDisk.get('a.json').document,localBase);
    await listeners.keydown({key:'z',ctrlKey:true,shiftKey:true,target:svg,preventDefault(){}});
    assert.deepEqual(reviewDisk.get('a.json').document,localApplied);
    await el('polygonUndo').click();select();el('polygonLocalCorrect').click();
    localClick(20,10);localClick(70,10);localClick(40,5);reviewFail=true;
    await el('polygonLocalApply').click();assert(el('polygonLocalBar').hidden);
    assert.equal(el('polygonSaveState').textContent,'Save failed — unsaved changes');
    assert.deepEqual(reviewDisk.get('a.json').document,localBase);reviewFail=false;
    await el('polygonSave').click();assert.equal(el('polygonSaveState').textContent,'Saved');
    await el('polygonUndo').click();assert.deepEqual(reviewDisk.get('a.json').document,localBase);
    select();el('polygonLocalCorrect').click();localClick(20,10);localClick(70,10);localClick(40,5);
    localHold={};const staleLocal=el('polygonLocalApply').click();await tick();
    const beforeStaleLocal=reviewWrites;localEditor.dispose();localHold.resolve();await staleLocal;
    assert.equal(reviewWrites,beforeStaleLocal);assert.deepEqual(reviewDisk.get('a.json').document,localBase);

    // Manual cutting uses the same anchors/draft controls, but replaces the
    // parent with two fresh objects without inference or changing neighbors.
    localHold=null;
    const splitBoundary=window.SAM2PolygonGeometry.correctedBoundary;
    let cutReject=false,cutHold=null,cutWrongCount=false,cutRequests=0;
    const localApi=window.SAM2ApiClient;
    window.SAM2ApiWorkflows.runSam=()=>{throw Error('Manual cutting must not invoke SAM');};
    window.SAM2ApiClient={async apiFetch(path,options){
        if(path.includes('sam/'))throw Error('Manual cutting must not invoke SAM');
        if(path==='api/project/segmentation'){
            const data=JSON.parse(options.body);
            if(data.action==='manual_split_preview'){
                cutRequests++;if(cutHold)await new Promise(resolve=>cutHold.resolve=resolve);
                if(cutReject)return {ok:false,json:async()=>({error:'Invalid manual cut'})};
                const points=data.geometry.points;
                const anchor=value=>{const a=points[value.edge],b=points[(value.edge+1)%points.length];return {...value,point:a.map((x,i)=>x+value.t*(b[i]-x))};};
                const geometries=[false,true].map(side=>({type:'polygon',points:splitBoundary(points,anchor(data.start),anchor(data.end),data.points,side).points}));
                return response({geometries:cutWrongCount?geometries.slice(0,1):geometries});
            }
        }
        return localApi.apiFetch(path,options);
    }};
    const cutEditor=window.SAM2PolygonEditor.mount({project_id:'resume-project',classes:reviewClasses});
    assert(await cutEditor.resume({files:[reviewFiles[0]],lastPath:'a.png',identity:localBase.image.identity,filter:'all'}));
    const startCut=()=>{select();el('polygonManualSplit').click();localClick(45,10);localClick(45,80);};
    const cutPieces=()=>localLayer().filter(node=>node.getAttribute('class')==='local-cut-preview');
    const cutLine=()=>localLayer().find(node=>node.getAttribute('class')==='local-cut-line').getAttribute('points');
    svg.onclick(event(find('data-object-id',10),90,90));assert(el('polygonManualSplit').disabled);
    const beforeCutWrites=reviewWrites;
    startCut();assert.equal(el('polygonLocalApply').textContent,'Apply split');assert(el('polygonLocalSide').hidden);
    assert.equal(el('polygonLocalBar').getAttribute('aria-label'),'Manual cut-line split');
    assert.equal(cutPieces().length,2);assert.equal(cutLine(),'45,10 45,80');
    assert.equal(cutRequests,0);assert(el('polygonReviewNext').disabled);
    localClick(40,40);assert.equal(cutLine(),'45,10 40,40 45,80');
    await el('polygonLocalCompare').click();assert.equal(cutPieces().length,0);
    await el('polygonLocalCompare').click();assert.equal(cutPieces().length,2);
    const cutTransform=svg.style.transform,cutPan={...event(svg,45,45),pointerId:55,button:1};
    svg.parentElement.onpointerdown(cutPan);
    svg.parentElement.onpointermove({...cutPan,clientX:cutPan.clientX+20,clientY:cutPan.clientY+15});
    svg.parentElement.onpointerup({...cutPan,clientX:cutPan.clientX+20,clientY:cutPan.clientY+15});
    svg.onclick(cutPan);assert.notEqual(svg.style.transform,cutTransform);
    assert.equal(cutLine(),'45,10 40,40 45,80');assert.equal(reviewWrites,beforeCutWrites);
    await listeners.keydown({key:'z',ctrlKey:true,target:svg,preventDefault(){}});
    assert.equal(cutLine(),'45,10 45,80');assert.deepEqual(reviewDisk.get('a.json').document,localBase);
    discard=false;assert(!cutEditor.canLeave());discard=true;
    await listeners.keydown({key:'Escape',target:svg,preventDefault(){}});
    assert(el('polygonLocalBar').hidden);assert.equal(reviewWrites,beforeCutWrites);
    startCut();localClick(40,40);cutReject=true;
    await el('polygonLocalApply').click();assert(!el('polygonLocalBar').hidden);
    assert(el('polygonStatus').textContent.includes('Invalid manual cut'));
    assert.equal(reviewWrites,beforeCutWrites);assert.deepEqual(reviewDisk.get('a.json').document,localBase);
    cutReject=false;cutWrongCount=true;await el('polygonLocalApply').click();
    assert(el('polygonStatus').textContent.includes('exactly two outlines'));assert.equal(reviewWrites,beforeCutWrites);cutWrongCount=false;
    await listeners.keydown({key:'Enter',target:svg,preventDefault(){}});
    assert(el('polygonLocalBar').hidden);assert.equal(reviewWrites,beforeCutWrites+1);
    const cutApplied=structuredClone(reviewDisk.get('a.json').document);
    assert.deepEqual(cutApplied.annotations[0],localBase.annotations[1]);
    assert.deepEqual(cutApplied.annotations.map(item=>item.id),[10,11,12]);assert.equal(cutApplied.next_object_id,13);
    for(const child of cutApplied.annotations.slice(1)){
        assert.equal(child.class_id,localBase.annotations[0].class_id);assert.equal(child.source,'manual');assert(child.edited);
        assert.equal(child.labelme,undefined);
    }
    assert.equal(cutApplied.review_status,'in_progress');assert.equal(el('polygonObjectCount').textContent,'3');
    await listeners.keydown({key:'z',ctrlKey:true,target:svg,preventDefault(){}});
    const restoredCut=reviewDisk.get('a.json').document;
    assert.deepEqual({...restoredCut,next_object_id:11},localBase);assert.equal(restoredCut.next_object_id,13);
    await listeners.keydown({key:'z',ctrlKey:true,shiftKey:true,target:svg,preventDefault(){}});
    assert.deepEqual(reviewDisk.get('a.json').document,cutApplied);
    await el('polygonUndo').click();startCut();reviewFail=true;
    const beforeFailedCut=structuredClone(reviewDisk.get('a.json').document);
    await el('polygonLocalApply').click();assert(el('polygonLocalBar').hidden);
    assert.equal(el('polygonSaveState').textContent,'Save failed — unsaved changes');
    assert.deepEqual(reviewDisk.get('a.json').document,beforeFailedCut);reviewFail=false;
    await el('polygonSave').click();assert.equal(el('polygonSaveState').textContent,'Saved');
    assert.deepEqual(reviewDisk.get('a.json').document.annotations.map(item=>item.id),[10,13,14]);
    await el('polygonUndo').click();assert.deepEqual(reviewDisk.get('a.json').document.annotations,localBase.annotations);
    startCut();cutHold={};const staleCut=el('polygonLocalApply').click();await tick();
    const beforeStaleCut=reviewWrites;cutEditor.dispose();cutHold.resolve();await staleCut;
    assert.equal(reviewWrites,beforeStaleCut);assert.deepEqual(reviewDisk.get('a.json').document.annotations,localBase.annotations);

})().catch(error => { console.error(error); process.exit(1); });
""", text=True, encoding="utf-8", cwd=Path(__file__).resolve().parents[1], check=True)
