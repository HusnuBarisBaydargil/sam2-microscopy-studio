import copy
import subprocess
from pathlib import Path

import pytest
from test_frontend_canvas_renderer import _node_executable
from test_polygon_api import polygon_project  # noqa: F401


def test_detection_class_deletion_is_one_reversible_action():
    subprocess.run([_node_executable(), '-e', r"""
const fs=require('fs'),assert=require('assert');global.window={};
eval(fs.readFileSync('static/frontendConfig.js','utf8'));
eval(fs.readFileSync('static/annotationCodecs.js','utf8'));
eval(fs.readFileSync('static/annotationController.js','utf8'));
const controller=window.SAM2AnnotationController;
const classes=[{id:1,name:'Cell',color:'#123456',hotkey:'c'},{id:2,name:'Other'}];
const annotations=[{id:1,class:'Cell',contour:[[1,2],[3,4]]},{id:2,class:'Other'},{id:3,class:'Cell'}];
const original=structuredClone({classes,annotations}),history=[],redo=[],candidates=[];
const otherImage=[{id:5,class:'Cell'}];
assert.equal(controller.deleteClassFromImage(classes,annotations,history,redo,0),2);
assert.deepEqual(annotations,[original.annotations[1]]);assert.equal(classes.length,1);
assert.equal(history.length,1);assert.deepEqual(otherImage,[{id:5,class:'Cell'}]);
controller.undoLastAction(annotations,candidates,history,redo,classes);
assert.deepEqual({classes,annotations},original);
controller.redoLastAction(annotations,candidates,history,redo,classes);
assert.equal(annotations.length,1);assert.equal(classes.length,1);
controller.undoLastAction(annotations,candidates,history,redo,classes);
assert.deepEqual({classes,annotations},original);
// Removing an unused class is also reversible without clearing prior history.
classes.push({id:3,name:'Unused'});
assert.equal(controller.deleteClassFromImage(classes,annotations,history,redo,2),0);
controller.undoLastAction(annotations,candidates,history,redo,classes);
assert.equal(classes[2].name,'Unused');
"""], cwd=Path(__file__).resolve().parents[1], check=True)


def test_class_removed_on_one_image_does_not_break_another(client, request):
    headers, image, document = request.getfixturevalue('polygon_project')
    endpoint = '/api/project/segmentation'
    other = copy.deepcopy(document)
    other['image']['identity'] = 'b' * 64
    original_classes = client.get('/api/classes').get_json()['classes']
    saved = client.post(endpoint, headers=headers, json={
        'action': 'save', 'image': other['image'], 'document': other, 'revision': None,
    })
    assert saved.status_code == 200
    deleted = client.post('/api/classes', headers=headers, json={'classes': []})
    assert deleted.status_code == 200
    assert deleted.get_json()['classes'] == []
    empty = copy.deepcopy(document)
    empty['annotations'] = []
    assert client.post(endpoint, headers=headers, json={
        'action': 'save', 'image': image, 'document': empty, 'revision': None,
    }).status_code == 200
    # Reloading the project keeps the archived definition, including its stable ID.
    reopened = client.post('/api/project/projects', headers=headers, json={
        'action': 'open', 'project_id': headers['X-Project-ID'],
    })
    assert reopened.status_code == 200
    local_override = client.post(endpoint, headers=headers, json={
        'action': 'load', 'image': other['image'], 'restore_classes': False,
    })
    assert local_override.status_code == 200
    assert local_override.get_json()['classes'] == []
    loaded = client.post(endpoint, headers=headers, json={'action': 'load', 'image': other['image']})
    assert loaded.status_code == 200
    assert loaded.get_json()['document']['annotations'][0]['class_id'] == original_classes[0]['id']
    assert loaded.get_json()['classes'] == original_classes
    current = client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()
    assert current['document']['annotations'] == []
    # Undo can reactivate the original class ID and persist the original annotation.
    assert client.post('/api/classes', headers=headers, json={'classes': original_classes}).status_code == 200
    assert client.post(endpoint, headers=headers, json={
        'action': 'save', 'image': image, 'document': document, 'revision': current['revision'],
    }).status_code == 200


