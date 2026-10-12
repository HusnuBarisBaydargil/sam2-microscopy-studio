import copy

import pytest

from segmentation_io import manual_split_polygon, normalize_polygon

SQUARE = [[10, 10], [80, 10], [80, 80], [10, 80]]
NECK = [[10, 10], [35, 10], [35, 30], [65, 30], [65, 10], [90, 10],
        [90, 90], [65, 90], [65, 70], [35, 70], [35, 90], [10, 90]]


@pytest.mark.parametrize(('outline', 'start', 'end', 'cut'), [
    (SQUARE, {'edge': 0, 't': .5}, {'edge': 2, 't': .5}, []),
    (SQUARE, {'edge': 3, 't': .5}, {'edge': 1, 't': .5}, []),
    (SQUARE, {'edge': 0, 't': .23456789123}, {'edge': 2, 't': 0}, [[50, 40]]),
    (SQUARE, {'edge': 0, 't': .25}, {'edge': 0, 't': .75}, [[45, 30]]),
    (list(reversed(SQUARE)), {'edge': 0, 't': .5}, {'edge': 2, 't': .5}, [[40, 40]]),
    (NECK, {'edge': 2, 't': .5}, {'edge': 8, 't': .5}, []),
    (NECK, {'edge': 2, 't': .5}, {'edge': 8, 't': .5}, [[45, 40], [55, 60]]),
])
def test_cut_partitions_without_changing_original_vertices(outline, start, end, cut):
    geometry = {'type': 'polygon', 'points': copy.deepcopy(outline)}
    unchanged = copy.deepcopy((geometry, start, end, cut))
    pieces = manual_split_polygon(geometry, start, end, cut, 100, 100)
    assert len(pieces) == 2
    assert (geometry, start, end, cut) == unchanged
    original_area = normalize_polygon(geometry, 100, 100)[2]
    areas = [normalize_polygon(piece, 100, 100)[2] for piece in pieces]
    assert sum(areas) == pytest.approx(original_area, rel=1e-12)
    assert all(area > 0 for area in areas)
    for point in outline:
        assert any(point in piece['points'] for piece in pieces)
    for point in cut:
        assert all(point in piece['points'] for piece in pieces)
    if outline == NECK and not cut:
        assert areas == [2600, 2600]


@pytest.mark.parametrize(('start', 'end', 'cut', 'message'), [
    ({'edge': 0, 't': .5}, {'edge': 0, 't': .5}, [], 'different cut anchors'),
    ({'edge': 0, 't': 0}, {'edge': 1, 't': 0}, [], '3 to 512'),
    ({'edge': 0, 't': .25}, {'edge': 0, 't': .75}, [[45, 0]], 'inside'),
    ({'edge': 0, 't': .5}, {'edge': 2, 't': .5}, [[70, 65], [20, 30], [70, 30], [20, 65]], 'self-intersect'),
    ({'edge': 0, 't': .5}, {'edge': 2, 't': .5}, [[45, 40], [45, 40]], 'overlap'),
    ({'edge': 0, 't': .5}, {'edge': 2, 't': .5}, [[80, 40]], 'touch itself'),
    ({'edge': 0, 't': .5}, {'edge': 2, 't': .5}, [[101, 40]], 'inside the image'),
    ({'edge': 0, 't': .5}, {'edge': 2, 't': .5}, [[True, 40]], 'finite numbers'),
    ({'edge': -1, 't': .5}, {'edge': 2, 't': .5}, [], 'anchor edge'),
    ({'edge': True, 't': .5}, {'edge': 2, 't': .5}, [], 'anchor edge'),
    ({'edge': 0, 't': 1}, {'edge': 2, 't': .5}, [], 'anchor position'),
    ({'edge': 0, 't': float('nan')}, {'edge': 2, 't': .5}, [], 'anchor position'),
    ({'edge': 0, 't': True}, {'edge': 2, 't': .5}, [], 'anchor position'),
    ({'edge': 0, 't': .5}, {'edge': 2, 't': .5}, [[40]], 'x and y'),
    ({'edge': 0, 't': .5}, {'edge': 2, 't': .5}, None, 'interior points'),
    ({'edge': 0, 't': .5}, {'edge': 2, 't': .5}, [[40, 40]] * 511, 'interior points'),
])
def test_invalid_cut_does_not_repair_the_parent(start, end, cut, message):
    geometry = {'type': 'polygon', 'points': copy.deepcopy(SQUARE)}
    with pytest.raises(ValueError, match=message):
        manual_split_polygon(geometry, start, end, cut, 100, 100)
    assert geometry['points'] == SQUARE


