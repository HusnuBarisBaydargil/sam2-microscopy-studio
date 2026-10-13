import copy
import subprocess
from pathlib import Path

import pytest
from test_frontend_canvas_renderer import _node_executable
from test_polygon_api import polygon_project  # noqa: F401


@pytest.mark.parametrize('change', ['color', 'rename', 'hotkey', 'create', 'delete'])
def test_stale_segmentation_class_changes_preserve_other_tabs_objects(client, app_module, change):
    initial = client.get('/api/project/manifest').json
    created = client.post('/api/project/projects', headers={'X-Project-ID': initial['project_id']}, json={
        'action': 'new', 'name': 'Concurrent outlines', 'task_type': 'instance_segmentation',
    })
    assert created.status_code == 200, created.json
    headers = {'X-Project-ID': created.json['project_id']}
    first = client.post('/api/classes', headers=headers, json={'classes': [{'name': 'Cell'}]}).json
    other = app_module.app.test_client()
    stale = other.get('/api/classes', headers=headers).json
    added = client.post('/api/classes', headers=headers, json={
        'classes': first['classes'] + [{'name': 'New cell type'}], 'classes_revision': first['classes_revision'],
    })
    assert added.status_code == 200, added.json
    image = {'identity': 'c' * 64, 'width': 100, 'height': 80}
    loaded = client.post('/api/project/segmentation', headers=headers, json={'action': 'load', 'image': image})
    assert loaded.status_code == 200, loaded.json
    assert loaded.json['classes_revision'] == added.json['classes_revision']
    document = loaded.json['document']
    document['next_object_id'] = 2
    document['annotations'] = [{'id': 1, 'class_id': added.json['classes'][1]['id'], 'source': 'manual', 'edited': False,
                               'geometry': {'type': 'polygon', 'points': [[10, 10], [40, 10], [40, 40], [10, 40]]}}]
    saved = client.post('/api/project/segmentation', headers=headers, json={
        'action': 'save', 'image': image, 'document': document, 'revision': loaded.json['revision'],
    })
    assert saved.status_code == 200, saved.json
    before = Path(app_module._project_manifest_path()).read_bytes()
    attempted = copy.deepcopy(stale['classes'])
    if change == 'color':
        attempted[0]['color'] = '#abcdef'
    elif change == 'rename':
        attempted[0]['name'] = 'Renamed cell'
    elif change == 'hotkey':
        attempted[0]['hotkey'] = 'z'
    elif change == 'create':
        attempted.append({'name': 'Stale class'})
    else:
        attempted = []
    rejected = other.post('/api/classes', headers=headers, json={
        'classes': attempted, 'classes_revision': stale['classes_revision'],
    })
    assert rejected.status_code == 409, rejected.json
    assert rejected.json['classes_conflict'] is True
    assert Path(app_module._project_manifest_path()).read_bytes() == before
    assert client.get('/api/classes', headers=headers).json == added.json
    exported = client.post('/api/project/segmentation', headers=headers, json={
        'action': 'export_labelme', 'image': image, 'document': saved.json['document'], 'image_name': 'cells.png',
    })
    assert exported.status_code == 200, exported.json
    assert exported.json['labelme']['shapes'][0]['label'] == 'New cell type'
    assert client.post('/api/project/segmentation', headers=headers, json={
        'action': 'save', 'image': image, 'document': saved.json['document'], 'revision': saved.json['revision'],
    }).status_code == 200


def test_segmentation_reopen_and_import_return_paired_class_revisions(client, request):
    headers, image, document = request.getfixturevalue('polygon_project')
    before = client.get('/api/classes', headers=headers).json
    exported = client.post('/api/project/segmentation', headers=headers, json={
        'action': 'export_labelme', 'image': image, 'document': document, 'image_name': 'cells.png',
    }).json['labelme']
    assert client.post('/api/classes', headers=headers, json={
        'classes': [], 'classes_revision': before['classes_revision'],
    }).status_code == 200
    reopened = client.post('/api/project/segmentation', headers=headers, json={
        'action': 'load', 'image': image, 'labelme': exported, 'image_name': 'cells.png',
    })
    assert reopened.status_code == 200, reopened.json
    current = client.get('/api/classes', headers=headers).json
    assert reopened.json['classes'] == current['classes'] == before['classes']
    assert reopened.json['classes_revision'] == current['classes_revision']
    external = {'imagePath': 'cells.png', 'imageWidth': image['width'], 'imageHeight': image['height'],
                'shapes': [{'label': 'Imported', 'shape_type': 'polygon', 'points': [[10, 10], [30, 10], [20, 30]]}]}
    imported = client.post('/api/project/segmentation', headers=headers, json={
        'action': 'import_labelme', 'image': image, 'image_name': 'cells.png', 'labelme': external,
        'next_object_id': 2, 'revision': reopened.json['revision'],
    })
    assert imported.status_code == 200, imported.json
    current = client.get('/api/classes', headers=headers).json
    assert imported.json['classes'] == current['classes']
    assert imported.json['classes_revision'] == current['classes_revision']
    assert current['classes_revision'] != reopened.json['classes_revision']