def test_undo_class_restore_rejects_name_conflicts_without_mutating_manifest(client, request, app_module):
    headers, _, _ = request.getfixturevalue('polygon_project')
    original = client.get('/api/classes').get_json()['classes'][0]
    classes = client.post('/api/classes', headers=headers, json={
        'classes': [original, {'name': 'Other'}]}).get_json()['classes']
    other = classes[1]
    assert client.post('/api/classes', headers=headers, json={'classes': [other]}).status_code == 200
    reused = {**other, 'name': original['name']}
    assert client.post('/api/classes', headers=headers, json={'classes': [reused]}).status_code == 200
    before = client.get('/api/project/manifest').get_json()
    before_bytes = Path(app_module._project_manifest_path()).read_bytes()
    # Both insertion orders must reject instead of silently dropping either identity.
    for attempted in ([original, reused], [reused, original]):
        result = client.post('/api/classes', headers=headers, json={
            'classes': attempted, 'restore_class_id': original['id']})
        assert result.status_code == 409, result.get_json()
        assert client.get('/api/project/manifest').get_json() == before
        assert Path(app_module._project_manifest_path()).read_bytes() == before_bytes
    # A stale editor may not know that another tab has reused the name.
    result = client.post('/api/classes', headers=headers, json={
        'classes': [original, other], 'restore_class_id': original['id']})
    assert result.status_code == 409, result.get_json()
    assert client.get('/api/project/manifest').get_json() == before
    assert Path(app_module._project_manifest_path()).read_bytes() == before_bytes
    assert client.post('/api/classes', headers=headers, json={'classes': [other]}).status_code == 200
    restored = client.post('/api/classes', headers=headers, json={
        'classes': [original, other], 'restore_class_id': original['id']})
    assert restored.status_code == 200, restored.get_json()
    assert restored.get_json()['classes'] == [original, other]


def test_class_restore_requires_a_positive_integer_id(client, request, app_module):
    headers, _, _ = request.getfixturevalue('polygon_project')
    before = client.get('/api/project/manifest').get_json()
    before_bytes = Path(app_module._project_manifest_path()).read_bytes()
    for invalid in (None, True, 0, '1'):
        response = client.post('/api/classes', headers=headers, json={
            'classes': before['classes'], 'restore_class_id': invalid})
        assert response.status_code == 400, response.get_json()
        assert Path(app_module._project_manifest_path()).read_bytes() == before_bytes
    assert client.get('/api/project/manifest').get_json() == before


def test_detection_class_history_conflicts_are_atomic_and_redo_uses_ids():
    subprocess.run([_node_executable(), '-'], input=r"""
const fs=require('fs'),assert=require('assert');global.window={};
for(const name of ['frontendConfig','annotationCodecs','annotationController'])eval(fs.readFileSync('static/'+name+'.js','utf8'));
const controller=window.SAM2AnnotationController;
const original={id:1,name:'Cell',color:'#123456',hotkey:'c'},other={id:2,name:'Other',color:'#abcdef',hotkey:'o'};
const classes=[structuredClone(original),structuredClone(other)];
const annotations=[{id:1,class:'Cell',bbox:[1,2,3,4]},{id:2,class:'Other',bbox:[5,6,7,8]}];
const history=[],redo=[],candidates=[{id:'candidate',bbox:[10,10,4,4]}];
controller.deleteClassFromImage(classes,annotations,history,redo,0);
classes[0].name='Cell';
const snapshot=()=>structuredClone({classes,annotations,history,redo,candidates});
const before=snapshot();
assert.throws(()=>controller.undoLastAction(annotations,candidates,history,redo,classes),/another class uses that name/);
assert.deepEqual(snapshot(),before);
// A conflict late in a nested command must not partly undo geometry or annotations.
const deleteCommand=history[0];
history[0]={type:'compound',label:'nested action',commands:[deleteCommand,
 {type:'geometry_edit',changes:[{id:2,oldBbox:[0,0,2,2],newBbox:[5,6,7,8]}]}]};
const nested=snapshot();
assert.throws(()=>controller.undoLastAction(annotations,candidates,history,redo,classes),/another class uses that name/);
assert.deepEqual(snapshot(),nested);
history[0]=deleteCommand;
classes[0].name='Other';
controller.undoLastAction(annotations,candidates,history,redo,classes);
assert.deepEqual(classes,[original,other]);assert.equal(annotations[0].class,'Cell');
assert.equal(annotations[0].id,1);assert.deepEqual(annotations[0].bbox,[1,2,3,4]);
controller.redoLastAction(annotations,candidates,history,redo,classes);
assert.deepEqual(classes,[other]);assert.equal(annotations.length,1);
controller.undoLastAction(annotations,candidates,history,redo,classes);
// Redo must remove the original ID even if its name changes and another ID reuses it.
classes[0].name='Renamed original';classes[1].name='Cell';
controller.redoLastAction(annotations,candidates,history,redo,classes);
assert.deepEqual(classes,[{...other,name:'Cell'}]);assert.equal(classes[0].id,2);
// When the original ID is already absent, Redo must leave the replacement untouched.
const absent=[{...other,name:'Cell'}],absentHistory=[],absentRedo=[deleteCommand];
controller.redoLastAction([],[],absentHistory,absentRedo,absent);
assert.deepEqual(absent,[{...other,name:'Cell'}]);
// Reusing the original ID under a different name cannot misclassify restored annotations.
const reusedId=[{...original,name:'Different name'}],idHistory=[deleteCommand],idRedo=[];
const idBefore=structuredClone({reusedId,idHistory,idRedo});
assert.throws(()=>controller.undoLastAction([],[],idHistory,idRedo,reusedId),/different name/);
assert.deepEqual({reusedId,idHistory,idRedo},idBefore);
""", text=True, encoding='utf-8', cwd=Path(__file__).resolve().parents[1], check=True)


