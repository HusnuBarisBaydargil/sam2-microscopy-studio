import copy
import subprocess
from pathlib import Path

import pytest
from test_frontend_async_operations import HARNESS
from test_frontend_canvas_renderer import _node_executable


def test_two_detection_tabs_cannot_overwrite_a_new_class_id(client, app_module):
    other = app_module.app.test_client()
    first = client.get('/api/classes').get_json()
    second = other.get('/api/classes').get_json()
    assert first == second
    headers = {'X-Project-ID': client.get('/api/project/manifest').json['project_id']}
    class_id = first['next_class_id']
    saved = client.post('/api/classes', headers=headers, json={
        'classes': first['classes'] + [{'id': class_id, 'name': 'First tab'}],
        'classes_revision': first['classes_revision'],
    })
    assert saved.status_code == 200, saved.json
    manifest_path = Path(app_module._project_manifest_path())
    before = manifest_path.read_bytes()
    rejected = other.post('/api/classes', headers=headers, json={
        'classes': second['classes'] + [{'id': class_id, 'name': 'Second tab'}],
        'classes_revision': second['classes_revision'],
    })
    assert rejected.status_code == 409, rejected.json
    assert rejected.json['classes_conflict'] is True
    assert manifest_path.read_bytes() == before
    assert client.get('/api/classes').json == saved.json
    # After explicitly refreshing, a new class uses the next ID and a rename keeps its ID.
    current = other.get('/api/classes').json
    renamed = {**current['classes'][0], 'name': 'Renamed first tab'}
    retried = other.post('/api/classes', headers=headers, json={
        'classes': [renamed, {'id': current['next_class_id'], 'name': 'Second tab'}],
        'classes_revision': current['classes_revision'],
    })
    assert retried.status_code == 200, retried.json
    assert [(item['id'], item['name']) for item in retried.json['classes']] == [
        (class_id, 'Renamed first tab'), (class_id + 1, 'Second tab'),
    ]
    assert retried.json['classes_revision'] != current['classes_revision']


@pytest.mark.parametrize('annotation_format', ['csv', 'csv_rich', 'yolo', 'coco', 'voc'])
def test_stale_annotation_save_cannot_bypass_class_conflict(client, app_module, annotation_format):
    initial = client.get('/api/classes').json
    classes = client.post('/api/classes', json={
        'classes': [{'id': initial['next_class_id'], 'name': 'Cell'}],
        'classes_revision': initial['classes_revision'],
    }).json
    payload = {
        'image_name': 'cells.png', 'image_identity': 'cells:content',
        'image_width': 100, 'image_height': 80, 'format': annotation_format,
        'review_status': 'reviewed', 'overwrite': True,
        'classes': classes['classes'], 'classes_revision': classes['classes_revision'],
        'annotations': [{'id': 1, 'class': 'Cell', 'bbox': [1, 2, 20, 30]}],
    }
    saved = client.post('/api/annotations/save', json=payload)
    assert saved.status_code == 200, saved.json
    current = client.get('/api/classes').json
    assert current['classes_revision'] == saved.json['classes_revision']
    stale = copy.deepcopy(payload)
    stale['classes_revision'] = current['classes_revision']
    stale['classes'].append({'id': current['next_class_id'], 'name': 'Stale tab'})
    changed = client.post('/api/classes', json={
        'classes': current['classes'] + [{'id': current['next_class_id'], 'name': 'Other tab'}],
        'classes_revision': current['classes_revision'],
    })
    assert changed.status_code == 200, changed.json
    paths = [Path(app_module._project_manifest_path()),
             Path(app_module._annotation_path_for_image('cells.png', 'cells.png', 'basename', annotation_format))]
    paths.append(Path(str(paths[1]) + '.review.json'))
    before = {path: path.read_bytes() for path in paths}
    for overwrite in (False, True):
        rejected = client.post('/api/annotations/save', json={**stale, 'overwrite': overwrite})
        assert rejected.status_code == 409, rejected.json
        assert rejected.json['classes_conflict'] is True
        assert {path: path.read_bytes() for path in paths} == before
    assert client.get('/api/classes').json == changed.json


def test_class_revision_tracks_retired_ids_and_rejects_invalid_values(client, app_module):
    initial = client.get('/api/classes').json
    saved = client.post('/api/classes', json={
        'classes': [{'id': initial['next_class_id'], 'name': 'Temporary'}],
        'classes_revision': initial['classes_revision'],
    }).json
    deleted = client.post('/api/classes', json={
        'classes': [], 'classes_revision': saved['classes_revision'],
    }).json
    assert deleted['classes'] == initial['classes'] == []
    assert deleted['classes_revision'] != initial['classes_revision']
    before = Path(app_module._project_manifest_path()).read_bytes()
    stale = client.post('/api/classes', json={
        'classes': [{'id': 1, 'name': 'Different'}], 'classes_revision': initial['classes_revision'],
    })
    assert stale.status_code == 409, stale.json
    for invalid in (None, True, 1, '', []):
        response = client.post('/api/classes', json={'classes': [], 'classes_revision': invalid})
        assert response.status_code == 400, response.json
    assert Path(app_module._project_manifest_path()).read_bytes() == before


