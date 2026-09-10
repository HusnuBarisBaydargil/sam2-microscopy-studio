import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_working_state_tracks_tools_classes_and_review_without_mutating_data():
    subprocess.run([_node_executable(), "-e", r"""
const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=source.match(/    function updateWorkingState\(\) \{([\s\S]*?)\n    \}/)[1];
const elements={};let writes=0;
const document={getElementById(id){if(!elements[id]){let value='';elements[id]={style:{},dataset:{},get textContent(){return value;},set textContent(text){value=text;writes++;}};}return elements[id];}};
const state={currentImage:null,classes:[{name:'User label',color:'#abcdef'}],dirtyImages:new Set(),selectedCandidateIds:new Set(),selectedAnnotationIds:new Set()};
const visibility={imageOnly:false,candidates:true};const oneClick={checked:false};const button={setAttribute(){}};
const labels={reviewed:'Reviewed',in_progress:'In progress',unreviewed:'Unreviewed',confirmed_empty:'Confirmed empty'};
const update=new Function('appState','overlayVisibility','oneClickAcceptInput','classificationSelect','imageController','annotationSavePending','document','manualAnnotationBtn',body);
function render(saving=false){update(state,visibility,oneClick,{value:'User label'},{reviewStatusLabel:value=>labels[value]},saving,document,button);}
render();assert.equal(elements.workingReview.textContent,'Review: No image');
state.currentImage={id:'a',reviewStatus:'reviewed'};render();assert.equal(elements.workingReview.dataset.complete,'true');
const before=writes;render();assert.equal(writes,before);
state.dirtyImages.add('a');render();assert.equal(elements.workingReview.dataset.complete,'false');assert.equal(elements.workingReview.textContent,'Review: In progress');assert.equal(state.currentImage.reviewStatus,'reviewed');
render(true);assert.equal(elements.workingReview.textContent,'Review: In progress');
state.isManualMode=true;render();assert(elements.workingTool.textContent.includes('Manual box'));
state.isDrawing=true;render();assert.equal(elements.workingTool.textContent,'Tool: Drawing box');
state.isAwaitingChoice=true;render();assert(elements.workingTool.textContent.includes('Choose a class'));
state.isAwaitingChoice=false;state.isDrawing=false;state.isManualMode=false;
visibility.imageOnly=true;render();assert(elements.workingTool.textContent.includes('Inspect image'));
visibility.imageOnly=false;oneClick.checked=true;render();assert(elements.workingTool.textContent.includes('One-click accept'));
visibility.candidates=false;render();assert.equal(elements.workingTool.textContent,'Tool: Select / pan');
state.selectedCandidateIds.add(4);render();assert(elements.workingSelection.textContent.includes('1 candidate ·'));
assert.equal(elements.workingClass.textContent,'Class: User label');
assert.equal(elements.workingClass.style.borderLeftColor,'#abcdef');
"""], cwd=Path(__file__).resolve().parents[1], check=True)
