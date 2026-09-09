import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_reserved_shortcuts_and_modifier_routing():
    subprocess.run([_node_executable(), "-e", r"""
const fs=require('fs'),assert=require('assert');global.window={};
for(const path of ['frontendConfig.js','classManager-refined.js'])eval(fs.readFileSync('static/'+path,'utf8'));
const manager=window.SAM2ClassManager;
let classes=[];for(let i=0;i<40;i++)classes.push(manager.buildNewClass('Background '+i,classes));
assert(classes.every(c=>!['b','u'].includes(c.hotkey)));
assert.equal(new Set(classes.map(c=>c.hotkey).filter(Boolean)).size,34);
assert.equal(manager.isReservedHotkey('B'),true);assert.equal(manager.isReservedHotkey('u'),true);
const legacy=manager.normalizeClassList([{id:7,name:'Saved',color:'#abcdef',hotkey:'b'}]);
assert.equal(legacy[0].id,7);assert.equal(legacy[0].hotkey,'b');assert(manager.isReservedHotkey(legacy[0].hotkey));
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=name=>source.match(new RegExp('    function '+name+'\\([^\\n]*\\) \\{([\\s\\S]*?)\\n    \\}'))[1];
let feedback='',saved=0;
const state={classes:[{name:'Saved',hotkey:'s'},{name:'Other',hotkey:'o'}]};
const edit=new Function('index','rawHotkey','appState','normalizeHotkey','classManagerLogic','showClassManagerFeedback','showToast','renderClassControls','classificationSelect','clearClassManagerFeedback','scheduleProjectClassesSave',body('commitClassHotkey'));
const noop=()=>{};
const change=value=>edit(0,value,state,manager.normalizeHotkey,manager,msg=>feedback=msg,noop,noop,{value:'Saved'},noop,()=>saved++);
change('B');assert.equal(state.classes[0].hotkey,'s');assert(feedback.includes('reserved'));assert.equal(saved,0);
change('u');assert.equal(state.classes[0].hotkey,'s');assert.equal(saved,0);
change('o');assert.equal(state.classes[0].hotkey,'s');assert.equal(saved,0);
change('');assert.equal(state.classes[0].hotkey,'');assert.equal(saved,1);
change('s');assert.equal(state.classes[0].hotkey,'s');assert.equal(saved,2);
let actions=[];
const appState={currentImage:{},classes:[{name:'Legacy B',hotkey:'b'},{name:'Legacy U',hotkey:'u'},{name:'Z class',hotkey:'z'}],selectedAnnotationIds:new Set(),isManualMode:false,isAwaitingChoice:true,choiceInfo:{}};
const bindings={projectDialog:{open:false},modalKeyboardController:{visibleModal:()=>null},samSettingsModal:{},preprocessSettingsModal:{},helpModal:{},document:{activeElement:{tagName:'BUTTON'}},appState,classManagerLogic:manager,finalizeAnnotation:name=>actions.push(name),toggleManualMode:()=>actions.push('box'),handleUndoAction:()=>actions.push('undo'),handleRedoAction:()=>actions.push('redo'),arrowKeyDelta:()=>null,processSelection:name=>actions.push(name)};
const keydown=new Function(...Object.keys(bindings),'event',body('handleKeyDown'));
function key(key,ctrlKey=false){keydown(...Object.values(bindings),{key,ctrlKey,preventDefault(){}});}
key('b');key('u');key('z',true);key('z');key('b',true);
assert.deepEqual(actions,['box','undo','undo','Z class']);
"""],cwd=Path(__file__).resolve().parents[1],check=True)
