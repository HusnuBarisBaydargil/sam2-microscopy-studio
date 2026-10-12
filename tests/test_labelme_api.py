import copy
import json
from pathlib import Path

import pytest
from test_polygon_api import polygon_project as _polygon_project

polygon_project = _polygon_project


def labelme(image):
    return {'version': '5.7.0', 'imagePath': 'cells.tiff', 'imageData': None,
            'imageWidth': image['width'], 'imageHeight': image['height'], 'flags': {'checked': True},
            'shapes': [{'label': 'Imported cell', 'shape_type': 'polygon', 'flags': {'occluded': True},
                        'group_id': 42, 'description': 'preserve', 'points': [[10, 10], [50, 10], [50, 40], [10, 40]]}]}


@pytest.mark.parametrize("kind", ["polygon", "rectangle", "circle"])
def test_import_classes_save_reopen_and_export(client, polygon_project, app_module, kind):
    headers, image, old = polygon_project
    endpoint = '/api/project/segmentation'
    raw = labelme(image)
    if kind != 'polygon':
        raw['shapes'][0].update(shape_type=kind, points=[[30, 30], [40, 40]])
    result = client.post(endpoint, headers=headers, json={'action': 'import_labelme', 'image': image,
        'image_name': 'cells.tiff', 'next_object_id': old['next_object_id'], 'revision': None, 'labelme': raw})
    assert result.status_code == 200, result.get_json()
    result = result.get_json()
    assert [c['name'] for c in result['classes']] == ['Target', 'Imported cell']
    assert len({c['color'] for c in result['classes']}) == 2
    doc = result['document']
    assert doc['annotations'][0]['id'] == old['next_object_id']
    assert client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()['document']['annotations'] == []
    saved = client.post(endpoint, headers=headers, json={'action': 'save', 'image': image, 'document': doc,
                                                       'image_name': 'cells.tiff', 'revision': None})
    assert saved.status_code == 200, saved.get_json()
    stored = json.loads(next(Path(app_module._annotation_dir()).glob('*.studio.json')).read_text())
    assert stored['imagePath'] == 'cells.tiff'
    assert stored['shapes'][0]['label'] == 'Imported cell'
    loaded = client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()
    assert loaded['document'] == saved.get_json()['document']
    exported = client.post(endpoint, headers=headers, json={'action': 'export_labelme', 'image': image,
                              'document': loaded['document'], 'image_name': 'cells.tiff'}).get_json()['labelme']
    for key in ('points', 'flags', 'group_id', 'description'):
        assert exported['shapes'][0][key] == raw['shapes'][0][key]
    assert exported['shapes'][0]['shape_type'] == kind
    assert exported['flags'] == {'checked': True}


def test_rejected_import_does_not_change_classes_or_annotations(client, polygon_project):
    headers, image, doc = polygon_project
    endpoint = '/api/project/segmentation'
    saved = client.post(endpoint, headers=headers, json={'action': 'save', 'image': image, 'document': doc, 'revision': None}).get_json()
    before_classes = client.get('/api/project/manifest').get_json()['classes']
    for kind in ('ellipse', 'line', 'mask'):
        raw = labelme(image)
        raw['shapes'].append({**raw['shapes'][0], 'shape_type': kind})
        response = client.post(endpoint, headers=headers, json={'action': 'import_labelme', 'image': image,
            'image_name': 'cells.tiff', 'next_object_id': 2, 'revision': saved['revision'], 'labelme': raw})
        assert response.status_code == 400
        assert 'Unsupported Labelme shapes' in response.get_json()['error']
    response = client.post(endpoint, headers=headers, json={'action': 'import_labelme', 'image': image,
        'image_name': 'cells.tiff', 'next_object_id': 2, 'revision': 'stale', 'labelme': labelme(image)})
    assert response.status_code == 409
    assert client.get('/api/project/manifest').get_json()['classes'] == before_classes
    assert client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()['document'] == saved['document']


def test_labelme_export_honors_phi_safe_filenames(client, polygon_project, app_module, monkeypatch):
    headers, image, doc = polygon_project
    monkeypatch.setattr(app_module, 'PHI_SAFE_MODE', True)
    response = client.post('/api/project/segmentation', headers=headers, json={'action': 'export_labelme',
        'image': image, 'document': doc, 'image_name': 'patient-name.tif'})
    assert response.status_code == 200
    assert 'patient-name' not in json.dumps(response.get_json())
    assert response.get_json()['labelme']['imagePath'].endswith('.tif')


def test_legacy_api_file_is_read_then_migrated_only_on_save(client, polygon_project, app_module):
    headers, image, doc = polygon_project
    directory = Path(app_module._annotation_dir())
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (image['identity'] + '.studio.json')
    path.write_text(json.dumps(doc))
    before = path.read_bytes()
    loaded = client.post('/api/project/segmentation', headers=headers, json={'action': 'load', 'image': image}).get_json()
    assert path.read_bytes() == before
    changed = copy.deepcopy(loaded['document'])
    changed['annotations'][0]['edited'] = True
    saved = client.post('/api/project/segmentation', headers=headers, json={'action': 'save', 'image': image,
        'document': changed, 'revision': loaded['revision'], 'image_name': 'cells.tiff'})
    assert saved.status_code == 200
    assert 'shapes' in json.loads(path.read_text())
    assert Path(str(path) + '.bak').read_bytes() == before
