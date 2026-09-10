import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_panel_refit_and_export_format_are_presentation_only():
    subprocess.run([_node_executable(), '-e', r"""
const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=name=>source.match(new RegExp('    function '+name+'\\([^\\n]*\\) \\{([\\s\\S]*?)\\n    \\}'))[1];
let chosen='yolo',received=[],downloads=[];
const annotations=[{id:1,bbox:[10,20,30,40]}];
const state={currentImage:{name:'image.png'},classes:[],projectSettings:{annotationFormat:'csv'}};
const before=JSON.stringify({annotations,state});
const bindings={currentAnnotations:()=>annotations,appState:state,publicImageName:()=> 'image.png',
document:{getElementById:()=>({value:chosen}),createElement:()=>({click(){downloads.push(this.download);}}),body:{appendChild(){},removeChild(){}}},
annotationWorkflowController:{buildAnnotationExport:(name,items,format)=>{received.push(format);return {content:'data',mime:'text/plain'};}},
normalizeAnnotation:x=>x,Blob:class{},URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},
annotationDownloadName:(name,format)=>name+'.'+format,formatLabel:x=>x,updateStatus(){},showToast(){}};
const run=new Function(...Object.keys(bindings),body('handleExportAnnotationFile'));
for(chosen of ['yolo','coco','csv','csv_rich','voc'])run(...Object.values(bindings));
assert.deepEqual(received,['yolo','coco','csv','csv_rich','voc']);assert.equal(downloads.length,5);
assert.equal(JSON.stringify({annotations,state}),before);
const callback=source.match(/window.addEventListener\('workspace-panels-changed', \(\) => \{([\s\S]*?)\n    \}\);/)[1];
const events=[];
new Function('resizeCanvasToContainer','fitImageToView','draw',callback)(()=>events.push('resize'),()=>events.push('fit'),()=>events.push('draw'));
assert.deepEqual(events,['resize','fit','draw']);
// Success notifications are quiet, while errors still reach the toast container.
let count=0;const toast={style:{},remove(){}};
const show=new Function('message','type','duration','toastContainer','document','setTimeout',body('showToast'));
const container={appendChild(){count++;}};
show('Added box','success',3000,container,{createElement:()=>toast},()=>{});assert.equal(count,0);
show('Save failed','error',3000,container,{createElement:()=>toast},()=>{});assert.equal(count,1);
"""], cwd=Path(__file__).resolve().parents[1], check=True)