@pytest.mark.parametrize('script_name', ['script.js', 'script-refined.js'])
def test_detection_undo_conflict_feedback_and_retry_preserve_local_state(script_name):
    script = r"""
const fs=require('fs'),assert=require('assert'),vm=require('vm');global.window={};
for(const name of ['frontendConfig','annotationCodecs','annotationController','stateStore','classManager-refined'])eval(fs.readFileSync('static/'+name+'.js','utf8'));
const store=window.SAM2StateStore,controller=window.SAM2AnnotationController,state=store.createAppState();
const image={id:'image',reviewStatus:'in_progress'},otherImage={id:'other',reviewStatus:'reviewed'};
state.images=[image,otherImage];state.currentImage=image;
for(const record of state.images)store.initializeImageState(state,record.id);
state.classes=[{id:1,name:'Cell',color:'#123456',hotkey:'c'},{id:2,name:'Other',color:'#abcdef',hotkey:'o'},
 {id:3,name:'Unrelated',color:'#654321',hotkey:'r'}];
state.annotationsByImage.set(image.id,[{id:1,class:'Cell',bbox:[1,2,3,4]}]);
state.annotationsByImage.set(otherImage.id,[{id:7,class:'Unrelated',bbox:[10,10,4,4]}]);
state.cameraOffset={x:27,y:-14};state.selectedAnnotationIds.add(1);state.selectedCandidateIds.add('candidate');
const beforeDelete=structuredClone(state.classes);
controller.deleteClassFromImage(state.classes,store.currentAnnotations(state),store.currentHistory(state),store.currentRedoHistory(state),0);
let classSaves=0,autosaves=0,feedback='',status='';const noop=()=>{};
const c={window:{confirm:()=>true},appState:state,annotationController:controller,historyClassFeedback:null,
 classManagerFeedback:{get textContent(){return feedback;}},
 normalizeClassName:window.SAM2ClassManager.normalizeClassName,
 countAnnotationsWithClass:name=>controller.countAnnotationsWithClass(state.annotationsByImage,name),
 currentAnnotations:()=>store.currentAnnotations(state),currentCandidates:()=>store.currentCandidates(state),
 currentHistory:()=>store.currentHistory(state),currentRedoHistory:()=>store.currentRedoHistory(state),
 markCurrentImageDirty:()=>{store.markCurrentImageDirty(state);autosaves++;},
 scheduleProjectClassesSave:()=>classSaves++,scheduleFolderAutosave:()=>autosaves++,renderClassControls:noop,classificationSelect:{value:'Cell'},
 showClassManagerFeedback:text=>feedback=text,clearClassManagerFeedback:()=>feedback='',
 updateStatus:text=>status=text,showToast:noop,updateAnnotationLog:noop,renderImageBrowser:noop,
 updateAnnotationInspector:noop,draw:noop,updateButtonStates:noop};
vm.createContext(c);
const source=fs.readFileSync('static/SCRIPT_NAME','utf8'),starts=[...source.matchAll(/^    (?:async )?function (\w+)\(/gm)];
const names=new Set(['commitClassRename','renameAnnotationClass','clearAllAnnotationHistory','handleUndoAction','handleRedoAction']);
for(let i=0;i<starts.length;i++)if(names.has(starts[i][1]))vm.runInContext(source.slice(starts[i].index,starts[i+1]?.index??source.length),c);
// Exact audit sequence: delete Cell, rename unused Other to Cell, then press Undo.
c.commitClassRename(0,'Cell');classSaves=0;autosaves=0;
const before=structuredClone(state);
c.handleUndoAction();
assert(feedback.includes('another class uses that name'));assert(status.includes('retry Undo'));
assert.deepEqual(state,before);assert.equal(classSaves,0);assert.equal(autosaves,0);
assert.equal(store.currentHistory(state).length,1);assert.equal(store.currentRedoHistory(state).length,0);
// Resolve the name conflict and retry the same history entry.
c.commitClassRename(0,'Other');classSaves=0;autosaves=0;
c.handleUndoAction();assert.equal(feedback,'');assert.deepEqual(state.classes,beforeDelete);
assert.equal(store.currentAnnotations(state)[0].id,1);assert.equal(classSaves,1);assert.equal(autosaves,1);
assert.deepEqual(Array.from(state.classRestoreIds),[1]);
assert(state.dirtyImages.has(image.id));assert.equal(image.reviewStatus,'in_progress');
assert.deepEqual(state.cameraOffset,{x:27,y:-14});
assert.deepEqual(state.annotationsByImage.get(otherImage.id),[{id:7,class:'Unrelated',bbox:[10,10,4,4]}]);
c.handleRedoAction();assert.deepEqual(state.classes,beforeDelete.slice(1));assert.equal(store.currentAnnotations(state).length,0);
assert.equal(classSaves,2);assert.equal(autosaves,2);assert.deepEqual(state.cameraOffset,{x:27,y:-14});
// Annotation-only Undo/Redo must not hide an unrelated failed class autosave.
feedback='Classes could not be saved: Project classes changed in another tab.';
const saveError=feedback;
c.historyClassFeedback='An earlier history conflict';
const item={id:9,class:'Unrelated',bbox:[4,4,2,2]};
store.currentAnnotations(state).push(item);
store.currentHistory(state).push({type:'create_annotations',annotationRecords:[{index:0,item:structuredClone(item)}]});
c.handleUndoAction();assert.equal(feedback,saveError);
c.handleRedoAction();assert.equal(feedback,saveError);

""".replace('SCRIPT_NAME', script_name)
    subprocess.run([_node_executable(), '-'], input=script, text=True, encoding='utf-8',
                   cwd=Path(__file__).resolve().parents[1], check=True)