def test_segmentation_editors_guard_all_class_mutations_and_rollback_stale_history():
    script = r"""
const fs=require('fs'),assert=require('assert'),vm=require('vm');
class Element {
 constructor(){this.attrs={};this.style={};this.children=[];this.value='';this.tagName='DIV';}
 setAttribute(k,v){this.attrs[k]=String(v);} getAttribute(k){return this.attrs[k];} hasAttribute(k){return k in this.attrs;}
 removeAttribute(k){delete this.attrs[k];} appendChild(c){this.children.push(c);} replaceChildren(...c){this.children=c;}
 querySelectorAll(){return [];} querySelector(){return null;} getBoundingClientRect(){return {left:100,top:50,bottom:250,width:200,height:200};}
 focus(){} click(){if(!this.disabled)return this.onclick();}
}
const server={classes:[{id:4,name:'Cell',color:'#123456',hotkey:'c'},{id:8,name:'Other',color:'#abcdef',hotkey:'o'}],revision:'c1',nextId:9,
 document:null,documentRevision:'d1',saves:0,calls:[]};
const reply=(data,ok=true)=>({ok,json:async()=>structuredClone(data)});
async function request(path,options){
 if(path==='api/load_image')return reply({width:100,height:100,image_url:'pixels'});
 const data=JSON.parse(options.body);
 if(path==='api/classes'){
  server.calls.push(data);
  if(Object.hasOwn(data,'classes_revision')&&data.classes_revision!==server.revision)return reply({error:'Project classes changed in another tab.',classes_conflict:true},false);
  server.classes=data.classes.map(item=>({...item,id:item.id||server.nextId++}));server.revision+='-saved';
  return reply({classes:server.classes,classes_revision:server.revision});
 }
 if(data.action==='load'){
  if(!server.document)server.document={schema_version:1,task_type:'instance_segmentation',project_id:'project',image:data.image,next_object_id:2,
   review_status:'reviewed',annotations:[{id:1,class_id:4,source:'manual',edited:false,geometry:{type:'polygon',points:[[10,10],[80,10],[80,80],[10,80]]}}]};
  return reply({document:server.document,revision:server.documentRevision,classes:server.classes,classes_revision:server.revision});
 }
 if(data.action==='import_labelme'){
  server.classes.push({id:server.nextId++,name:'Imported',color:'#654321',hotkey:'i'});server.revision+='-imported';
  return reply({document:structuredClone(server.document),classes:server.classes,classes_revision:server.revision});
 }
 if(data.action==='validate'||data.action==='save'){
  if(data.document.annotations.some(item=>!server.classes.some(cls=>cls.id===item.class_id)))return reply({error:'Unknown class ID'},false);
  if(data.action==='save'){server.saves++;server.document=structuredClone(data.document);server.documentRevision+='-saved';}
  return reply({document:data.document,revision:server.documentRevision});
 }
 throw Error('Unexpected request '+data.action);
}
function editor(){
 const elements=new Map(),el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
 const listeners={},svg=el('polygonCanvas'),stage={style:{},clientWidth:200,clientHeight:200,scrollLeft:0,scrollTop:0,addEventListener(){},removeEventListener(){}};
 svg.parentElement=stage;svg.getScreenCTM=()=>({a:2,b:0,inverse:()=>({})});
 svg.createSVGPoint=()=>({x:0,y:0,matrixTransform(){return {x:(this.x-100)/2,y:(this.y-50)/2};}});
 let captured;svg.setPointerCapture=id=>captured=id;svg.hasPointerCapture=id=>captured===id;svg.releasePointerCapture=()=>captured=null;
 const c={console,crypto,TextEncoder,structuredClone,Map,Set,Blob,FormData,Uint8Array,Option:function(text,value){this.text=text;this.value=value;},
 ResizeObserver:class{observe(){}disconnect(){}},window:{innerWidth:1200,innerHeight:800,confirm:()=>true,addEventListener(){},removeEventListener(){},SAM2ApiClient:{apiFetch:request}},
 document:{getElementById:el,createElementNS:()=>new Element(),createElement:()=>new Element(),querySelector:()=>null,addEventListener:(name,fn)=>listeners[name]=fn,removeEventListener(){}}};
 vm.createContext(c);
 for(const name of ['frontendConfig','fileUtils','canvasInteractionController','classManager-refined'])vm.runInContext(fs.readFileSync('static/'+name+'.js','utf8'),c);
 c.window.SAM2ClassUiController={renderClassControls(refs,classes,preferred){refs.classificationSelect.replaceChildren(...classes.map(cls=>new c.Option(cls.name,cls.name)));refs.classificationSelect.value=preferred;},getClassRowIndex:input=>input.rowIndex};
 for(const name of ['state','geometry','persistence','viewport','localTools'])vm.runInContext(fs.readFileSync('static/polygon/'+name+'.js','utf8'),c);
 vm.runInContext(fs.readFileSync('static/polygonEditor.js','utf8'),c);
 const mounted=c.window.SAM2PolygonEditor.mount({project_id:'project',classes:structuredClone(server.classes),classes_revision:server.revision});
 return {el,svg,stage,mounted,async load(){await el('polygonFiles').onchange({target:{files:[{name:'cells.png',arrayBuffer:async()=>new TextEncoder().encode('pixels').buffer}],value:''}});},
 async create(name){el('polygonClassName').value=name;await el('polygonClassForm').onsubmit({preventDefault(){}});},
 async edit(kind,value){const input={rowIndex:0,value,classList:{contains:name=>name==='class-'+kind+'-input'}};await el('polygonClassManager').onchange({target:input});},
 async remove(){await el('polygonClassManager').onclick({target:{closest:selector=>selector==='.class-delete-btn'?{rowIndex:0}:null}});}};
}
(async()=>{
 const a=editor(),b=editor();await a.load();await b.load();
 // Actual middle-button panning must survive rejected class mutations.
 const pan={button:1,pointerId:5,clientX:200,clientY:150,preventDefault(){},target:b.stage};
 b.stage.onpointerdown(pan);b.stage.onpointermove({...pan,clientX:230,clientY:165});b.stage.onpointerup({...pan,clientX:230,clientY:165});
 const transform=b.svg.style.transform;
 await a.create('New cell type');assert.equal(server.classes.length,3);const canonical=structuredClone(server.classes),saved=structuredClone(server.document);
 for(const [kind,value] of [['color','#ffffff'],['name','Renamed'],['hotkey','z']]){
  await b.edit(kind,value);assert(b.el('polygonStatus').textContent.includes('changed in another tab'));
  assert.deepEqual(server.classes,canonical);assert.deepEqual(server.document,saved);assert.equal(b.svg.style.transform,transform);
 }
 await b.create('Stale class');await b.remove();assert.deepEqual(server.classes,canonical);assert.deepEqual(server.document,saved);
 assert.equal(b.el('polygonObjectCount').textContent,'1');
 // The first tab can still complete and autosave an outline in its new class.
 a.el('polygonDraw').click();for(const [x,y] of [[20,20],[60,20],[40,60]])a.svg.onclick({target:a.svg,button:0,clientX:100+2*x,clientY:50+2*y});
 await a.el('polygonFinish').click();assert.equal(server.document.annotations.length,2);assert.equal(server.document.annotations[1].class_id,9);
 const c=editor();await c.load();await c.remove();assert.equal(server.document.annotations.length,1);
 const prior=structuredClone(server.document),saves=server.saves;
 const outsider=editor();await outsider.load();await outsider.create('Another class');const afterOtherTab=structuredClone(server.classes);
 await c.el('polygonUndo').click();assert(c.el('polygonStatus').textContent.includes('changed in another tab'));
 assert.deepEqual(server.document,prior);assert.equal(server.saves,saves);assert.deepEqual(server.classes,afterOtherTab);
 assert.equal(c.el('polygonUndo').disabled,false);assert.equal(c.el('polygonRedo').disabled,true);
 assert.equal(c.el('polygonObjectCount').textContent,'1');assert.equal(c.el('polygonSaveState').textContent,'Saved');
 // Fresh loads, imports, and own successful edits must advance the palette/revision together.
 const fresh=editor();await fresh.load();await fresh.edit('hotkey','z');await fresh.edit('name','Renamed');
 assert.equal(server.classes[0].name,'Renamed');await fresh.el('polygonUndo').click();assert.equal(server.classes[0].name,'Other');
 const redoDocument=structuredClone(server.document),redoSaves=server.saves;
 const redoOutsider=editor();await redoOutsider.load();await redoOutsider.create('Before redo');
 const redoPalette=structuredClone(server.classes);
 await fresh.el('polygonRedo').click();assert(fresh.el('polygonStatus').textContent.includes('changed in another tab'));
 assert.deepEqual(server.document,redoDocument);assert.equal(server.saves,redoSaves);assert.deepEqual(server.classes,redoPalette);
 assert.equal(fresh.el('polygonRedo').disabled,false);assert.equal(fresh.el('polygonUndo').disabled,true);
 await fresh.load();await fresh.edit('name','Renamed');await fresh.el('polygonUndo').click();await fresh.el('polygonRedo').click();
 assert.equal(server.classes[0].name,'Renamed');
 await fresh.el('polygonLabelmeFile').onchange({target:{files:[{size:1,text:async()=>JSON.stringify({shapes:[]})}],value:''}});
 await fresh.create('After import');assert(server.classes.some(cls=>cls.name==='After import'));
 const noImage=editor(),beforeNoImage=server.saves;await noImage.create('Before opening an image');
 assert(server.classes.some(cls=>cls.name==='Before opening an image'));assert.equal(server.saves,beforeNoImage);
 assert(server.calls.every(call=>typeof call.classes_revision==='string'));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    subprocess.run([_node_executable(), '-'], input=script, text=True, encoding='utf-8',
                   cwd=Path(__file__).resolve().parents[1], check=True)
