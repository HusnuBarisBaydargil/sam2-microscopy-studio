import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_folder_writes_use_image_parent_and_detect_conflicts():
    subprocess.run([_node_executable(), "-"], input=r"""
const assert=require('assert'),fs=require('fs');
global.window={};
eval(fs.readFileSync('static/frontendConfig.js','utf8'));
eval(fs.readFileSync('static/fileUtils.js','utf8'));
function directory(name,contents={}) {
 const dir={name,kind:'directory',contents,permission:'granted',fail:false,
  async *values(){for(const [name,value] of Object.entries(contents))yield typeof value==='string'?this.handle(name):value;},
  async queryPermission(){return this.permission;},
  handle(name){return {name,kind:'file',getFile:async()=>({name,text:async()=>contents[name]}),createWritable:async()=>{
   let pending;return {write:async text=>{if(dir.fail)throw Error('Disk full');pending=text;},close:async()=>contents[name]=pending,abort:async()=>{}};
  }};},
  async getFileHandle(name,options={}){if(!(name in contents)){if(!options.create){const e=Error();e.name='NotFoundError';throw e;}contents[name]='';}return this.handle(name);}
 };return dir;
}
(async()=>{
 const sub=directory('nested',{'cell.bmp':'pixels','cell.json':'old'});
 const root=directory('dataset',{'cell.bmp':'different pixels',nested:sub,'ignore.bak':'backup'});
 window.showDirectoryPicker=async options=>{assert.equal(options.mode,'readwrite');return root;};
 eval(fs.readFileSync('static/projectFolder.js','utf8'));
 const folder=window.SAM2ProjectFolder,files=await folder.open();
 const image=files.find(f=>f.webkitRelativePath==='dataset/nested/cell.bmp');
 const other=files.find(f=>f.webkitRelativePath==='dataset/cell.bmp');
 assert(!files.some(f=>f.name.endsWith('.bak')));
 await assert.rejects(folder.write(image,'cell.json','new'),/already exists/);
 assert.equal(await folder.read(image,'cell.json'),'old');
 sub.contents['cell.json']='external peek';assert.equal(await folder.peek(image,'cell.json'),'external peek');
 await assert.rejects(folder.write(image,'cell.json','overwrite'),/outside/);
 sub.contents['cell.json']='old';
 await folder.write(image,'cell.json','new');assert.equal(sub.contents['cell.json'],'new');
 await folder.write(other,'cell.json','other');assert.equal(root.contents['cell.json'],'other');
 sub.contents['cell.json']='external';await assert.rejects(folder.write(image,'cell.json','overwrite'),/outside/);
 assert.equal(sub.contents['cell.json'],'external');
 await folder.read(image,'cell.json');sub.permission='denied';await assert.rejects(folder.write(image,'cell.json','x'),/permission/);
 sub.permission='granted';sub.fail=true;await assert.rejects(folder.write(image,'cell.json','x'),/Disk full/);assert.equal(sub.contents['cell.json'],'external');
 await assert.rejects(folder.write(image,'fresh.json','first'),/Disk full/);sub.fail=false;await folder.write(image,'fresh.json','retry');assert.equal(sub.contents['fresh.json'],'retry');
 await assert.rejects(folder.write({name:'unbound.bmp'},'unbound.json','x'),/Open folder/);
 await assert.rejects(folder.write(image,'../escape.json','x'),/Invalid/);
 root.contents['cell.png']='same stem';const ambiguous=(await folder.open()).find(f=>f.webkitRelativePath==='dataset/cell.bmp');
 await assert.rejects(folder.write(ambiguous,'cell.json','x'),/same stem/);
 window.showDirectoryPicker=undefined;await assert.rejects(folder.open(),/Chrome or Edge/);
})().catch(e=>{console.error(e);process.exit(1);});
""", text=True, encoding="utf-8", cwd=Path(__file__).resolve().parents[1], check=True)


def test_detection_folder_save_uses_selected_format_and_parent():
    subprocess.run([_node_executable(), "-"], input=r"""
const assert=require('assert'),fs=require('fs');global.window={};
for(const name of ['frontendConfig.js','annotationCodecs.js'])eval(fs.readFileSync('static/'+name,'utf8'));
const annotationCodecs=window.SAM2AnnotationCodecs;
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=source.match(/    async function saveFolderAnnotations\(imageRecord, annotations, reviewStatus\) \{([\s\S]*?)\n    \}/)[1];
let written,format='csv';const disk=new Map();window.SAM2ProjectFolder={read:async(file,name)=>disk.get(name)??null,write:async(...args)=>{disk.set(args[1],args[2]);if(!args[1].endsWith('.review.json'))written=args;}};
const appState={classes:[{id:1,name:'Cell'}]},folderLoadFailures=new WeakSet();
const save=new Function('annotationCodecs','appState','folderLoadFailures','currentAnnotationFormat','annotationTextHash',`return async function(imageRecord,annotations,reviewStatus){${body}}`)(annotationCodecs,appState,folderLoadFailures,()=>format,async()=> 'testhash');
const loadBody=source.match(/    async function loadFolderAnnotations\(imageRecord\) \{([\s\S]*?)\n    \}/)[1];
const load=new Function('annotationCodecs','appState','folderLoadFailures','currentAnnotationFormat','annotationTextHash',`return async function(imageRecord){${loadBody}}`)(annotationCodecs,appState,folderLoadFailures,()=>format,async()=> 'testhash');
(async()=>{
 const image={name:'cell with spaces.bmp',file:{},originalImage:{width:100,height:100}},annotations=[{id:1,class:'Cell',bbox:[10,10,20,20]}];
 for(format of ['csv','csv_rich','coco','voc','yolo']){
  const result=await save(image,annotations,'reviewed');assert.strictEqual(written[0],image.file);
  assert.equal(written[1],annotationCodecs.annotationDownloadName(image.name,format));assert.equal(result.count,1);
  const parsed=annotationCodecs.parseAnnotationFile(written[2],format,image,{classes:appState.classes});assert.equal(parsed.annotations.length,1);
  const reopened=await load(image);assert.equal(reopened.annotations.length,1);assert.equal(reopened.review_status,'reviewed');assert.deepEqual(reopened.classes,appState.classes);
  // The caller clears the guard only after applying a non-stale load result.
  folderLoadFailures.delete(image.file);
  await save(image,[],'confirmed_empty');assert.equal(annotationCodecs.parseAnnotationFile(written[2],format,image,{classes:appState.classes}).annotations.length,0);
 }
 folderLoadFailures.add(image.file);await assert.rejects(save(image,annotations,'reviewed'),/could not be loaded/);
})().catch(e=>{console.error(e);process.exit(1);});
""", text=True, encoding="utf-8", cwd=Path(__file__).resolve().parents[1], check=True)
