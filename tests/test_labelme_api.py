import copy
import json
from pathlib import Path

import pytest
from test_polygon_api import polygon_project as _polygon_project

from labelme_io import export_labelme
from segmentation_io import normalize_segmentation_document

polygon_project = _polygon_project


@pytest.mark.parametrize('empty', [False, True])
def test_folder_autosave_reopen_preserves_ids_and_metadata(client, polygon_project, app_module, empty):
    headers, image, doc = polygon_project
    classes = client.get('/api/classes').get_json()['classes']
    doc['next_object_id'] = 12
    first = {**doc['annotations'][0], 'id': 2, 'source': 'manual', 'edited': True,
             'labelme': {'group_id': 42, 'flags': {'occluded': True}, 'description': 'keep', 'custom': [1, 2]}}
    second = {**copy.deepcopy(first), 'id': 7, 'source': 'sam2', 'edited': False}
    doc['annotations'] = [] if empty else [first, second]
    doc['labelme'] = {'flags': {'checked': True}, 'custom': {'owner': 'fixture'}}
    doc['review_status'] = 'confirmed_empty' if empty else 'reviewed'
    expected = normalize_segmentation_document(doc, project_id=headers['X-Project-ID'],
        image_identity=image['identity'], image_size=(image['width'], image['height']),
        class_ids=[item['id'] for item in classes])
    raw = export_labelme(expected, classes, 'cells.tiff')
    endpoint = '/api/project/segmentation'
    # Folder saves do not populate the server annotation store. Its counter starts at one.
    assert client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()['document']['next_object_id'] == 1
    for _ in range(2):
        loaded = client.post(endpoint, headers=headers, json={'action': 'load', 'image': image,
            'image_name': 'cells.tiff', 'labelme': raw})
        assert loaded.status_code == 200, loaded.get_json()
        assert loaded.get_json()['document'] == expected
        assert loaded.get_json()['revision'] is None
        assert loaded.get_json()['classes'] == classes
        raw = export_labelme(loaded.get_json()['document'], classes, 'cells.tiff')
    assert not list(Path(app_module._annotation_dir()).glob('*.studio.json'))


@pytest.mark.parametrize('invalid', ['project', 'image', 'filename', 'dimensions', 'counter', 'ids', 'class', 'metadata'])
def test_invalid_folder_autosave_is_not_imported_or_saved(client, polygon_project, app_module, invalid):
    headers, image, doc = polygon_project
    classes = client.get('/api/classes').get_json()['classes']
    raw = export_labelme({**doc, 'annotations': [{**doc['annotations'][0], 'source': 'manual', 'edited': True}]}, classes, 'cells.tiff')
    if invalid == 'project':
        raw['microscopy_studio']['project_id'] = '00000000-0000-0000-0000-000000000001'
    elif invalid == 'image':
        raw['microscopy_studio']['image']['identity'] = 'b' * 64
    elif invalid == 'filename':
        raw['imagePath'] = 'other.tiff'
    elif invalid == 'dimensions':
        raw['imageWidth'] += 1
    elif invalid == 'counter':
        raw['microscopy_studio']['next_object_id'] = 1
    elif invalid == 'ids':
        raw['shapes'][0]['microscopy_studio']['id'] = 0
    elif invalid == 'class':
        raw['shapes'][0]['microscopy_studio']['class_id'] = 999
    else:
        raw['microscopy_studio'] = None
    response = client.post('/api/project/segmentation', headers=headers, json={
        'action': 'load', 'image': image, 'image_name': 'cells.tiff', 'labelme': raw})
    assert response.status_code == 400, response.get_json()
    assert client.get('/api/classes').get_json()['classes'] == classes
    assert not list(Path(app_module._annotation_dir()).glob('*.studio.json'))


def test_folder_autosave_restores_retired_class_with_original_id(client, polygon_project):
    headers, image, doc = polygon_project
    classes = client.get('/api/classes').get_json()['classes']
    raw = export_labelme({**doc, 'annotations': [{**doc['annotations'][0], 'source': 'sam2', 'edited': True}]}, classes, 'cells.tiff')
    assert client.post('/api/classes', headers=headers, json={'classes': []}).status_code == 200
    response = client.post('/api/project/segmentation', headers=headers, json={
        'action': 'load', 'image': image, 'image_name': 'cells.tiff', 'labelme': raw})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['classes'] == classes
    assert response.get_json()['document']['annotations'][0]['class_id'] == classes[0]['id']