def test_detection_class_conflicts_keep_local_work_and_advance_successful_save_baselines():
    subprocess.run([_node_executable(), '-'], input=r"""
const fs=require('fs'),assert=require('assert');global.window={};
for(const name of ['frontendConfig','stateStore','classManager-refined'])eval(fs.readFileSync('static/'+name+'.js','utf8'));
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=name=>source.match(new RegExp('    (?:async )?function '+name+'\\([^\\n]*\\) \\{([\\s\\S]*?)\\n    \\}'))[1];
const make=new Function('apiWorkflows',`
const window=globalThis.window;
const appState=window.SAM2StateStore.createAppState(),image={id:'image',name:'cells.png',reviewStatus:'in_progress'};
appState.currentImage=image;appState.images=[image];appState.annotationsByImage.set(image.id,[{id:1,class:'Second tab',bbox:[1,2,3,4]}]);
appState.dirtyImages.add(image.id);appState.annotationHistoryByImage.set(image.id,[{type:'add',id:1}]);appState.cameraOffset={x:20,y:30};
let classChangesPending=false,classSaveQueue=Promise.resolve(),annotationSavePending=false,annotationDirectoryChangePending=false;
let feedback='',writes=0;
const normalizeClassList=window.SAM2ClassManager.normalizeClassList,stateStore=window.SAM2StateStore;
const classificationSelect={value:'Second tab'},renderClassControls=()=>{},updateButtonStates=()=>{},updateStatus=()=>{},showToast=()=>{};
const showClassManagerFeedback=text=>feedback=text;
const applyLoadedClasses=classes=>appState.classes=normalizeClassList(classes);
const imageDimensions=()=>({width:100,height:80}),normalizeAnnotation=x=>x,beginAnnotationOperation=()=>()=>true;
const saveFolderAnnotations=async()=>{writes++;return {review_status:'in_progress'};};
window.SAM2ProjectFolder={};
function saveProjectClasses(options={}){${body('saveProjectClasses')}}
async function persistProjectClasses({silent=false}={}){${body('persistProjectClasses')}}
return {state:appState,load:async function(){${body('loadProjectClasses')}},save:saveProjectClasses,
saveImage:async function(imageRecord){${body('saveImageAnnotationsToServer')}},
edit(name){appState.classes.push(window.SAM2ClassManager.buildNewClass(name,appState.classes,appState.nextClassId));classChangesPending=true;},
pending:()=>classChangesPending,feedback:()=>feedback,writes:()=>writes};`);
(async()=>{
let classes=[],revision='initial',nextId=1,calls=[];
const api={loadClasses:async()=>({ok:true,json:async()=>({classes:structuredClone(classes),classes_revision:revision,next_class_id:nextId})}),
saveClasses:async(input,base)=>{
 calls.push(base);if(base!==revision)return {ok:false,status:409,json:async()=>({error:'Project classes changed in another tab.',classes_conflict:true})};
 classes=structuredClone(input);revision+='-saved';nextId=classes.length+1;
 return {ok:true,json:async()=>({classes:structuredClone(classes),classes_revision:revision,next_class_id:nextId})};
}};
const first=make(api),second=make(api);assert(await first.load());assert(await second.load());
first.edit('First tab');second.edit('Second tab');
assert.equal(first.state.classes[0].id,second.state.classes[0].id);
assert(await first.save());assert.equal(await second.save(),false);
assert(second.pending());assert(second.feedback().includes('changed in another tab'));
assert.equal(classes[0].name,'First tab');assert.equal(second.state.classes[0].name,'Second tab');
const local=structuredClone(second.state);
await assert.rejects(second.saveImage(second.state.currentImage),/classes are not saved/);
assert.equal(second.writes(),0);assert.deepEqual(second.state,local);
assert.equal(second.state.projectClassesRevision,'initial');
// Successful queued saves update the baseline even when the local snapshot changes in flight.
let release,received;
api.saveClasses=(input,base)=>{received=base;return new Promise(resolve=>release=resolve);};
first.edit('Third class');const pending=first.save();await Promise.resolve();
assert.equal(received,revision);first.state.classes[0].name='Newer local name';
release({ok:true,json:async()=>({classes:structuredClone(classes),classes_revision:'new-baseline',next_class_id:10})});
assert(await pending);assert(first.pending());assert.equal(first.state.projectClassesRevision,'new-baseline');
assert.equal(first.state.nextClassId,10);assert.equal(first.state.classes[0].name,'Newer local name');
const retry=first.save();await Promise.resolve();assert.equal(received,'new-baseline');
release({ok:true,json:async()=>({classes:structuredClone(first.state.classes),classes_revision:'latest',next_class_id:10})});
assert(await retry);assert(!first.pending());assert.equal(first.state.projectClassesRevision,'latest');
})().catch(e=>{console.error(e);process.exitCode=1;});
""", text=True, encoding='utf-8', cwd=Path(__file__).resolve().parents[1], check=True)


def test_project_reset_while_saving_classes_prevents_folder_write():
    script = HARNESS.replace("'static/script.js'", "'static/script-refined.js'") + r"""
    const request=deferred();let dispatched=false;
    context.classChangesPending=true;
    context.saveProjectClasses=async()=>{await request.promise;context.classChangesPending=false;return true;};
    context.window.SAM2ProjectFolder={};
    context.saveFolderAnnotations=async()=>{dispatched=true;return {};};
    const pending=context.saveImageAnnotationsToServer(a);
    store.resetProjectState(state);
    request.resolve();assert.equal((await pending).stale,true);
    assert.equal(dispatched,false);assert.equal(context.annotationSavePending,false);
}
main().catch(error=>{console.error(error);process.exitCode=1;});
"""
    subprocess.run([_node_executable(), '-'], input=script, text=True, encoding='utf-8',
                   cwd=Path(__file__).resolve().parents[1], check=True)
