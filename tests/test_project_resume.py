import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_folder_bookmarks_survive_reload_with_permission_and_revision_safety():
    subprocess.run([_node_executable(), '-'], input=r"""
const assert=require('assert'),fs=require('fs');
const records=new Map(),metadata=new Map();
const indexedDB={open(){const request={};queueMicrotask(()=>{
    request.result={transaction(store,mode){
        const transaction={objectStore:()=>({
            put(value,key){const request={};queueMicrotask(()=>{records.set(key,value);transaction.oncomplete();});return request;},
            get(key){const request={};queueMicrotask(()=>{request.result=records.get(key);transaction.oncomplete();});return request;}
        })};return transaction;
    }};request.onsuccess();
});return request;}};
global.window={indexedDB,localStorage:{setItem:(key,value)=>metadata.set(key,value),getItem:key=>metadata.get(key)}};
eval(fs.readFileSync('static/frontendConfig.js','utf8'));
eval(fs.readFileSync('static/fileUtils.js','utf8'));
function directory(name,contents={}) {
    const dir={name,kind:'directory',contents,permission:'granted',requests:0,reads:0,missing:false,
        async queryPermission(){return this.permission;},async requestPermission(){this.requests++;return this.permission='granted';},
        async *values(){if(this.missing)throw Error('Folder moved');this.reads++;for(const [name,value] of Object.entries(contents))yield typeof value==='string'?this.handle(name):value;},
        handle(name){return {name,kind:'file',getFile:async()=>({name,text:async()=>contents[name]}),createWritable:async()=>{
            let pending;return {write:async text=>pending=text,close:async()=>contents[name]=pending,abort:async()=>{}};
        }};},
        async getFileHandle(name,options={}){if(!(name in contents)){if(!options.create){const e=Error();e.name='NotFoundError';throw e;}contents[name]='';}return this.handle(name);}
    };return dir;
}
const reload=()=>{eval(fs.readFileSync('static/projectFolder.js','utf8'));return window.SAM2ProjectFolder;};
(async()=>{
    const nested=directory('nested',{'same.png':'pixels','same.json':'original'});
    const first=directory('dataset',{'same.png':'other',nested});
    const second=directory('second',{'b.png':'b'});
    window.showDirectoryPicker=async()=>first;
    let folder=reload(),files=(await folder.open()).filter(window.SAM2FileUtils.isSupportedImageFile);
    const current=files.find(file=>folder.imagePath(file)==='nested/same.png');
    assert(await folder.remember('outlines',files,current,{identity:'source hash',filter:'needs_review'}));
    window.showDirectoryPicker=async()=>second;
    const other=(await folder.open()).filter(window.SAM2FileUtils.isSupportedImageFile);
    assert(await folder.remember('boxes',other,other[0],{identity:'b hash',filter:'completed'}));
    folder=reload(); // Simulate a new page, preserving only browser storage.
    const restored=await folder.restore('outlines');
    assert.equal(restored.status,'ready');assert.equal(restored.lastPath,'nested/same.png');
    assert.equal(restored.identity,'source hash');assert.equal(restored.filter,'needs_review');
    assert.notStrictEqual(restored.files.find(file=>folder.imagePath(file)==='nested/same.png'),current);
    assert.equal((await folder.restore('boxes')).lastPath,'b.png');
    assert.equal((await folder.restore('unknown')).status,'none');
    const resumed=restored.files.find(file=>folder.imagePath(file)==='nested/same.png');
    // Restoring handles cannot restore obsolete write baselines or bypass import.
    await assert.rejects(folder.write(resumed,'same.json','overwrite'),/already exists/);
    assert.equal(await folder.read(resumed,'same.json'),'original');
    nested.contents['same.json']='external edit';
    await assert.rejects(folder.write(resumed,'same.json','overwrite'),/outside/);
    assert.equal(nested.contents['same.json'],'external edit');
    first.permission='prompt';const before=first.reads;
    assert.equal((await folder.restore('outlines')).status,'permission');
    assert.equal(first.requests,0);assert.equal(first.reads,before);
    assert.equal((await folder.restore('outlines',true)).status,'ready');assert.equal(first.requests,1);
    first.permission='denied';first.requestPermission=async()=>{first.requests++;return 'denied';};
    assert.equal((await folder.restore('outlines',true)).status,'permission');assert.equal(first.reads,before+1);
    first.permission='granted';first.missing=true;
    assert.equal((await folder.restore('outlines')).status,'missing');first.missing=false;
    // A folder manually chosen during slow restoration wins.
    let release;first.queryPermission=()=>new Promise(resolve=>release=resolve);
    const pending=folder.restore('outlines');await Promise.resolve();
    await folder.open();release('granted');assert.equal((await pending).status,'cancelled');
    // The durable handle may be older than the synchronous recovery bookmark
    // if the page closed during a write. Never reopen that older folder.
    const key='microscopyStudioWorkspace:outlines',latest=JSON.parse(metadata.get(key));
    metadata.set(key,JSON.stringify({...latest,bookmarkId:'newer bookmark',updatedAt:latest.updatedAt+1,lastPath:'new-folder.png'}));
    folder=reload();const interrupted=await folder.restore('outlines');
    assert.equal(interrupted.status,'missing');assert.equal(interrupted.lastPath,'new-folder.png');
    metadata.set(key,JSON.stringify(latest));
    delete window.indexedDB;folder=reload();
    const disconnected=await folder.restore('outlines');
    assert.equal(disconnected.status,'missing');assert.equal(disconnected.lastPath,'nested/same.png');
    assert(!JSON.stringify(disconnected).includes('pixels'));
    const reopened=(await folder.open()).filter(window.SAM2FileUtils.isSupportedImageFile);
    assert.equal(await folder.remember('boxes',reopened,reopened[0]),false);
    await folder.write(reopened[0],'b.json','autosave still works');
    assert.equal(second.contents['b.json'],'autosave still works');
})().catch(error=>{console.error(error);process.exit(1);});
""", text=True, encoding='utf-8', cwd=Path(__file__).resolve().parents[1], check=True)