@pytest.mark.parametrize('folder', [False, True])
def test_repeated_class_name_reuse_keeps_both_saved_images_reopenable(client, polygon_project, app_module, folder):
    headers, image, doc = polygon_project
    endpoint = '/api/project/segmentation'
    first = client.get('/api/classes').get_json()['classes'][0]
    classes = client.post('/api/classes', headers=headers, json={
        'classes': [first, {'name': 'Other', 'color': '#58a6ff', 'hotkey': 'o'}]}).get_json()['classes']
    second = classes[1]
    files = []

    def snapshot(class_info, identity, object_id, image_name):
        document = copy.deepcopy(doc)
        document['image']['identity'] = identity
        document['next_object_id'] = object_id + 1
        document['annotations'][0].update(id=object_id, class_id=class_info['id'], source='sam2', edited=True,
            labelme={'group_id': object_id, 'description': 'preserve'})
        document = normalize_segmentation_document(document, project_id=headers['X-Project-ID'],
            image_identity=identity, image_size=(image['width'], image['height']), class_ids=[class_info['id']])
        raw = export_labelme(document, [class_info], image_name)
        if not folder:
            saved = client.post(endpoint, headers=headers, json={'action': 'save', 'image': document['image'],
                'image_name': image_name, 'document': document, 'revision': None})
            assert saved.status_code == 200, saved.get_json()
            path = Path(app_module._annotation_dir()) / (identity + '.studio.json')
            files.append((path, path.read_bytes()))
        return document, raw

    first_doc, first_raw = snapshot(first, 'a' * 64, 7, 'first.tiff')
    assert client.post('/api/classes', headers=headers, json={'classes': [second]}).status_code == 200
    renamed = {**second, 'name': first['name']}
    assert client.post('/api/classes', headers=headers, json={'classes': [renamed]}).status_code == 200
    second_doc, second_raw = snapshot(renamed, 'b' * 64, 11, 'second.tiff')
    assert client.post('/api/classes', headers=headers, json={'classes': []}).status_code == 200
    # Reopen the project after writing its archived manifest, as a resumed session would.
    current = client.get('/api/project/manifest').get_json()
    other = client.post('/api/project/projects', headers=headers, json={'action': 'new', 'name': 'Temporary'}).get_json()
    reopened = client.post('/api/project/projects', headers={'X-Project-ID': other['project_id']}, json={
        'action': 'open', 'project_id': headers['X-Project-ID']})
    assert reopened.status_code == 200, reopened.get_json()
    app_module.PROJECT_MANIFEST = None
    manifest = client.get('/api/project/manifest').get_json()
    assert manifest['retired_classes'] == [first, renamed]
    assert manifest['next_class_id'] == current['next_class_id']
    for index, (expected, raw, image_name) in enumerate([(first_doc, first_raw, 'first.tiff'), (second_doc, second_raw, 'second.tiff')]):
        payload = {'action': 'load', 'image': expected['image']}
        if folder:
            payload.update(labelme=raw, image_name=image_name)
        result = client.post(endpoint, headers=headers, json=payload)
        assert result.status_code == 200, result.get_json()
        result = result.get_json()
        assert result['document'] == expected
        assert expected['annotations'][0]['class_id'] in {item['id'] for item in result['classes']}
        exported = client.post(endpoint, headers=headers, json={'action': 'export_labelme', 'image': expected['image'],
            'image_name': image_name, 'document': result['document']})
        assert exported.status_code == 200, exported.get_json()
        assert exported.get_json()['labelme']['shapes'][0]['microscopy_studio']['id'] == expected['annotations'][0]['id']
        # Resolve the existing active-name conflict before reopening the other identity.
        if index == 0:
            active = result['classes']
            assert client.post('/api/classes', headers=headers, json={'classes': [{**item, 'name': 'Resolved'} for item in active]}).status_code == 200
    for path, before in files:
        assert path.read_bytes() == before


