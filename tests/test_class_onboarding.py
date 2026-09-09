import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_class_guidance_follows_current_list_through_creation_load_and_removal():
    subprocess.run([_node_executable(), "-e", r"""
const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=source.match(/    function renderClassControls\([^\n]*\) \{([\s\S]*?)\n    \}/)[1];
let text='',writes=0;
const summary={get textContent(){return text;},set textContent(value){text=value;writes++;}};
const state={classes:[]};const button={};const noop=()=>{};
const bindings={appState:state,document:{getElementById:()=>summary},addClassBtn:button,stateStore:{invalidateReviewsForClassChanges:noop},renderImageBrowser:noop,updateButtonStates:noop,classUiController:{renderClassControls:noop},classManager:{},classificationSelect:{value:''},filterClassList:noop,updateWorkingState:noop};
const render=new Function(...Object.keys(bindings),'preferredClassName',body);
const run=()=>render(...Object.values(bindings),'');
run();assert(text.includes('first class'));assert.equal(summary.hidden,false);assert.equal(button.textContent,'Create first class');
state.classes=[{name:'Created'}];run();assert(text.startsWith('1 class in this project.'));assert.equal(summary.hidden,true);assert(!text.includes('first class'));assert.equal(button.textContent,'Create class');
const before=writes;run();assert.equal(writes,before);
state.classes=[{name:'Loaded one'},{name:'Imported two'}];run();assert(text.startsWith('2 classes in this project.'));
state.classes.pop();run();assert(text.startsWith('1 class in this project.'));assert.equal(summary.hidden,true);
state.classes=[];run();assert(text.includes('first class'));assert.equal(summary.hidden,false);assert.equal(button.textContent,'Create first class');
"""],cwd=Path(__file__).resolve().parents[1],check=True)
