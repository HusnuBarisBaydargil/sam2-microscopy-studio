import ast
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import waitress

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('failure', [None, 'bind', 'fresh'])
def test_waitress_launcher_preserves_binding_and_upload_limit(monkeypatch, failure):
    source = ast.parse((ROOT / 'app.py').read_text(encoding='utf-8'))
    launcher = ast.Module(body=source.body[-1].body, type_ignores=[])
    calls = []
    events = []

    class Server:
        def run(self):
            events.append('run')

        def close(self):
            events.append('close')

    def bind(app, **kwargs):
        events.append('bind')
        if failure == 'bind':
            raise OSError('Port occupied')
        calls.append((app, kwargs))
        return Server()

    def fresh():
        events.append('fresh')
        if failure == 'fresh':
            raise OSError('Cannot archive project')

    monkeypatch.setattr(waitress, 'create_server', bind)
    monkeypatch.setenv('APP_HOST', '127.0.0.1')
    monkeypatch.setenv('APP_PORT', '5099')

    class App:
        config = {'MAX_CONTENT_LENGTH': 64 * 1024 * 1024}

    app = App()
    scope = {
        'app': app, 'os': os, '_start_fresh_project': fresh,
        '_positive_int_env': lambda key, default: int(os.environ.get(key, default))
    }
    if failure:
        with pytest.raises(OSError):
            exec(compile(launcher, 'app.py', 'exec'), scope)
    else:
        exec(compile(launcher, 'app.py', 'exec'), scope)
    if failure == 'bind':
        assert events == ['bind']
        assert calls == []
    else:
        assert events == (['bind', 'fresh', 'close'] if failure == 'fresh'
                          else ['bind', 'fresh', 'run', 'close'])
        assert calls == [(app, {'host': '127.0.0.1', 'port': 5099, 'threads': 4,
                               'max_request_body_size': 64 * 1024 * 1024})]