@pytest.mark.parametrize('folder', [False, True])
def test_retired_class_name_conflict_preserves_files_and_manifest(client, polygon_project, app_module, folder):
    headers, image, doc = polygon_project
    endpoint = '/api/project/segmentation'
    original_classes = client.get('/api/classes').get_json()['classes']
    classes = client.post('/api/classes', headers=headers, json={
        'classes': original_classes + [{'name': 'Other'}]}).get_json()['classes']
    retired_id, active_id = classes[0]['id'], classes[1]['id']
    doc['next_object_id'] = 12
    doc['annotations'][0].update(id=7, source='sam2', edited=True, labelme={'group_id': 42})
    doc = normalize_segmentation_document(doc, project_id=headers['X-Project-ID'],
        image_identity=image['identity'], image_size=(image['width'], image['height']),
        class_ids=[item['id'] for item in classes])
    raw = export_labelme(doc, classes, 'cells.tiff')
    raw_before = copy.deepcopy(raw)
    path = None
    if not folder:
        saved = client.post(endpoint, headers=headers, json={'action': 'save', 'image': image,
            'image_name': 'cells.tiff', 'document': doc, 'revision': None})
        assert saved.status_code == 200, saved.get_json()
        path = next(Path(app_module._annotation_dir()).glob('*.studio.json'))
        saved_bytes = path.read_bytes()
    # Delete Target, then reuse its name by renaming Other (a different class ID).
    assert client.post('/api/classes', headers=headers, json={'classes': [classes[1]]}).status_code == 200
    renamed = {**classes[1], 'name': classes[0]['name']}
    assert client.post('/api/classes', headers=headers, json={'classes': [renamed]}).status_code == 200
    before = client.get('/api/project/manifest').get_json()
    manifest_bytes = Path(app_module._project_manifest_path()).read_bytes()
    payload = {'action': 'load', 'image': image}
    if folder:
        payload.update(image_name='cells.tiff', labelme=raw)
    response = client.post(endpoint, headers=headers, json=payload)
    assert response.status_code == 409, response.get_json()
    assert 'Target' in response.get_json()['error']
    assert 'name' in response.get_json()['error']
    assert client.get('/api/project/manifest').get_json() == before
    assert Path(app_module._project_manifest_path()).read_bytes() == manifest_bytes
    assert raw == raw_before
    if path:
        assert path.read_bytes() == saved_bytes
    else:
        assert not list(Path(app_module._annotation_dir()).glob('*.studio.json'))
    # Renaming the active class back resolves the conflict without reassigning saved IDs.
    assert client.post('/api/classes', headers=headers, json={'classes': [classes[1]]}).status_code == 200
    loaded = client.post(endpoint, headers=headers, json=payload)
    assert loaded.status_code == 200, loaded.get_json()
    result = loaded.get_json()
    assert result['document'] == doc
    assert {item['id'] for item in result['classes']} == {retired_id, active_id}
    exported = client.post(endpoint, headers=headers, json={'action': 'export_labelme', 'image': image,
        'image_name': 'cells.tiff', 'document': result['document']})
    assert exported.status_code == 200, exported.get_json()
    assert exported.get_json()['labelme']['shapes'][0]['microscopy_studio']['class_id'] == retired_id


def test_folder_autosave_takes_priority_without_changing_server_file(client, polygon_project, app_module):
    headers, image, doc = polygon_project
    endpoint = '/api/project/segmentation'
    stored = client.post(endpoint, headers=headers, json={'action': 'save', 'image': image,
        'document': {**doc, 'next_object_id': 100}, 'revision': None}).get_json()
    path = next(Path(app_module._annotation_dir()).glob('*.studio.json'))
    before = path.read_bytes()
    classes = client.get('/api/classes').get_json()['classes']
    local = {**stored['document'], 'next_object_id': 12,
             'annotations': [{**stored['document']['annotations'][0], 'id': 7, 'source': 'sam2', 'edited': True}]}
    response = client.post(endpoint, headers=headers, json={'action': 'load', 'image': image,
        'image_name': 'cells.tiff', 'labelme': export_labelme(local, classes, 'cells.tiff')})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['document'] == local
    assert response.get_json()['revision'] == stored['revision']
    assert path.read_bytes() == before


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
