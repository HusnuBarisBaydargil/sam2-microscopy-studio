import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable


def test_folder_matching_preserves_paths_formats_and_rejects_ambiguity():
    subprocess.run([_node_executable(), '-e', r"""
const fs=require('fs'),assert=require('assert');
global.window={};
eval(fs.readFileSync('static/frontendConfig.js','utf8'));
eval(fs.readFileSync('static/fileUtils.js','utf8'));
eval(fs.readFileSync('static/polygon/persistence.js','utf8'));
const match=window.SAM2PolygonPersistence.matchFolderFiles;
const file=path=>({name:path.split('/').pop(),webkitRelativePath:path});
const a=file('study/a/cell2.TIFF'), b=file('study/b/cell2.tiff'), c=file('study/a/cell10.png');
const json=file('study/a/cell2.JSON'), wrong=file('study/other/cell2.json');
let result=match([c,b,wrong,json,a,file('study/README.md')]);
assert.deepEqual(result.images,[a,c,b]);assert.equal(result.annotations.get(a),json);
assert(!result.annotations.has(b));assert(!result.annotations.has(c));
result=match([a,json,file('study/a/cell2.png')]);assert.equal(result.annotations.get(a),null);
result=match([a,json,file('study/a/cell2.json')]);assert.equal(result.annotations.get(a),null);
assert.equal(match([json]).images.length,0);
for(const extension of window.SAM2FrontendConfig.ALLOWED_IMAGE_EXTENSIONS){
    const image=file(`study/image${extension.toUpperCase()}`);
    assert.deepEqual(match([image]).images,[image]);
}
"""], cwd=Path(__file__).resolve().parents[1], check=True)
