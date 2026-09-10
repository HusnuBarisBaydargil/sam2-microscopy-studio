import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_popup_dismissal_focus_and_shortcut_isolation():
    subprocess.run([_node_executable(), '-e', r"""
const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('static/refinedUi.js','utf8');
const start=source.indexOf('    const exportMenu =');
const end=source.indexOf("    document.getElementById('classificationSelect')",start);
const handlers={},menuHandlers={};let focused=0;
const inside={closest:()=>true},outside={};
const menu={open:true,querySelector:()=>({focus(){focused++;}}),contains:item=>item===inside,
addEventListener:(name,fn)=>menuHandlers[name]=fn};
const document={getElementById:()=>menu,activeElement:inside,addEventListener:(name,fn,capture)=>{handlers[name]=fn;if(name==='keydown')assert.equal(capture,true);}};
new Function('document',source.slice(start,end))(document);
let stopped=0,prevented=0;
handlers.keydown({key:'b',stopPropagation(){stopped++;},preventDefault(){prevented++;}});
assert.equal(stopped,1);assert.equal(prevented,0);assert(menu.open);
handlers.keydown({key:'Escape',stopPropagation(){stopped++;},preventDefault(){prevented++;}});
assert(!menu.open);assert.equal(focused,1);assert.equal(prevented,1);
menu.open=true;handlers.pointerdown({target:inside});assert(menu.open);
handlers.pointerdown({target:outside});assert(!menu.open);
menu.open=true;menuHandlers.focusout({relatedTarget:inside});assert(menu.open);
menuHandlers.focusout({relatedTarget:outside});assert(!menu.open);
menu.open=true;menuHandlers.click({target:inside});assert(!menu.open);assert.equal(focused,2);
// Opening the project dialog must retain its new focus.
document.activeElement=outside;menu.open=true;menuHandlers.click({target:inside});assert.equal(focused,2);
"""], cwd=Path(__file__).resolve().parents[1], check=True)
