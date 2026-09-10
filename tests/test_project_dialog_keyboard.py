import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_project_dialog_isolates_keyboard_and_closed_workspace_still_works():
    subprocess.run([_node_executable(), "-e", r"""
const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=source.match(/    function handleKeyDown\(event\) \{([\s\S]*?)\n    \}/)[1];
const dialog={open:true};
const isolated=new Function('projectDialog','event',body);
// No workspace bindings are provided: any attempt to access one fails this test.
for(const key of ['Delete','Backspace','b','u','z','y','ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Escape','Tab','Enter']) {
    let prevented=false;
    isolated(dialog,{key,ctrlKey:key==='z'||key==='y',preventDefault(){prevented=true;}});
    assert.equal(prevented,false,`${key}: native dialog handling must remain available`);
}
const calls=[];
const state={classes:[],currentImage:{},selectedAnnotationIds:new Set([1]),isManualMode:false};
const bindings={classManagerLogic:{isReservedHotkey:key=>['b','u'].includes(key.toLowerCase())},projectDialog:dialog,modalKeyboardController:{visibleModal:()=>null},samSettingsModal:{},preprocessSettingsModal:{},helpModal:{},document:{activeElement:{tagName:'BUTTON'}},appState:state,toggleManualMode:()=>calls.push('manual'),annotationController:{deleteAnnotationsByIds:()=>{calls.push('delete');return [];}},currentAnnotations:()=>[],currentCandidates:()=>[],currentHistory:()=>[],currentRedoHistory:()=>[],handleUndoAction:()=>calls.push('undo'),handleRedoAction:()=>calls.push('redo'),arrowKeyDelta:key=>key==='ArrowRight'?{dx:1,dy:0}:null,nudgeSelectedAnnotations:()=>calls.push('nudge')};
const handler=new Function(...Object.keys(bindings),'event',body);
const event=key=>({key,ctrlKey:key==='z'||key==='y',preventDefault(){}});
for(const key of ['b','Delete','u','z','y','ArrowRight']) handler(...Object.values(bindings),event(key));
assert.deepEqual(calls,[]);
dialog.open=false;
for(const key of ['b','Delete','u','z','y','ArrowRight']) handler(...Object.values(bindings),event(key));
assert.deepEqual(calls,['manual','delete','undo','undo','redo','nudge']);
// Keep the existing cancellation guard while a project switch is being saved.
const cancelBody=source.match(/projectDialog.addEventListener\('cancel', event => \{([^}]+)\}/)[1];
let prevented=false;
new Function('projectSwitchPending','event',cancelBody)(true,{preventDefault(){prevented=true;}});
assert(prevented);
prevented=false;
new Function('projectSwitchPending','event',cancelBody)(false,{preventDefault(){prevented=true;}});
assert(!prevented);
"""],cwd=Path(__file__).resolve().parents[1],check=True)
