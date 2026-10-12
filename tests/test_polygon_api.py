import copy

import pytest


@pytest.fixture
def polygon_project(client):
    old = client.get('/api/project/manifest').get_json()
    project = client.post('/api/project/projects', headers={'X-Project-ID': old['project_id']}, json={
        'action': 'new', 'name': 'Polygons', 'task_type': 'instance_segmentation',
    }).get_json()
    headers = {'X-Project-ID': project['project_id']}
    classes = client.post('/api/classes', headers=headers, json={'classes': [{'name': 'Target'}]}).get_json()['classes']
    image = {'identity': 'a' * 64, 'width': 100, 'height': 80}
    loaded = client.post('/api/project/segmentation', headers=headers, json={'action': 'load', 'image': image}).get_json()
    document = loaded['document']
    document['next_object_id'] = 2
    document['annotations'] = [{'id': 1, 'class_id': classes[0]['id'], 'geometry': {
        'type': 'polygon', 'points': [[10.5, 10], [40, 10], [30, 30], [10, 25]],
    }}]
    return headers, image, document


def test_polygon_validate_save_reopen_and_conflict(client, polygon_project, app_module):
    headers, image, document = polygon_project
    endpoint = '/api/project/segmentation'
    validated = client.post(endpoint, headers=headers, json={'action': 'validate', 'image': image, 'document': document})
    assert validated.status_code == 200
    empty = client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()
    assert empty['document']['annotations'] == []
    assert empty['revision'] is None
    saved = client.post(endpoint, headers=headers, json={'action': 'save', 'image': image, 'document': document, 'revision': None})
    assert saved.status_code == 200
    saved = saved.get_json()
    app_module.PROJECT_MANIFEST = None
    reloaded = client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()
    assert reloaded['document'] == saved['document']
    assert reloaded['revision'] == saved['revision']
    assert reloaded['document']['annotations'][0]['geometry'] == document['annotations'][0]['geometry']
    for revision in (None, 'stale'):
        assert client.post(endpoint, headers=headers, json={
            'action': 'save', 'image': image, 'document': document, 'revision': revision,
        }).status_code == 409
    assert client.post(endpoint, headers=headers, json={'action': 'save', 'image': image, 'document': document}).status_code == 409


def test_invalid_geometry_image_task_and_old_tab_are_rejected(client, polygon_project):
    headers, image, document = polygon_project
    invalid = copy.deepcopy(document)
    invalid['annotations'][0]['geometry']['points'] = [[0, 0], [20, 20], [0, 20], [20, 0]]
    assert client.post('/api/project/segmentation', headers=headers, json={
        'action': 'save', 'image': image, 'document': invalid, 'revision': None,
    }).status_code == 400
    for bad in ({**image, 'identity': '../unsafe'}, {**image, 'width': 0}, {**image, 'height': True}):
        assert client.post('/api/project/segmentation', headers=headers, json={'action': 'load', 'image': bad}).status_code == 400
    new = client.post('/api/project/projects', headers=headers, json={'action': 'new', 'name': 'Detection'}).get_json()
    assert client.post('/api/project/segmentation', headers=headers, json={'action': 'load', 'image': image}).status_code == 409
    assert client.post('/api/project/segmentation', headers={'X-Project-ID': new['project_id']}, json={'action': 'load', 'image': image}).status_code == 409


def test_empty_save_preserves_counter_and_other_images_are_separate(client, polygon_project):
    headers, image, document = polygon_project
    endpoint = '/api/project/segmentation'
    saved = client.post(endpoint, headers=headers, json={'action': 'save', 'image': image, 'document': document, 'revision': None}).get_json()
    document['annotations'] = []
    document['next_object_id'] = 1
    assert client.post(endpoint, headers=headers, json={'action': 'save', 'image': image, 'document': document, 'revision': saved['revision']}).status_code == 400
    document['next_object_id'] = 2
    assert client.post(endpoint, headers=headers, json={'action': 'save', 'image': image, 'document': document, 'revision': saved['revision']}).status_code == 200
    other = client.post(endpoint, headers=headers, json={'action': 'load', 'image': {**image, 'identity': 'b' * 64}}).get_json()
    assert other['revision'] is None
    assert other['document']['annotations'] == []


