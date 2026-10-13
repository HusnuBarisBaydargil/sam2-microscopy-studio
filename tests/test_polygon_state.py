import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_polygon_history_keeps_ids_monotonic_and_save_snapshots_independent():
    subprocess.run([_node_executable(), '-e', r"""
const fs=require('fs'),assert=require('assert');
global.window={};
eval(fs.readFileSync('static/polygon/state.js','utf8'));
eval(fs.readFileSync('static/polygon/geometry.js','utf8'));
const create=window.SAM2PolygonState.createPolygonState;
const contains=window.SAM2PolygonGeometry.geometryContains;
assert(contains({type:'rectangle',points:[[20,20],[0,0]]},[10,10]));
assert(!contains({type:'rectangle',points:[[0,0],[20,20]]},[30,10]));
assert(contains({type:'circle',points:[[10,10],[20,10]]},[10,20]));
assert(!contains({type:'circle',points:[[10,10],[20,10]]},[20,20]));
const concave={type:'polygon',points:[[0,0],[20,0],[20,5],[5,5],[5,20],[0,20]]};
assert(contains(concave,[2,10]));assert(!contains(concave,[10,10]));
const original={next_object_id:1,annotations:[]};
const state=create(original);
assert(!state.dirty);assert(!state.canUndo);
const first={id:1,class_id:4,geometry:{type:'polygon',points:[[0,0],[10,0],[10,10]]}};
state.change([first],2);assert(state.dirty);assert(state.canUndo);
first.geometry.points[0][0]=999;
assert.equal(state.document.annotations[0].geometry.points[0][0],0);
state.undo();assert.equal(state.document.annotations.length,0);assert.equal(state.document.next_object_id,2);
state.redo();assert.equal(state.document.annotations[0].id,1);
state.markSaved(state.document);assert(!state.dirty);
state.change([]);assert(state.dirty);state.undo();assert(!state.dirty);
state.change([{...state.document.annotations[0],class_id:8}]);assert.equal(state.document.annotations[0].class_id,8);
state.undo();assert.equal(state.document.annotations[0].class_id,4);
state.change([]);assert(!state.canRedo);assert.equal(original.annotations.length,0);
// Inference, acceptance, and replacement share chronological undo history.
const history=create(original);
history.setProposals([{id:1}]);assert(!history.dirty);
history.change([first],2,[]);
history.setProposals([{id:99}]);
history.undo();assert.deepEqual(history.proposals,[]);assert.equal(history.document.annotations.length,1);
history.undo();assert.deepEqual(history.proposals,[{id:1}]);assert.equal(history.document.annotations.length,0);
history.undo();assert.deepEqual(history.proposals,[]);assert(!history.canUndo);
history.redo();assert.deepEqual(history.proposals,[{id:1}]);
history.redo();assert.equal(history.document.annotations.length,1);
history.redo();assert.deepEqual(history.proposals,[{id:99}]);
history.undo();history.setProposals([{id:7}]);assert(!history.canRedo);
history.undo();assert.deepEqual(history.proposals,[]);

"""], cwd=Path(__file__).resolve().parents[1], check=True)


def test_class_label_changes_stay_dirty_without_geometry_or_review_changes():
    subprocess.run([_node_executable(), '-'], input=r"""
const assert=require('assert'),fs=require('fs');global.window={};
eval(fs.readFileSync('static/polygon/state.js','utf8'));
const original={next_object_id:2,review_status:'in_progress',annotations:[{id:1,class_id:4,
    source:'manual',edited:false,geometry:{type:'polygon',points:[[0,0],[10,0],[10,10]]}}]};
const a={id:4,name:'A',color:'#123456'},b={...a,name:'B'};
const state=window.SAM2PolygonState.createPolygonState(original);
state.change(state.document.annotations,state.document.next_object_id,state.proposals,state.document.labelme,
    {id:4,index:0,item:a,field:'name'});
assert.deepEqual(state.document,original);assert(state.dirty);
state.markSaved(state.document);assert(!state.dirty);
assert.equal(state.undo([b]).item.name,'A');assert(state.dirty);
// A new rename after an unsaved Undo must not look like the saved rename to B.
state.change(state.document.annotations,state.document.next_object_id,state.proposals,state.document.labelme,
    {id:4,index:0,item:a,field:'name'});
assert(state.dirty);state.markSaved(state.document);assert(!state.dirty);
assert.equal(state.undo([{...a,name:'C'}]).item.name,'A');assert(state.dirty);
state.markSaved(state.document);assert(!state.dirty);
assert.equal(state.redo([a]).item.name,'C');assert(state.dirty);
assert.deepEqual(state.document,original);
""", text=True, encoding='utf-8', cwd=Path(__file__).resolve().parents[1], check=True)
