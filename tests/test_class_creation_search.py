import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_new_class_revealed_without_clearing_search_on_invalid_or_duplicate_name():
    subprocess.run([_node_executable(), "-e", r"""
const fs=require('fs'),assert=require('assert');global.window={};
for(const file of ['frontendConfig.js','classManager-refined.js'])eval(fs.readFileSync('static/'+file,'utf8'));
const manager=window.SAM2ClassManager;
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=source.match(/    function createClassFromName\([^\n]*\) \{([\s\S]*?)\n    \}/)[1];
const state={classes:[{id:1,name:'Background',hotkey:'a',color:'#abcdef'}],nextClassId:2};
const search={value:'Background'},list={scrollTop:0,scrollHeight:640};
let saves=0,selected='',visible=[];
const bindings={appState:state,normalizeClassName:manager.normalizeClassName,classManagerLogic:manager,classListSearch:search,classManager:list,quickClassInput:{value:'',focus(){}},classificationSelect:{value:'Background'},scheduleProjectClassesSave:()=>saves++,updateStatus(){},showToast(){},renderClassControls(name){selected=name;visible=state.classes.filter(c=>c.name.toLowerCase().includes(search.value.toLowerCase()));}};
const create=new Function(...Object.keys(bindings),'rawName','select',body);
const run=(name,select=true)=>create(...Object.values(bindings),name,select);
assert.equal(run('  '),null);assert.equal(search.value,'Background');assert.equal(saves,0);
assert.equal(run('Background'),'Background');assert.equal(search.value,'Background');assert.equal(state.classes.length,1);assert.equal(saves,0);
assert.equal(run('Target'),'Target');assert.equal(search.value,'');assert.equal(selected,'Target');assert(visible.some(c=>c.name==='Target'));assert.equal(list.scrollTop,list.scrollHeight);assert.equal(saves,1);
assert.equal(state.classes[0].name,'Background');assert.equal(state.classes[0].id,1);
search.value='does not match';assert.equal(run('Another target'),'Another target');assert.equal(search.value,'');assert(visible.some(c=>c.name==='Another target'));
"""],cwd=Path(__file__).resolve().parents[1],check=True)