def test_resume_controls_request_permission_only_on_click_and_ignore_stale_restore():
    subprocess.run([_node_executable(), '-'], input=r"""
const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=name=>source.match(new RegExp('    (?:async )?function '+name+'\\([^\\n]*\\) \\{([\\s\\S]*?)\\n    \\}'))[1];
const make=new Function('folder','editor',`
const elements=new Map();const document={getElementById:id=>{if(!elements.has(id))elements.set(id,{});return elements.get(id);}};
const window={SAM2ProjectFolder:folder},appState={images:[]};
let projectSwitchPending=false,polygonEditor=editor,projectWorkspace=null,resumePending=false;
let error='';const updateStatus=text=>error=text;
function showResumeState(text,locate=false){${body('showResumeState')}}
return {resume:async function(project,requestAccess=false){${body('resumeProjectWorkspace')}},
elements,state:appState,error:()=>error};`);
(async()=>{
    const calls=[];let status='permission',opened=0,picked=0;
    const saved={lastPath:'last.png',identity:'hash',filter:'completed'};
    const folder={restore:async(id,request)=>{calls.push([id,request]);return {...saved,status,files:['last.png']};},open:async()=>{picked++;return ['last.png'];}};
    const editor={hasImages:()=>false,resume:async bookmark=>{assert.equal(bookmark.lastPath,'last.png');opened++;return true;}};
    const ui=make(folder,editor);
    await ui.resume({project_id:'one'});assert.equal(opened,0);assert.deepEqual(calls,[['one',false]]);
    assert.equal(ui.elements.get('projectResumeText').textContent,'Folder disconnected');
    assert.equal(ui.elements.get('resumeProjectFolder').textContent,'Reconnect folder');
    status='ready';await ui.resume({project_id:'one'},true);assert.equal(opened,1);
    assert(ui.elements.get('projectResumeBar').hidden);assert.equal(ui.elements.get('resumeProjectFolder').disabled,false);
    status='missing';await ui.resume({project_id:'one'});
    assert.equal(ui.elements.get('resumeProjectFolder').textContent,'Locate folder');
    await ui.resume({project_id:'one'},true);assert.equal(picked,1);assert.equal(opened,2);
    let release;folder.restore=()=>new Promise(resolve=>release=resolve);
    const pending=ui.resume({project_id:'one'});ui.state.images.push('manually loaded');
    release({...saved,status:'ready',files:['old.png']});await pending;assert.equal(opened,2);
    ui.state.images=[];folder.restore=async()=>({...saved,status:'ready',files:[]});
    editor.resume=async()=>{throw Error('Image changed');};await ui.resume({project_id:'one'});
    assert.equal(ui.error(),'Image changed');assert.equal(ui.elements.get('resumeProjectFolder').textContent,'Locate folder');
})().catch(error=>{console.error(error);process.exit(1);});
""", text=True, encoding='utf-8', cwd=Path(__file__).resolve().parents[1], check=True)


