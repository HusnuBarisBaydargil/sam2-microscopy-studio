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


def test_detection_reopen_preserves_project_classes_and_saved_id_mapping():
    subprocess.run([_node_executable(), '-'], input=r"""
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const context={window:{SAM2ApiWorkflows:{}},assert,console,crypto,TextEncoder,structuredClone,Map,Set,WeakSet,JSON,process};
vm.createContext(context);
for(const name of ['frontendConfig','annotationCodecs','classManager-refined','stateStore','fileUtils','imageController','annotationController','annotationMatching','annotationWorkflowController']) {
    vm.runInContext(fs.readFileSync('static/'+name+'.js','utf8'),context);
}
const source=fs.readFileSync('static/script-refined.js','utf8');
const declarations=[...source.matchAll(/^    (?:async )?function (\w+)\(/gm)];
const selected=new Set(['loadFolderAnnotations','saveFolderAnnotations','annotationTextHash','applyLoadedClasses',
    'ensureClassesForAnnotations','loadServerAnnotationsForCurrentImage','applyLoadedAnnotations','setAnnotationsForImage','currentImageId']);
for(let i=0;i<declarations.length;i++)if(selected.has(declarations[i][1])) {
    vm.runInContext(source.slice(declarations[i].index,declarations[i+1]?.index??source.length),context);
}
vm.runInContext(`
const stateStore=window.SAM2StateStore,classManagerLogic=window.SAM2ClassManager;
const normalizeClassList=classManagerLogic.normalizeClassList,annotationCodecs=window.SAM2AnnotationCodecs;
const imageController=window.SAM2ImageController,annotationWorkflowController=window.SAM2AnnotationWorkflowController;
let appState,format,disk,writes,classSaves,autosaves,manifest,manifestReads,error;
const folderLoadFailures=new WeakSet(),classificationSelect={value:'Cell'};
const currentAnnotationFormat=()=>format,imageDimensions=image=>({width:100,height:100});
const normalizeAnnotation=item=>item,beginAnnotationOperation=()=>()=>true,setLoader=()=>()=>{};
const confirmReplaceUnsavedAnnotations=()=>true;
const annotationMatchModeForImage=()=> 'path',publicImageName=image=>image.name,publicAnnotationPath=value=>value;
const scheduleProjectClassesSave=()=>classSaves++,scheduleFolderAutosave=()=>autosaves++;
const renderClassControls=()=>{},draw=()=>{},updateButtonStates=()=>{},updateAnnotationLog=()=>{},renderImageBrowser=()=>{},updateMatchSummaryDisplay=()=>{},showToast=()=>{};
const updateStatus=value=>error=value;
const image={id:'image',name:'cells.png',file:{},originalImage:{width:100,height:100}};
const oldClasses=[{id:3,name:'Cell',color:'#123456',hotkey:'c'},{id:9,name:'Debris',color:'#567890',hotkey:'d'}];
const annotations=[{id:1,class:'Cell',bbox:[10,10,20,20]},{id:2,class:'Debris',bbox:[50,50,10,10]}];
window.SAM2ProjectFolder={has:()=>true,read:async(file,name)=>disk.get(name)??null,write:async(file,name,text)=>{writes++;disk.set(name,text);}};
window.SAM2ApiClient={apiFetch:async()=>{manifestReads++;return {ok:true,json:async()=>structuredClone(manifest)};}};
async function savedFile(selectedFormat,values=annotations,review='reviewed') {
    appState=stateStore.createAppState();appState.projectSettings.projectId='project-a';
    appState.classes=normalizeClassList(oldClasses);appState.nextClassId=20;
    appState.images=[image];appState.currentImage=image;stateStore.initializeImageState(appState,image.id);
    format=selectedFormat;disk=new Map();writes=0;classSaves=0;autosaves=0;manifestReads=0;error='';
    folderLoadFailures.delete(image.file);
    await saveFolderAnnotations(image,values,review);writes=0;
    manifest={project_id:'project-a',classes:[],retired_classes:[]};
}
async function reopen() {return loadServerAnnotationsForCurrentImage({silentWhenMissing:false});}
async function main() {
    for(const kind of ['csv','csv_rich','yolo','coco','voc']) {
        await savedFile(kind);
        // Reordering and editing controls must not reinterpret sparse saved numeric IDs.
        appState.classes=normalizeClassList([{...oldClasses[1],color:'#abcdef',hotkey:'b'},
            {...oldClasses[0],color:'#654321',hotkey:'n'},{id:15,name:'New class',color:'#70b7ff',hotkey:'x'}]);
        const expected=structuredClone(appState.classes),before=[...disk];
        assert(await reopen());assert.deepEqual(appState.classes,expected);assert.equal(appState.nextClassId,20);
        assert.deepEqual(appState.annotationsByImage.get(image.id).map(item=>item.class),['Cell','Debris']);
        assert.deepEqual([...disk],before);assert.equal(writes,0);assert.equal(classSaves,0);assert.equal(autosaves,0);
        assert.equal(image.reviewStatus,'in_progress'); // Taxonomy changed since this review.
        // A same-project rename follows its original ID without reviving the obsolete name.
        await savedFile(kind);
        const decodedBoxes=annotationCodecs.parseAnnotationFile(disk.get(annotationCodecs.annotationDownloadName(image.name,kind)),kind,image,{classes:oldClasses}).annotations.map(item=>item.bbox);
        appState.classes=normalizeClassList([{...oldClasses[1],color:'#abcdef',hotkey:'b'},
            {...oldClasses[0],name:'Nucleus',color:'#654321',hotkey:'n'}]);
        const renamedPalette=structuredClone(appState.classes);
        assert(await reopen());assert.deepEqual(appState.classes,renamedPalette);
        const loaded=appState.annotationsByImage.get(image.id);
        assert.deepEqual(loaded.map(item=>item.class),['Nucleus','Debris']);
        assert.deepEqual(loaded.map(item=>item.bbox),decodedBoxes);
        assert.equal(image.reviewStatus,'in_progress');assert(appState.dirtyImages.has(image.id));assert.equal(autosaves,1);
        await saveFolderAnnotations(image,loaded,image.reviewStatus);
        assert.equal(JSON.parse(disk.get(annotationCodecs.annotationDownloadName(image.name,kind)+'.review.json')).project_id,'project-a');
        assert(await reopen());assert.deepEqual(appState.classes,renamedPalette);
        assert.deepEqual(appState.annotationsByImage.get(image.id).map(item=>item.class),['Nucleus','Debris']);
    }
    // Colors, shortcuts, and ordering alone do not invalidate a completed review.
    await savedFile('yolo');appState.classes=normalizeClassList([{...oldClasses[1],hotkey:'b'},{...oldClasses[0],color:'#654321'}]);
    assert(await reopen());assert.equal(image.reviewStatus,'reviewed');assert.equal(writes,0);
    // Legacy sidecars remain readable when their ID/name mapping is unambiguous.
    await savedFile('yolo');const legacyName=annotationCodecs.annotationDownloadName(image.name,format)+'.review.json';
    const validLegacy=JSON.parse(disk.get(legacyName));delete validLegacy.project_id;disk.set(legacyName,JSON.stringify(validLegacy));
    appState.classes=normalizeClassList([{...oldClasses[1],hotkey:'b'}, {...oldClasses[0],color:'#654321'},
        {id:15,name:'New class',color:'#70b7ff',hotkey:'x'}]);
    const validLegacyPalette=structuredClone(appState.classes);
    assert(await reopen());assert.deepEqual(appState.classes,validLegacyPalette);
    assert.deepEqual(appState.annotationsByImage.get(image.id).map(item=>item.class),['Cell','Debris']);assert.equal(writes,0);
    // Empty files must not bring deleted, unused palette entries back.
    await savedFile('csv',[],'confirmed_empty');appState.classes=normalizeClassList([oldClasses[0]]);
    assert(await reopen());assert.deepEqual(appState.classes,normalizeClassList([oldClasses[0]]));assert.equal(image.reviewStatus,'unreviewed');
    // Referenced retired IDs use current retained definitions, not stale sidecar controls/names.
    await savedFile('yolo',[annotations[1]]);appState.classes=normalizeClassList([oldClasses[0]]);
    manifest.classes=structuredClone(appState.classes);
    const retained={...oldClasses[1],name:'Retained debris',color:'#abcdef',hotkey:'b'};
    manifest.retired_classes=[retained];
    assert(await reopen());assert.equal(manifestReads,1);assert.equal(classSaves,1);
    assert.deepEqual(appState.classes[1],retained);assert.equal(appState.annotationsByImage.get(image.id)[0].class,'Retained debris');
    assert.equal(appState.classes[1].id,9);
    // Legacy ambiguous identities fail closed; newer definitions remain intact.
    await savedFile('yolo');const name=annotationCodecs.annotationDownloadName(image.name,format)+'.review.json';
    const metadata=JSON.parse(disk.get(name));delete metadata.project_id;disk.set(name,JSON.stringify(metadata));
    appState.classes=normalizeClassList([{...oldClasses[0],name:'Nucleus'},oldClasses[1]]);
    const legacyPalette=structuredClone(appState.classes),legacyBytes=[...disk];
    assert.equal(await reopen(),false);assert(error.includes('Legacy class mapping'));
    assert.deepEqual(appState.classes,legacyPalette);assert.deepEqual([...disk],legacyBytes);assert.equal(writes,0);
    // Missing legacy IDs must not be silently recreated under a fresh class identity.
    for(const kind of ['csv','csv_rich','yolo','coco','voc']) {
        await savedFile(kind,[annotations[1]]);
        const legacyPath=annotationCodecs.annotationDownloadName(image.name,kind)+'.review.json';
        const missingLegacy=JSON.parse(disk.get(legacyPath));delete missingLegacy.project_id;
        disk.set(legacyPath,JSON.stringify(missingLegacy));
        appState.classes=normalizeClassList([oldClasses[0]]);
        manifest.retired_classes=[oldClasses[1]];
        const palette=structuredClone(appState.classes),bytes=[...disk],nextId=appState.nextClassId;
        assert.equal(await reopen(),false);assert(error.includes('Legacy class mapping'));
        assert.deepEqual(appState.classes,palette);assert.equal(appState.nextClassId,nextId);
        assert.deepEqual([...disk],bytes);assert.equal(writes,0);assert.equal(classSaves,0);assert.equal(autosaves,0);
        assert.equal(appState.annotationsByImage.get(image.id).length,0);
    }
    // A known foreign project decodes by its own names; coincident IDs are not a rename.
    await savedFile('yolo',[annotations[0]]);appState.projectSettings.projectId='project-b';
    appState.classes=normalizeClassList([{id:3,name:'Different target',color:'#abcdef',hotkey:'n'}]);
    assert(await reopen());assert.equal(appState.classes[0].name,'Different target');assert.equal(appState.classes[0].id,3);
    assert.equal(appState.annotationsByImage.get(image.id)[0].class,'Cell');assert.equal(image.reviewStatus,'in_progress');
    assert(appState.classes.find(item=>item.name==='Cell').id>=20);assert.equal(writes,0);
    // Unknown same-project IDs must not silently become fresh identities.
    await savedFile('csv',[annotations[1]]);appState.classes=normalizeClassList([oldClasses[0]]);
    const unknownPalette=structuredClone(appState.classes);
    assert.equal(await reopen(),false);assert(error.includes('no longer defined'));
    assert.deepEqual(appState.classes,unknownPalette);assert.equal(writes,0);
    // Retained name collisions and stale project replies cannot partially update the palette.
    await savedFile('csv',[annotations[1]]);appState.classes=normalizeClassList([oldClasses[0]]);
    manifest.retired_classes=[{...oldClasses[1],name:'Cell'}];
    assert.equal(await reopen(),false);assert(error.includes('another class uses that name'));assert.equal(writes,0);
    assert.deepEqual(appState.classes,normalizeClassList([oldClasses[0]]));
    manifest.project_id='project-b';assert.equal(await reopen(),false);assert(error.includes('active project changed'));
    assert.deepEqual(appState.classes,normalizeClassList([oldClasses[0]]));
    // Full supported names sharing a 64-character prefix survive folder autosave and reopen.
    for(const kind of ['csv','csv_rich','yolo','coco','voc']) {
        await savedFile(kind);
        const prefix='Microscopy '+ 'x'.repeat(53),names=[prefix+'a'.repeat(63)+'A',prefix+'a'.repeat(63)+'B'];
        const palette=normalizeClassList(oldClasses.map((item,index)=>({...item,name:names[index]})));
        appState.classes=palette;const values=annotations.map((item,index)=>({...item,class:names[index]}));
        await saveFolderAnnotations(image,values,'reviewed');writes=0;classSaves=0;autosaves=0;
        appState.classes=palette.slice().reverse();
        const expected=structuredClone(appState.classes);
        assert(await reopen());assert.deepEqual(appState.classes,expected);
        assert.deepEqual(appState.annotationsByImage.get(image.id).map(item=>item.class),names);
        assert.equal(image.reviewStatus,'reviewed');assert.equal(classSaves,0);assert.equal(autosaves,0);assert.equal(writes,0);
        assert.equal(appState.classes.length,2);assert.equal(appState.nextClassId,20);
    }
    // Reject unsupported names before either annotation or review sidecar is written.
    for(const kind of ['csv','csv_rich','yolo','coco','voc']) {
        await savedFile(kind);const bytes=[...disk],before=structuredClone(appState);
        const name='x'.repeat(129),values=[{...annotations[0],class:name}];
        await assert.rejects(saveFolderAnnotations(image,values,'reviewed'),/cannot exceed 128 characters/);
        assert.equal(writes,0);assert.deepEqual([...disk],bytes);assert.deepEqual(appState,before);
    }
    // Complete COCO names must not create a spurious project class after a rename.
    appState=stateStore.createAppState();appState.projectSettings.projectId='project-a';
    const longName='Microscopy cell '+ 'a'.repeat(70),renamedLong='Reviewed cell '+ 'b'.repeat(70);
    appState.classes=normalizeClassList([{...oldClasses[0],name:longName}]);appState.nextClassId=20;
    appState.images=[image];appState.currentImage=image;stateStore.initializeImageState(appState,image.id);
    format='coco';disk=new Map();writes=0;classSaves=0;autosaves=0;folderLoadFailures.delete(image.file);
    await saveFolderAnnotations(image,[{...annotations[0],class:longName}],'reviewed');writes=0;
    appState.classes=normalizeClassList([{...oldClasses[0],name:renamedLong}]);
    assert(await reopen());assert.equal(appState.classes.length,1);
    assert.equal(appState.annotationsByImage.get(image.id)[0].class,renamedLong);assert.equal(classSaves,0);
    const external={images:[{id:1,file_name:image.name,width:100,height:100}],categories:[{id:3,name:'External label'}],
        annotations:[{id:1,image_id:1,category_id:3,bbox:[10,10,20,20]}]};
    assert.equal(annotationCodecs.parseAnnotationFile(JSON.stringify(external),'coco',image,{classes:appState.classes}).annotations[0].class,'External label');
}
main().catch(error=>{console.error(error);process.exitCode=1;});`,context);
""", text=True, encoding='utf-8', cwd=Path(__file__).resolve().parents[1], check=True)


