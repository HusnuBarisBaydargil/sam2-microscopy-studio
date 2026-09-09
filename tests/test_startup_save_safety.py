import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_failed_class_save_warns_before_close_and_retry_clears_pending():
    subprocess.run([_node_executable(), '-e', r"""
const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=name=>source.match(new RegExp('    (?:async )?function '+name+'\\([^\\n]*\\) \\{([\\s\\S]*?)\\n    \\}'))[1];
const make=new Function('apiWorkflows', `
let classChangesPending=true;
const appState={classes:[{id:1,name:'Cell'}],nextClassId:2};
const normalizeClassList=x=>x,renderClassControls=()=>{},classificationSelect={value:''};
let feedback='';const showClassManagerFeedback=m=>feedback=m;
let displayedPending=null;const updateButtonStates=()=>{displayedPending=classChangesPending;},updateStatus=()=>{},showToast=()=>{},unsavedImageCount=()=>0;
return {save:async function({silent=true}={}){${body('persistProjectClasses')}},
unload:function(event){${body('handleBeforeUnload')}},pending:()=>classChangesPending,
feedback:()=>feedback,displayed:()=>displayedPending,state:appState};`);
(async()=>{
let fail=true,resolve;
const api={saveClasses:async classes=>fail ? {ok:false,statusText:'Unavailable'} : {ok:true,json:async()=>({classes})}};
const editor=make(api);
const blocked=()=>{let prevented=false;editor.unload({preventDefault(){prevented=true;}});return prevented;};
assert(blocked());assert.equal(await editor.save(),false);assert(blocked());assert.equal(editor.displayed(),true);
assert(editor.feedback().includes('edit a class to retry'));
fail=false;assert.equal(await editor.save(),true);assert(!blocked());assert.equal(editor.displayed(),false);
api.saveClasses=()=>new Promise(r=>resolve=r);
const newer=make(api),pending=newer.save();newer.state.classes[0].name='Changed during save';
resolve({ok:true,json:async()=>({classes:[{id:1,name:'Cell'}]})});await pending;
assert(newer.pending());assert.equal(newer.displayed(),true);assert.equal(newer.state.classes[0].name,'Changed during save');
})().catch(e=>{console.error(e);process.exitCode=1;});
"""], cwd=Path(__file__).resolve().parents[1], check=True)


def test_startup_disables_editing_until_project_load_succeeds():
    subprocess.run([_node_executable(), '-e', r"""
const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=source.match(/    async function initializeApp\(\) \{([\s\S]*?)\n    \}/)[1];
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
(async()=>{
for(const failure of ['manifest','settings','classes',null]){
const workspace={inert:false},button={disabled:true},label={};let message='',finish;
const bindings={document:{querySelector:()=>workspace,getElementById:id=>id==='manageProjectsBtn'?button:label},
window:{SAM2ApiClient:{apiFetch:()=>new Promise(r=>finish=r),setProjectId:()=>{}}},
renderSamSettingsPanel:()=>{},syncPreprocessSettingsInputs:()=>{},resetState:()=>{},renderClassControls:()=>{},
loadProjectSettings:async()=>failure!=='settings',loadProjectClasses:async()=>failure!=='classes',
resizeCanvasToContainer:()=>{},draw:()=>{},updateButtonStates:()=>{},updateStatus:m=>message=m};
const init=new AsyncFunction(...Object.keys(bindings),body);
const pending=init(...Object.values(bindings));assert(workspace.inert);assert(button.disabled);
finish({ok:failure!=='manifest',json:async()=>({project_id:'project',name:'Project'})});await pending;
assert.equal(workspace.inert,Boolean(failure));assert.equal(button.disabled,Boolean(failure));
if(failure)assert(message.includes('editing is disabled'));else assert.equal(label.textContent,'Project');
}
})().catch(e=>{console.error(e);process.exitCode=1;});
"""], cwd=Path(__file__).resolve().parents[1], check=True)