def test_detection_resumes_last_image_filter_and_blocks_changed_source():
    subprocess.run([_node_executable(), '-'], input=r"""
const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('static/script-refined.js','utf8');
const body=name=>source.match(new RegExp('    async function '+name+'\\([^\\n]*\\) \\{([\\s\\S]*?)\\n    \\}'))[1];
global.window={};eval(fs.readFileSync('static/frontendConfig.js','utf8'));eval(fs.readFileSync('static/stateStore.js','utf8'));
const make=new Function(`
const stateStore=globalThis.window.SAM2StateStore,appState=stateStore.createAppState();
appState.projectSettings={projectId:'boxes'};
let projectSwitchPending=false,loads=[],bookmarks=[],notices=[];
const window={SAM2ProjectFolder:{imagePath:file=>file.name,has:()=>true,remember:async(...args)=>bookmarks.push(args)}};
const document={getElementById:()=>({})};
const isSupportedImageFile=file=>file.name.endsWith('.png'),imageSortName=file=>file.name;
const resetState=()=>{appState.images=[];appState.currentImage=null;};
const createImageRecord=(file,unused,index)=>({id:index,file});
const initializeImageState=()=>{},renderImageBrowser=()=>{};
const imageController={normalizeQueueFilter:value=>['all','needs_review','completed'].includes(value)?value:'all'};
const refreshAnnotationMatches=async()=>{},selectImageByIndex=async(index,options)=>{loads.push([index,options]);appState.currentImage=appState.images[index];};
const showToast=text=>notices.push(text);
return {resume:async function(saved){${body('resumeDetectionWorkspace')}},
remember:async function(imageRecord=appState.currentImage){${body('rememberDetectionWorkspace')}},
state:appState,loads,bookmarks,notices};`);
(async()=>{
    const files=['b.png','a.png','c.png'].map(name=>new File([name],name));
    const digest=await crypto.subtle.digest('SHA-256',await files[0].arrayBuffer());
    const identity=Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('');
    const saved={files,lastPath:'b.png',identity,filter:'needs_review'};
    const editor=make();assert(await editor.resume(saved));
    assert.equal(editor.state.currentImage.file.name,'b.png');assert.equal(editor.state.imageQueueFilter,'needs_review');
    assert.deepEqual(editor.loads,[[1,{autoLoadAnnotations:true}]]);
    await editor.remember();assert.equal(editor.bookmarks[0][0],'boxes');assert.equal(editor.bookmarks[0][2].name,'b.png');
    assert.equal(editor.bookmarks[0][3].identity,identity);assert.equal(editor.bookmarks[0][3].filter,'needs_review');
    const changed=make();await assert.rejects(changed.resume({...saved,identity:'wrong source'}),/saved image changed/);
    assert.equal(changed.state.images.length,0);assert.equal(changed.loads.length,0);
    const missing=make();assert(await missing.resume({...saved,lastPath:'removed.png'}));
    assert.equal(missing.state.currentImage.file.name,'a.png');assert(missing.notices[0].includes('first available'));
    // A slower bookmark from the prior image cannot overwrite the new position.
    let release;const first=editor.state.images[0];first.file={name:'a.png',arrayBuffer:()=>new Promise(resolve=>release=resolve)};
    editor.state.currentImage=first;const pending=editor.remember();
    editor.state.currentImage=editor.state.images[1];await editor.remember();release(new Uint8Array([1]).buffer);await pending;
    assert.equal(editor.bookmarks.at(-1)[2].name,'b.png');assert.equal(editor.bookmarks.length,2);
})().catch(error=>{console.error(error);process.exit(1);});
""", text=True, encoding='utf-8', cwd=Path(__file__).resolve().parents[1], check=True)