def test_manual_cut_keeps_polygon_type_and_vertex_limits():
    with pytest.raises(ValueError, match='Only polygon'):
        manual_split_polygon({'type': 'rectangle', 'points': [[10, 10], [80, 80]]},
                             {'edge': 0, 't': 0}, {'edge': 1, 't': 0}, [], 100, 100)
    with pytest.raises(ValueError, match='512'):
        manual_split_polygon({'type': 'polygon', 'points': SQUARE}, {'edge': 0, 't': .5},
                             {'edge': 2, 't': .5}, [[40, 40]] * 510, 100, 100)


def test_manual_cut_api_preview_is_read_only_and_saved_children_round_trip(client):
    current = client.get('/api/project/manifest').get_json()
    project = client.post('/api/project/projects', headers={'X-Project-ID': current['project_id']}, json={
        'action': 'new', 'name': 'Manual cut', 'task_type': 'instance_segmentation',
    }).get_json()
    headers = {'X-Project-ID': project['project_id']}
    classes = client.post('/api/classes', headers=headers, json={'classes': [{'name': 'Cell'}]}).get_json()['classes']
    image = {'identity': 'e' * 64, 'width': 100, 'height': 100}
    endpoint = '/api/project/segmentation'
    document = client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()['document']
    document['next_object_id'] = 3
    document['review_status'] = 'reviewed'
    document['annotations'] = [
        {'id': 1, 'class_id': classes[0]['id'], 'source': 'imported', 'edited': False,
         'geometry': {'type': 'polygon', 'points': SQUARE}, 'labelme': {'group_id': 7}},
        {'id': 2, 'class_id': classes[0]['id'], 'source': 'manual', 'edited': False,
         'geometry': {'type': 'rectangle', 'points': [[85, 85], [95, 95]]}, 'labelme': {'group_id': 9}},
    ]
    saved = client.post(endpoint, headers=headers, json={'action': 'save', 'image': image, 'document': document,
                                                       'revision': None}).get_json()
    parent = saved['document']['annotations'][0]
    neighbor = copy.deepcopy(saved['document']['annotations'][1])
    payload = {'action': 'manual_split_preview', 'image': image, 'geometry': parent['geometry'],
               'start': {'edge': 0, 't': .5}, 'end': {'edge': 2, 't': .5}, 'points': [[40, 40]]}
    preview = client.post(endpoint, headers=headers, json=payload)
    assert preview.status_code == 200, preview.get_json()
    pieces = preview.get_json()['geometries']
    assert len(pieces) == 2
    assert client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()['document'] == saved['document']
    assert client.get('/api/project/manifest', headers=headers).get_json()['classes'] == classes
    assert client.post(endpoint, headers=headers, json={**payload, 'points': [[0, 40]]}).status_code == 400
    assert client.post(endpoint, headers={'X-Project-ID': current['project_id']}, json=payload).status_code == 409
    assert client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()['revision'] == saved['revision']
    split = copy.deepcopy(saved['document'])
    split['annotations'] = [neighbor] + [{'id': index + 3, 'class_id': parent['class_id'], 'source': 'manual',
                                        'edited': True, 'geometry': piece} for index, piece in enumerate(pieces)]
    split['next_object_id'] = 5
    split['review_status'] = 'in_progress'
    written = client.post(endpoint, headers=headers, json={'action': 'save', 'image': image, 'document': split,
                                                         'revision': saved['revision']})
    assert written.status_code == 200
    reloaded = client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()['document']
    assert reloaded == written.get_json()['document']
    assert reloaded['annotations'][0] == neighbor
    assert [item['id'] for item in reloaded['annotations']] == [2, 3, 4]
    assert reloaded['next_object_id'] == 5
    assert reloaded['review_status'] == 'in_progress'
