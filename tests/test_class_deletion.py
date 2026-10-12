import copy
import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable
from test_polygon_api import polygon_project  # noqa: F401


def test_detection_class_deletion_is_one_reversible_action():
    subprocess.run([_node_executable(), '-e', r"""
const fs=require('fs'),assert=require('assert');global.window={};
eval(fs.readFileSync('static/frontendConfig.js','utf8'));
eval(fs.readFileSync('static/annotationCodecs.js','utf8'));
eval(fs.readFileSync('static/annotationController.js','utf8'));
const controller=window.SAM2AnnotationController;
const classes=[{id:1,name:'Cell',color:'#123456',hotkey:'c'},{id:2,name:'Other'}];
const annotations=[{id:1,class:'Cell',contour:[[1,2],[3,4]]},{id:2,class:'Other'},{id:3,class:'Cell'}];
const original=structuredClone({classes,annotations}),history=[],redo=[],candidates=[];
const otherImage=[{id:5,class:'Cell'}];
assert.equal(controller.deleteClassFromImage(classes,annotations,history,redo,0),2);
assert.deepEqual(annotations,[original.annotations[1]]);assert.equal(classes.length,1);
assert.equal(history.length,1);assert.deepEqual(otherImage,[{id:5,class:'Cell'}]);
controller.undoLastAction(annotations,candidates,history,redo,classes);
assert.deepEqual({classes,annotations},original);
controller.redoLastAction(annotations,candidates,history,redo,classes);
assert.equal(annotations.length,1);assert.equal(classes.length,1);
controller.undoLastAction(annotations,candidates,history,redo,classes);
assert.deepEqual({classes,annotations},original);
// Removing an unused class is also reversible without clearing prior history.
classes.push({id:3,name:'Unused'});
assert.equal(controller.deleteClassFromImage(classes,annotations,history,redo,2),0);
controller.undoLastAction(annotations,candidates,history,redo,classes);
assert.equal(classes[2].name,'Unused');
"""], cwd=Path(__file__).resolve().parents[1], check=True)


def test_class_removed_on_one_image_does_not_break_another(client, request):
    headers, image, document = request.getfixturevalue('polygon_project')
    endpoint = '/api/project/segmentation'
    other = copy.deepcopy(document)
    other['image']['identity'] = 'b' * 64
    original_classes = client.get('/api/classes').get_json()['classes']
    saved = client.post(endpoint, headers=headers, json={
        'action': 'save', 'image': other['image'], 'document': other, 'revision': None,
    })
    assert saved.status_code == 200
    deleted = client.post('/api/classes', headers=headers, json={'classes': []})
    assert deleted.status_code == 200
    assert deleted.get_json()['classes'] == []
    empty = copy.deepcopy(document)
    empty['annotations'] = []
    assert client.post(endpoint, headers=headers, json={
        'action': 'save', 'image': image, 'document': empty, 'revision': None,
    }).status_code == 200
    # Reloading the project keeps the archived definition, including its stable ID.
    reopened = client.post('/api/project/projects', headers=headers, json={
        'action': 'open', 'project_id': headers['X-Project-ID'],
    })
    assert reopened.status_code == 200
    local_override = client.post(endpoint, headers=headers, json={
        'action': 'load', 'image': other['image'], 'restore_classes': False,
    })
    assert local_override.status_code == 200
    assert local_override.get_json()['classes'] == []
    loaded = client.post(endpoint, headers=headers, json={'action': 'load', 'image': other['image']})
    assert loaded.status_code == 200
    assert loaded.get_json()['document']['annotations'][0]['class_id'] == original_classes[0]['id']
    assert loaded.get_json()['classes'] == original_classes
    current = client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()
    assert current['document']['annotations'] == []
    # Undo can reactivate the original class ID and persist the original annotation.
    assert client.post('/api/classes', headers=headers, json={'classes': original_classes}).status_code == 200
    assert client.post(endpoint, headers=headers, json={
        'action': 'save', 'image': image, 'document': document, 'revision': current['revision'],
    }).status_code == 200