def test_detection_folder_save_uses_selected_format_and_parent():
    subprocess.run([_node_executable(), "-"], input=r"""
const assert=require('assert'),fs=require('fs');global.window={};
for(const name of ['frontendConfig.js','annotationCodecs.js','classManager-refined.js','stateStore.js'])eval(fs.readFileSync('static/'+name,'utf8'));
const annotationCodecs=window.SAM2AnnotationCodecs;
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=source.match(/    async function saveFolderAnnotations\(imageRecord, annotations, reviewStatus\) \{([\s\S]*?)\n    \}/)[1];
let written,format='csv';const disk=new Map();window.SAM2ProjectFolder={read:async(file,name)=>disk.get(name)??null,write:async(...args)=>{disk.set(args[1],args[2]);if(!args[1].endsWith('.review.json'))written=args;}};
const appState={classes:[{id:1,name:'Cell',color:'#39d353',hotkey:'c'}],projectSettings:{projectId:'project-a'}},folderLoadFailures=new WeakSet();
const save=new Function('annotationCodecs','appState','folderLoadFailures','currentAnnotationFormat','annotationTextHash',`return async function(imageRecord,annotations,reviewStatus){${body}}`)(annotationCodecs,appState,folderLoadFailures,()=>format,async()=> 'testhash');
const loadBody=source.match(/    async function loadFolderAnnotations\(imageRecord\) \{([\s\S]*?)\n    \}/)[1];
const load=new Function('annotationCodecs','appState','folderLoadFailures','currentAnnotationFormat','annotationTextHash','normalizeClassList','stateStore',`return async function(imageRecord){${loadBody}}`)(annotationCodecs,appState,folderLoadFailures,()=>format,async()=> 'testhash',window.SAM2ClassManager.normalizeClassList,window.SAM2StateStore);
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