def test_detection_undo_save_rejects_remapping_after_retired_class_rename(client, app_module):
    original = client.post('/api/classes', json={'classes': [{'name': 'Unused'}]}).json['classes'][0]
    assert client.post('/api/classes', json={'classes': []}).status_code == 200
    assert client.post('/api/classes', json={'classes': [original], 'restore_class_id': original['id']}).status_code == 200
    renamed = {**original, 'name': 'Renamed unused'}
    assert client.post('/api/classes', json={'classes': [renamed]}).status_code == 200
    assert client.post('/api/classes', json={'classes': []}).status_code == 200
    before = Path(app_module._project_manifest_path()).read_bytes()
    # The second Undo must reject instead of returning a fresh ID under the original name.
    revision = client.get('/api/classes').json['classes_revision']
    rejected = client.post('/api/classes', json={
        'classes': [original], 'restore_class_id': original['id'], 'classes_revision': revision,
    })
    assert rejected.status_code == 409, rejected.json
    assert Path(app_module._project_manifest_path()).read_bytes() == before
    assert client.get('/api/classes').json['classes_revision'] == revision
    # A matching retained definition can still be restored under the original ID.
    accepted = client.post('/api/classes', json={
        'classes': [renamed], 'restore_class_id': original['id'], 'classes_revision': revision,
    })
    assert accepted.status_code == 200, accepted.json
    assert accepted.json['classes'] == [renamed]


