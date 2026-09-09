import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_visibility_changes_only_rendering_and_hidden_hit_targets():
    node = _node_executable()
    assert node, "Node is required for canvas interaction checks"
    subprocess.run([node, "-e", r"""
const fs=require('fs'),assert=require('assert');
global.window={};
for(const file of ['frontendConfig.js','canvasGeometry.js','canvasRenderer-refined.js']) eval(fs.readFileSync('static/'+file,'utf8'));
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=name=>source.match(new RegExp('    function '+name+'\\([^\\n]*\\) \\{([\\s\\S]*?)\\n    \\}'))[1];
const candidates=[{id:1,bbox:[10,10,20,20]}],annotations=[{id:2,class:'Named',bbox:[50,50,20,20]}];
const original=JSON.stringify({candidates,annotations});
const visibility={candidates:true,annotations:true,labels:true,imageOnly:false};
const calls=[];
const ctx=new Proxy({measureText:()=>({width:12})},{get:(target,key)=>target[key]||((...args)=>calls.push([key,...args]))});
const noop=()=>{};
const inputs={candidates:{},annotations:{},labels:{},imageOnly:{}};
const state={isDrawing:false,isAwaitingChoice:false,boxEditMode:null,classes:[],cameraOffset:{x:0,y:0},cameraZoom:1,selectedCandidateIds:new Set(),selectedAnnotationIds:new Set()};
window.SAM2ManualClassPicker={sync:noop};
const bindings={updateWorkingState:noop,appState:state,visibilityInputs:inputs,overlayVisibility:visibility,document:{getElementById:()=>({})},resizeCanvasToContainer:noop,canvasContainer:{},classificationSelect:{value:''},finalizeAnnotation:noop,createClassFromName:noop,cancelManualAnnotation:noop,canvasRenderer:window.SAM2CanvasRenderer,ctx,canvas:{width:200,height:200},currentDisplayImage:()=>({}),currentCandidates:()=>candidates,currentAnnotations:()=>annotations,zoomLevelDisplay:{},getClassColor:()=>'#abcdef',window};
const draw=new Function(...Object.keys(bindings),body('draw'));
function render(){calls.length=0;draw(...Object.values(bindings));return calls.slice();}
const boxAt=x=>calls.some(c=>c[0]==='strokeRect'&&c[1]===x);
render();assert(boxAt(10));assert(boxAt(50));assert(calls.some(c=>c[0]==='fillText'));
visibility.labels=false;render();assert(boxAt(50));assert(!calls.some(c=>c[0]==='fillText'));
visibility.candidates=false;render();assert(!boxAt(10));assert(boxAt(50));
visibility.annotations=false;render();assert(!boxAt(50));
visibility.annotations=true;visibility.imageOnly=true;render();assert(!boxAt(50));assert(calls.some(c=>c[0]==='drawImage'));
visibility.imageOnly=false;render();assert(boxAt(50));assert(!boxAt(10));assert(!calls.some(c=>c[0]==='fillText'));
assert.equal(JSON.stringify({candidates,annotations}),original);
for(const name of ['findAnnotationAtPoint','findCandidateAtPoint','getSelectedResizeHandleAtPoint']) {
 visibility.imageOnly=true;
 assert.equal(new Function('overlayVisibility',body(name))(visibility),null);
}
state.isAwaitingChoice=true;render();assert(Object.values(inputs).every(input=>input.disabled));
"""], cwd=Path(__file__).resolve().parents[1], check=True)