def test_edited_vertices_round_trip_and_invalid_move_keeps_saved_outline(client, polygon_project):
    headers, image, document = polygon_project
    endpoint = '/api/project/segmentation'
    object_ = document['annotations'][0]
    object_['geometry']['points'] = [[10, 10], [25, 10], [40, 10], [40, 40], [10, 40]]
    object_['edited'] = True
    validated = client.post(endpoint, headers=headers, json={
        'action': 'validate', 'image': image, 'document': document,
    }).get_json()['document']
    assert validated['annotations'][0]['area'] == 900
    object_['geometry']['points'][1] = [25, 5]
    saved = client.post(endpoint, headers=headers, json={
        'action': 'save', 'image': image, 'document': document, 'revision': None,
    }).get_json()
    assert saved['document']['annotations'][0]['area'] == 975
    assert saved['document']['annotations'][0]['bbox'] == [10, 5, 30, 35]
    invalid = copy.deepcopy(document)
    invalid['annotations'][0]['geometry']['points'][1] = [25, 60]
    rejected = client.post(endpoint, headers=headers, json={
        'action': 'validate', 'image': image, 'document': invalid,
    })
    assert rejected.status_code == 400
    reopened = client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()
    assert reopened['document'] == saved['document']
    assert reopened['document']['annotations'][0]['edited'] is True


@pytest.mark.parametrize('empty,status', [(False, 'reviewed'), (True, 'confirmed_empty')])
def test_review_completion_survives_save_reopen_and_labelme_round_trip(client, polygon_project, empty, status):
    headers, image, document = polygon_project
    if empty:
        document['annotations'] = []
    document['review_status'] = status
    endpoint = '/api/project/segmentation'
    saved = client.post(endpoint, headers=headers, json={
        'action': 'save', 'image': image, 'document': document, 'revision': None,
    })
    assert saved.status_code == 200
    saved = saved.get_json()
    reopened = client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()
    assert reopened['document']['review_status'] == status
    raw = client.post(endpoint, headers=headers, json={
        'action': 'export_labelme', 'image': image, 'document': saved['document'], 'image_name': 'cells.png',
    }).get_json()['labelme']
    inspected = client.post(endpoint, headers=headers, json={
        'action': 'inspect_labelme', 'image': image, 'image_name': 'cells.png', 'labelme': raw,
    })
    assert inspected.status_code == 200
    assert inspected.get_json() == {'review_status': status, 'count': len(document['annotations'])}
    wrong_source = copy.deepcopy(raw)
    wrong_source['microscopy_studio']['image']['identity'] = 'b' * 64
    assert client.post(endpoint, headers=headers, json={
        'action': 'inspect_labelme', 'image': image, 'image_name': 'cells.png', 'labelme': wrong_source,
    }).status_code == 400
    imported = client.post(endpoint, headers=headers, json={
        'action': 'import_labelme', 'image': image, 'image_name': 'cells.png', 'labelme': raw,
        'next_object_id': saved['document']['next_object_id'], 'revision': saved['revision'],
    })
    assert imported.status_code == 200
    assert imported.get_json()['document']['review_status'] == status
    # Inspection must not write annotations or alter the revision.
    assert client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json() == reopened


@pytest.mark.parametrize('empty,status', [(True, 'reviewed'), (False, 'confirmed_empty'), (False, 'done')])
def test_invalid_completion_does_not_write_an_annotation(client, polygon_project, empty, status):
    headers, image, document = polygon_project
    if empty:
        document['annotations'] = []
    document['review_status'] = status
    response = client.post('/api/project/segmentation', headers=headers, json={
        'action': 'save', 'image': image, 'document': document, 'revision': None,
    })
    assert response.status_code == 400
    loaded = client.post('/api/project/segmentation', headers=headers, json={'action': 'load', 'image': image}).get_json()
    assert loaded['revision'] is None
