import subprocess
from pathlib import Path

import pytest
from test_frontend_canvas_renderer import _node_executable


@pytest.mark.parametrize('annotation_format', ['csv', 'csv_rich', 'yolo', 'coco', 'voc'])
def test_detection_rename_autosaves_labels_and_review_without_another_edit(annotation_format):
    script = r"""
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const timers=new Map();let nextTimer=1,format='FORMAT',disk=new Map(),writes=[],classWrites=0,failClasses=false,failDisk=false,confirmed=true;
const noop=()=>{},context={console,crypto,TextEncoder,structuredClone,Map,Set,WeakSet,JSON,Promise,
 window:{confirm:()=>confirmed,SAM2ApiWorkflows:{}},
 setTimeout:(callback,delay)=>{const id=nextTimer++;timers.set(id,{callback,delay});return id;},clearTimeout:id=>timers.delete(id)};
vm.createContext(context);
for(const module of ['frontendConfig','annotationCodecs','annotationController','classManager-refined','stateStore','fileUtils','imageController']) {
 vm.runInContext(fs.readFileSync('static/'+module+'.js','utf8'),context);
}
const store=context.window.SAM2StateStore,controller=context.window.SAM2AnnotationController,manager=context.window.SAM2ClassManager;
const codec=context.window.SAM2AnnotationCodecs;
const folder={has:()=>true,read:async(file,name)=>disk.get(file.path+'/'+name)??null,write:async(file,name,content)=>{
 if(failDisk)throw Error('Disk full');writes.push(file.path+'/'+name);disk.set(file.path+'/'+name,content);
}};
context.window.SAM2ProjectFolder=folder;
const elements=new Map(),element=id=>{if(!elements.has(id))elements.set(id,{});return elements.get(id);};
Object.assign(context,{
 stateStore:store,annotationController:controller,annotationCodecs:codec,imageController:context.window.SAM2ImageController,
 normalizeClassName:manager.normalizeClassName,normalizeClassList:manager.normalizeClassList,
 classUiController:{renderClassControls:noop},classificationSelect:{value:'Cell'},classManager:{},addClassBtn:{},
 document:{getElementById:element},filterClassList:noop,updateWorkingState:noop,renderImageBrowser:noop,
 updateButtonStates:noop,updateAnnotationLog:noop,updateAnnotationInspector:noop,updateStatus:noop,showToast:noop,draw:noop,
 currentAnnotationFormat:()=>format,imageDimensions:()=>({width:100,height:100}),normalizeAnnotation:item=>item,
 currentAnnotations:()=>store.currentAnnotations(context.appState),currentCandidates:()=>store.currentCandidates(context.appState),
 currentHistory:()=>store.currentHistory(context.appState),currentRedoHistory:()=>store.currentRedoHistory(context.appState),
 countAnnotationsWithClass:name=>controller.countAnnotationsWithClass(context.appState.annotationsByImage,name),
 showClassManagerFeedback:noop,clearClassManagerFeedback:noop,historyClassFeedback:null,
 classManagerFeedback:{textContent:''},folderLoadFailures:new WeakSet(),
 annotationSavePending:false,annotationDirectoryChangePending:false,classChangesPending:false,classSaveTimer:null,
 classSaveQueue:Promise.resolve(),folderAutosaveTimer:null,
 apiWorkflows:{saveClasses:async(classes,revision)=>{
  classWrites++;if(failClasses)return {ok:false,status:409,json:async()=>({error:'Project classes changed in another tab.'})};
  return {ok:true,json:async()=>({classes:structuredClone(classes),classes_revision:revision+'-saved',next_class_id:20})};
 }}
});
const source=fs.readFileSync('static/script-refined.js','utf8'),starts=[...source.matchAll(/^    (?:async )?function (\w+)\(/gm)];
const wanted=new Set(['commitClassRename','renameAnnotationClass','clearAllAnnotationHistory','renderClassControls',
 'scheduleProjectClassesSave','saveProjectClasses','persistProjectClasses','scheduleFolderAutosave',
 'saveImageAnnotationsToServer','saveFolderAnnotations','annotationTextHash','beginAnnotationOperation',
 'handleUndoAction','handleRedoAction','markCurrentImageDirty']);
for(let i=0;i<starts.length;i++)if(wanted.has(starts[i][1]))vm.runInContext(source.slice(starts[i].index,starts[i+1]?.index??source.length),context);
async function setup(){
 context.appState=store.createAppState();const state=context.appState;
 state.projectSettings.projectId='project-a';state.projectClassesRevision='before';state.nextClassId=20;
 state.classes=manager.normalizeClassList([{id:3,name:'Cell',color:'#123456',hotkey:'c'},
  {id:9,name:'Other',color:'#abcdef',hotkey:'o'},{id:15,name:'Unused',color:'#654321',hotkey:'r'}]);
 state.images=['a','b','empty','unaffected'].map(id=>({id,name:id+'.png',file:{path:'nested/'+id},originalImage:{width:100,height:100},
  reviewStatus:id==='empty'?'confirmed_empty':id==='unaffected'?'in_progress':'reviewed'}));
 state.currentImage=state.images[0];state.cameraOffset={x:27,y:-14};
 for(const image of state.images){
  store.initializeImageState(state,image.id);
  state.annotationsByImage.set(image.id,image.id==='empty'?[]:[{id:1,class:image.id==='unaffected'?'Other':'Cell',bbox:[10,10,20,20],type:'manual'}]);
  image.reviewClassSignature=store.reviewClassSignature(state);
 }
 timers.clear();disk=new Map();writes=[];classWrites=0;failClasses=false;failDisk=false;confirmed=true;
 context.classChangesPending=false;context.classSaveTimer=null;context.folderAutosaveTimer=null;context.classSaveQueue=Promise.resolve();
 for(const image of state.images)await context.saveFolderAnnotations(image,state.annotationsByImage.get(image.id),image.reviewStatus);
 writes=[];return state;
}
async function runAutosave(){
 const entry=[...timers].find(([id,timer])=>timer.delay===300);
 assert(entry,'A class rename must schedule folder autosave without another annotation edit.');
 timers.delete(entry[0]);await entry[1].callback();
}
function savedReview(image){return JSON.parse(disk.get(image.file.path+'/'+codec.annotationDownloadName(image.name,format)+'.review.json'));}
(async()=>{
 let state=await setup();const ids=state.classes.map(item=>item.id),boxes=structuredClone([...state.annotationsByImage]);
 const untouched=[...disk].filter(([path])=>path.startsWith('nested/unaffected/'));
 context.commitClassRename(0,'Nucleus');
 assert.deepEqual([...state.dirtyImages],['a','b','empty']);
 await runAutosave();assert.equal(classWrites,1);assert.equal(writes.length,6);assert.equal(state.dirtyImages.size,0);
 assert.deepEqual(state.classes.map(item=>item.id),ids);assert.deepEqual(state.cameraOffset,{x:27,y:-14});
 assert.deepEqual([...disk].filter(([path])=>path.startsWith('nested/unaffected/')),untouched);
 for(const image of state.images.slice(0,3)){
  const review=savedReview(image);assert.equal(review.review_status,'in_progress');
  assert.equal(review.classes[0].name,'Nucleus');assert.equal(review.classes[0].id,3);
  const text=disk.get(image.file.path+'/'+codec.annotationDownloadName(image.name,format));
  const loaded=codec.parseAnnotationFile(text,format,image,{classes:review.classes,savedClasses:review.classes}).annotations;
  assert.deepEqual(loaded.map(item=>item.class),image.id==='empty'?[]:['Nucleus']);
 }
 for(const [id,records] of boxes)assert.deepEqual(state.annotationsByImage.get(id).map(item=>item.bbox),records.map(item=>item.bbox));
 // Geometry Undo/Redo and subsequent autosave still work after the rename.
 const item=store.currentAnnotations(state)[0];item.bbox=[15,10,20,20];
 store.currentHistory(state).push({type:'geometry_edit',changes:[{id:1,oldBbox:[10,10,20,20],newBbox:[15,10,20,20]}]});
 context.handleUndoAction();await runAutosave();assert.deepEqual(item.bbox,[10,10,20,20]);assert.equal(state.dirtyImages.size,0);
 context.handleRedoAction();await runAutosave();assert.deepEqual(item.bbox,[15,10,20,20]);assert.deepEqual(state.cameraOffset,{x:27,y:-14});
 // A rename with no matching objects must still persist invalidated review decisions.
 state=await setup();context.commitClassRename(2,'Renamed unused');await runAutosave();
 assert.equal(writes.length,6);assert.equal(state.dirtyImages.size,0);assert.equal(savedReview(state.images[2]).review_status,'in_progress');
 // Cancelled, duplicate, and unchanged names must not start annotation saves.
 for(const name of ['Cell','Other','Nucleus']){
  state=await setup();if(name==='Nucleus')confirmed=false;
  context.commitClassRename(0,name);assert(![...timers.values()].some(timer=>timer.delay===300));assert.equal(writes.length,0);
 }
 // Failed palette or folder writes retain old files and dirty work for Retry save.
 for(const failure of ['classes','disk']){
  state=await setup();const before=[...disk];context.commitClassRename(0,'Nucleus');
  failClasses=failure==='classes';failDisk=failure==='disk';await runAutosave();
  assert.deepEqual([...disk],before);assert.equal(state.dirtyImages.size,3);assert.equal(state.classes[0].name,'Nucleus');
  failClasses=false;failDisk=false;context.scheduleFolderAutosave();await runAutosave();assert.equal(state.dirtyImages.size,0);
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
""".replace('FORMAT', annotation_format)
    subprocess.run([_node_executable(), '-'], input=script, text=True, encoding='utf-8',
                   cwd=Path(__file__).resolve().parents[1], check=True)