def test_manual_picker_limits_quick_choices_and_retains_every_class():
    node = shutil.which('node')
    if not node:
        bundled = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
        node = str(bundled) if bundled.exists() else None
    if not node:
        pytest.skip('Node unavailable')
    subprocess.run([node, '-e', r"""
const assert = require('assert');
const fs = require('fs');
global.window = {};
class Element {
    constructor(tag) {this.tagName=tag;this.children=[];this.style={};this.events={};this.attrs={};this.value='';this._text='';this.className='';}
    get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
    set textContent(value){this._text=value;this.children=[];}
    appendChild(child){child.parent=this;this.children.push(child);return child;}
    append(...children){children.forEach(c=>this.appendChild(c));}
    setAttribute(name,value){this.attrs[name]=value;}
    addEventListener(name,callback){this.events[name]=callback;}
    querySelectorAll(selector){const found=[];for(const child of this.children){if(selector[0]==='.' ? child.className.split(' ').includes(selector.slice(1)) : child.tagName===selector)found.push(child);found.push(...child.querySelectorAll(selector));}return found;}
    querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
    focus(){document.activeElement=this;}
    remove(){this.parent.children=this.parent.children.filter(c=>c!==this);}
    get offsetWidth(){return 300;}
    get offsetHeight(){return 200;}
}
global.document={createElement:tag=>new Element(tag),createTextNode:text=>{const n=new Element('#text');n.textContent=text;return n;}};
eval(fs.readFileSync('static/manualClassPicker.js','utf8'));
const container=new Element('div');container.clientWidth=360;container.clientHeight=400;
const classes=['Existing placeholder','WBC','RBC','Platelet','Lymphocyte'].map((name,i)=>({name,id:i+1,hotkey:String(i+1),color:'#abcdef'}));
let selected=null,created=null,cancelled=false;
const choice={rect:{x:340,y:350,w:10,h:20}};
const options={container,choice,classes,activeClass:'Platelet',onSelect:name=>{selected=name;},onCreate:name=>{created=name;},onCancel:()=>{cancelled=true;}};
window.SAM2ManualClassPicker.sync(options);
const panel=container.querySelector('.manual-class-picker');
const quick=panel.querySelector('.picker-classes').querySelectorAll('button');
assert.equal(quick.length,3);assert.ok(quick[0].textContent.includes('Platelet'));
quick[0].events.click();assert.equal(selected,'Platelet');
const select=panel.querySelector('select');assert.equal(select.children.length,classes.length+1);
select.value='Lymphocyte';select.events.change();assert.equal(selected,'Lymphocyte');
const button=text=>panel.querySelectorAll('button').find(b=>b.textContent===text);
button('Create class…').events.click();
const input=panel.querySelector('input');assert.equal(document.activeElement,input);
window.SAM2ManualClassPicker.sync(options);assert.equal(document.activeElement,input);
const form=panel.querySelector('form');input.value='   ';form.events.submit({preventDefault(){}});assert.equal(created,null);
input.value='Named class';form.events.submit({preventDefault(){}});assert.equal(created,'Named class');
button('Cancel').events.click();assert.equal(cancelled,true);
assert.ok(parseFloat(panel.style.left)+300<=360);assert.ok(parseFloat(panel.style.top)+200<=400);
window.SAM2ManualClassPicker.sync({...options,choice:null});assert.equal(container.querySelector('.manual-class-picker'),null);
window.SAM2ManualClassPicker.sync({...options, classes:[], choice:{rect:{x:20,y:20,w:30,h:30}}});
const emptyPanel=container.querySelector('.manual-class-picker');
assert.equal(emptyPanel.querySelector('form').hidden,false);
assert.equal(document.activeElement,emptyPanel.querySelector('input'));
assert.equal(emptyPanel.querySelector('.picker-classes').children.length,0);
const emptyForm=emptyPanel.querySelector('form');
created=null;emptyPanel.querySelector('input').value='   ';
emptyForm.events.submit({preventDefault(){}});assert.equal(created,null);
emptyPanel.querySelector('input').value='User label';
emptyForm.events.submit({preventDefault(){}});assert.equal(created,'User label');
const source=fs.readFileSync('static/script-refined.js','utf8');
const addClass=source.match(/    function handleAddClass\(\) \{([\s\S]*?)\n    \}/)[1];
const classRow={hidden:true};let focused=false;
new Function('quickClassInput','updateStatus',addClass)({closest:()=>classRow,focus:()=>{focused=true;},scrollIntoView(){}},()=>{});
assert.equal(classRow.hidden,false);assert.equal(focused,true);
const functionBody=name=>source.match(new RegExp('    (?:async )?function '+name+'\\([^\\n]*\\) \\{([\\s\\S]*?)\\n    \\}'))[1];
const state={classes:[{id:1,name:'User label'}]};let used=2,confirmed=0,saved=0;
window.confirm=()=>{confirmed++;return true;};
const noop=()=>{};
const remove=new Function('index','appState','countAnnotationsWithClass','showClassManagerFeedback','showToast','window','clearAllAnnotationHistory','clearClassManagerFeedback','scheduleProjectClassesSave','renderClassControls','classificationSelect','draw','updateButtonStates','updateStatus',functionBody('deleteClass'));
const removeClass=()=>remove(0,state,()=>used,noop,noop,window,noop,noop,()=>saved++,noop,{value:'User label'},noop,noop,noop);
removeClass();assert.equal(state.classes.length,1);assert.equal(confirmed,0);assert.equal(saved,0);
used=0;window.confirm=()=>false;removeClass();assert.equal(state.classes.length,1);
window.confirm=()=>true;removeClass();assert.equal(state.classes.length,0);assert.equal(saved,1);

(async()=>{
const appState={classes:[{id:1,name:'Before'}],nextClassId:2};
let finish;const api={saveClasses:()=>new Promise(resolve=>{finish=resolve;})};
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const persist=new AsyncFunction('appState','apiWorkflows','normalizeClassList','renderClassControls','classificationSelect','updateStatus','showToast','silent','updateButtonStates',functionBody('persistProjectClasses'));
const pending=persist(appState,api,x=>x,noop,{value:''},noop,noop,true,noop);
appState.classes=[{id:1,name:'After'}];
finish({ok:true,json:async()=>({classes:[{id:1,name:'Before'}]})});
await pending;assert.equal(appState.classes[0].name,'After');
let release;let calls=0;
const makeQueue=new Function('persistProjectClasses','let classSaveQueue=Promise.resolve(); return function(options={}) {'+functionBody('saveProjectClasses')+'};');
const save=makeQueue(()=>{calls++;return new Promise(resolve=>{release=resolve;});});
const first=save(),second=save();await Promise.resolve();assert.equal(calls,1);
release(true);await first;await Promise.resolve();assert.equal(calls,2);release(true);await second;
})().catch(error=>{console.error(error);process.exitCode=1;});

"""], cwd=ROOT, check=True)
