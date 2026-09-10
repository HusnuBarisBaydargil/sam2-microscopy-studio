import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_class_edits_are_included_in_footer_text_and_styling():
    subprocess.run([_node_executable(), '-e', r"""
const fs=require('fs'),assert=require('assert');global.window={};
eval(fs.readFileSync('static/controlsUiController.js','utf8'));
const controller=window.SAM2ControlsUiController;
const refs=new Proxy({}, {get(target,key){
 if(!target[key]){const classes=new Set();target[key]={value:'',checked:false,classList:{toggle(name,on){on?classes.add(name):classes.delete(name);},contains:name=>classes.has(name)}};}
 return target[key];
}});
const state={dirtyImageCount:0,currentImageDirty:false,imageCount:0,currentImageIndex:-1,selectedPreprocess:'original'};
const helpers={classUiController:{syncClassControlStates(){}},preprocessLabel:x=>x};
function render(pending){controller.updateButtonStates(refs,{...state,classChangesPending:pending},helpers);}
render(false);assert.equal(refs.unsavedStateIndicator.textContent,'All changes saved');
render(true);assert.equal(refs.unsavedStateIndicator.textContent,'Unsaved class changes');
assert(refs.unsavedStateIndicator.classList.contains('dirty'));assert(!refs.unsavedStateIndicator.classList.contains('saved'));
assert(refs.unsavedStateIndicator.title.includes('not been saved'));
state.dirtyImageCount=1;state.currentImageDirty=true;render(true);
assert.equal(refs.unsavedStateIndicator.textContent,'Unsaved changes: current image · classes');
render(false);assert.equal(refs.unsavedStateIndicator.textContent,'Unsaved changes: current image');
state.dirtyImageCount=0;render(false);assert.equal(refs.unsavedStateIndicator.textContent,'All changes saved');
assert(refs.unsavedStateIndicator.classList.contains('saved'));assert(!refs.unsavedStateIndicator.classList.contains('dirty'));
"""], cwd=Path(__file__).resolve().parents[1], check=True)