def test_queued_class_restorations_are_all_validated_before_save(client, app_module):
    originals = client.post('/api/classes', json={'classes': [{'name': 'A'}, {'name': 'B'}]}).json['classes']
    renamed = [{**item, 'name': item['name'] + ' renamed'} for item in originals]
    assert client.post('/api/classes', json={'classes': renamed}).status_code == 200
    assert client.post('/api/classes', json={'classes': []}).status_code == 200
    before = Path(app_module._project_manifest_path()).read_bytes()
    ids = [item['id'] for item in originals]
    result = client.post('/api/classes', json={
        'classes': [originals[0], renamed[1]], 'restore_class_ids': ids,
    })
    assert result.status_code == 409, result.json
    assert Path(app_module._project_manifest_path()).read_bytes() == before
    for invalid in (None, [], True, [True], [0], ['1']):
        result = client.post('/api/classes', json={'classes': renamed, 'restore_class_ids': invalid})
        assert result.status_code == 400, result.json
        assert Path(app_module._project_manifest_path()).read_bytes() == before
    result = client.post('/api/classes', json={'classes': renamed, 'restore_class_ids': ids})
    assert result.status_code == 200, result.json
    assert result.json['classes'] == renamed


@pytest.mark.parametrize('script_name', ['script.js', 'script-refined.js'])
def test_detection_class_save_carries_restored_ids_and_keeps_failed_restore_pending(script_name):
    script = r"""
const fs=require('fs'),assert=require('assert'),vm=require('vm');
const source=fs.readFileSync('static/SCRIPT_NAME','utf8');
const state={classes:[{id:1,name:'Original'},{id:2,name:'Other'}],nextClassId:3,projectClassesRevision:'before',classRestoreIds:[1,2]};
let sent,mode='reject',feedback='';
const noop=()=>{};
const c={appState:state,console,classChangesPending:true,classificationSelect:{value:'Original'},
 normalizeClassList:x=>x,renderClassControls:noop,updateButtonStates:noop,updateStatus:noop,showToast:noop,
 showClassManagerFeedback:text=>feedback=text,
 apiWorkflows:{saveClasses:async(classes,revision,restoreIds)=>{
  sent={classes:structuredClone(classes),revision,restoreIds:Array.from(restoreIds)};
  if(mode==='reject')return {ok:false,status:409,json:async()=>({error:'The original class ID could not be restored.'})};
  if(mode==='remap')return {ok:true,json:async()=>({classes:[{id:3,name:'Original'},{id:2,name:'Other'}],classes_revision:'bad',next_class_id:4})};
  return {ok:true,json:async()=>({classes:structuredClone(classes),classes_revision:'after',next_class_id:3})};
 }} };
vm.createContext(c);
const name='SCRIPT_NAME'==='script.js'?'saveProjectClasses':'persistProjectClasses';
const starts=[...source.matchAll(/^    (?:async )?function (\w+)\(/gm)],index=starts.findIndex(item=>item[1]===name);
vm.runInContext(source.slice(starts[index].index,starts[index+1].index),c);
(async()=>{
 const before=structuredClone(state);
 assert.equal(await c[name]({silent:true}),false);
 assert.deepEqual(sent.restoreIds,[1,2]);assert.equal(sent.revision,'before');assert.deepEqual(state,before);
 assert(feedback.includes('original class ID'));
 mode='remap';assert.equal(await c[name]({silent:true}),false);assert.deepEqual(state,before);
 mode='accept';assert(await c[name]({silent:true}));assert.deepEqual(Array.from(state.classRestoreIds),[]);
 assert.equal(state.classes[0].id,1);assert.equal(state.projectClassesRevision,'after');
 // Redo can remove a locally restored class before its debounced save executes.
 state.classRestoreIds=[1,2];state.classes=state.classes.filter(item=>item.id!==1);
 assert(await c[name]({silent:true}));assert.deepEqual(sent.restoreIds,[2]);assert.deepEqual(Array.from(state.classRestoreIds),[]);
})().catch(e=>{console.error(e);process.exitCode=1;});
""".replace('SCRIPT_NAME', script_name)
    subprocess.run([_node_executable(), '-'], input=script, text=True, encoding='utf-8',
                   cwd=Path(__file__).resolve().parents[1], check=True)
