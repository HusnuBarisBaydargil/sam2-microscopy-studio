import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_explicit_open_and_new_project_dialog_modes():
    subprocess.run([_node_executable(), '-e', r"""
const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=source.match(/    async function showProjectChooser\([^\n]*\) \{([\s\S]*?)\n    \}/)[1];
const elements=new Map();
const el=id=>{if(!elements.has(id)) elements.set(id,{replaceChildren(){},appendChild(){}});return elements.get(id);};
const dialog={open:false,showModal(){this.open=true;}};
const document={getElementById:el,createElement:()=>({})};
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const choose=new AsyncFunction('document','projectDialog','projectStatus','projectSelect','projectRequest','mode',body);
(async()=>{
    for(const mode of ['new','open','all']) {
        dialog.open=false;
        await choose(document,dialog,{},el('savedProjectSelect'),async()=>({projects:[{project_id:'one',name:'Study',task_type:'instance_segmentation',class_count:2}],active_project_id:'one'}),mode);
        assert.equal(el('projectOpenSection').hidden,mode==='new');
        assert.equal(el('projectNewSection').hidden,mode==='open');
        assert.equal(el('openProjectBtn').disabled,false);
    }
})().catch(error=>{console.error(error);process.exit(1);});
"""], cwd=Path(__file__).resolve().parents[1], check=True)


def test_chooser_first_visit_refresh_task_modes_and_unavailable_storage():
    subprocess.run([_node_executable(), "-e", r"""
const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=name=>source.match(new RegExp('    function '+name+'\\([^\\n]*\\) \\{([\\s\\S]*?)\\n    \\}'))[1];
const elements=new Map();
const el=id=>{if(!elements.has(id))elements.set(id,{inert:false,hidden:false,textContent:'',classList:{toggle:(name,value)=>elements.set('mode',value)}});return elements.get(id);};
let stored=null,persistent=null,opened=0;
const storage={getItem:()=>stored,setItem:(key,value)=>stored=value};
const window={sessionStorage:storage,localStorage:{getItem:()=>persistent,setItem:(key,value)=>persistent=value},SAM2PolygonEditor:{mount:()=>({})}};
const remember=new Function('window','projectId',body('rememberProject'));
const init=new Function('document','window','rememberProject','showProjectChooser','polygonEditor','phiSafeMode','project',body('initializeProjectChooser'));
const document={getElementById:el,querySelector:el};
const run=p=>init(document,window,id=>remember(window,id),()=>opened++,null,()=>true,p);
run({project_id:'one',name:'Detection study',task_type:'bounding_box'});
assert.equal(opened,1);assert.equal(stored,'one');assert(el('segmentationProjectNotice').hidden);
run({project_id:'one',name:'Detection study',task_type:'bounding_box'});assert.equal(opened,1);
remember(window,'two');run({project_id:'two',name:'Outlines',task_type:'instance_segmentation'});
assert.equal(opened,1);assert.equal(el('activeProjectMode').textContent,'Segmentation');
assert.equal(el('segmentationProjectHeading').textContent,'Outlines');
assert.equal(el('segmentationProjectNotice').hidden,false);assert.equal(el('.main-content').inert,true);
run({project_id:'three',name:'Boxes',task_type:'bounding_box'});assert.equal(opened,2);assert.equal(el('.main-content').inert,false);
stored=null;run({project_id:'three',name:'Boxes',task_type:'bounding_box'});assert.equal(opened,2); // A new tab/browser session resumes quietly.
window.sessionStorage={getItem(){throw Error('disabled');},setItem(){throw Error('disabled');}};
window.localStorage={getItem(){throw Error('disabled');},setItem(){throw Error('disabled');}};
run({project_id:'four',name:'Private window',task_type:'bounding_box'});assert.equal(opened,3);
"""], cwd=Path(__file__).resolve().parents[1], check=True)


def test_project_creation_requires_explicit_task_choice():
    subprocess.run([_node_executable(), "-e", r"""
const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=source.match(/getElementById\('createProjectBtn'\).addEventListener\('click', \(\) => \{([\s\S]*?)\n    \}\);/)[1];
let choice=null,payload=null;const status={textContent:''};
const document={getElementById:id=>id==='newProjectName'?{value:' Test project '}:{checked:false},querySelector:()=>choice};
const create=new Function('document','projectStatus','switchProject',body);
const run=()=>create(document,status,value=>payload=value);
run();assert.equal(payload,null);assert(status.textContent.includes('Choose'));
for(const type of ['bounding_box','instance_segmentation']){choice={value:type};run();assert.deepEqual(payload,{action:'new',name:'Test project',task_type:type,reuse_classes:false});}
"""], cwd=Path(__file__).resolve().parents[1], check=True)
