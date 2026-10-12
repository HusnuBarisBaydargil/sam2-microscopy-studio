import json
import subprocess
from pathlib import Path

import pytest
from test_frontend_canvas_renderer import _node_executable

from segmentation_io import normalize_polygon

ROOT = Path(__file__).resolve().parents[1]
OUTLINE = [[10, 10], [40, 10], [80, 10], [80, 40], [80, 80], [40, 80], [10, 80], [10, 40]]


def correction(points, start, end, replacement, other_side=False):
    script = r"""
const fs=require('fs');
global.window={};
eval(fs.readFileSync('static/polygon/geometry.js','utf8'));
const correct=window.SAM2PolygonGeometry.correctedBoundary;
const input=JSON.parse(fs.readFileSync(0,'utf8')),before=JSON.stringify(input);
const result=correct(...input);
if(JSON.stringify(input)!==before)throw Error('Original geometry was modified');
process.stdout.write(JSON.stringify(result));
"""
    result = subprocess.run([_node_executable(), '-e', script],
                            input=json.dumps([points, start, end, replacement, other_side]),
                            text=True, encoding='utf-8', capture_output=True, cwd=ROOT, check=True)
    return json.loads(result.stdout)


def anchor(points, edge, t=0):
    a, b = points[edge], points[(edge + 1) % len(points)]
    return {'edge': edge, 't': t, 'point': [a[i] + t * (b[i] - a[i]) for i in (0, 1)]}


@pytest.mark.parametrize(('start', 'end', 'replacement', 'other_side'), [
    ((0, .5), (1, .5), [[40, 5]], False),
    ((0, .5), (1, .5), [[40, 30]], True),
    ((7, .5), (0, .5), [[5, 5]], False),
    ((2, .25), (2, .75), [[85, 25]], False),
    ((2, .75), (2, .25), [[85, 25]], False),
    ((0, 0), (2, 0), [[30, 5], [60, 5]], False),
    ((0, .23456789123), (2, 0), [[30, 5], [60, 5]], False),
])
def test_local_splice_preserves_every_untouched_vertex_and_winding(start, end, replacement, other_side):
    result = correction(OUTLINE, anchor(OUTLINE, *start), anchor(OUTLINE, *end), replacement, other_side)
    validated, _, _ = normalize_polygon({'type': 'polygon', 'points': result['points']}, 100, 100)
    assert validated['points'] == result['points']
    for point in result['retained']:
        assert point in validated['points']
    for point in OUTLINE:
        if point not in result['removed'][1:-1]:
            assert point in validated['points']
    def signed_area(points):
        return sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(points, points[1:] + points[:1]))
    assert signed_area(OUTLINE) * signed_area(validated['points']) > 0


def test_reversed_winding_and_fractional_coordinates_are_kept_exact():
    points = [[10.123456789123, 10.987654321987], [10.123456789123, 80], [80, 80], [80, 10.987654321987]]
    result = correction(points, anchor(points, 0, .2), anchor(points, 0, .8), [[5, 45]])
    validated, _, _ = normalize_polygon({'type': 'polygon', 'points': result['points']}, 100, 100)
    assert validated['points'] == result['points']
    for point in points:
        assert point in validated['points']


def test_invalid_splice_is_rejected_without_repair_or_simplification():
    result = correction(OUTLINE, anchor(OUTLINE, 0, .5), anchor(OUTLINE, 1, .5), [[50, 90]])
    with pytest.raises(ValueError, match='self-intersect'):
        normalize_polygon({'type': 'polygon', 'points': result['points']}, 100, 100)
    # Excess vertices stay explicit: the existing server validation rejects them.
    many = [[10 + i / 600, 10] for i in range(510)] + [[80, 80], [10, 80]]
    result = correction(many, anchor(many, 0), anchor(many, 2), [[10.001, 9], [10.002, 8], [10.003, 9]])
    assert len(result['points']) > 512
    with pytest.raises(ValueError, match='512'):
        normalize_polygon({'type': 'polygon', 'points': result['points']}, 100, 100)


def test_local_geometry_round_trip_keeps_neighbor_and_labelme_metadata(client):
    current = client.get('/api/project/manifest').get_json()
    project = client.post('/api/project/projects', headers={'X-Project-ID': current['project_id']}, json={
        'action': 'new', 'name': 'Local correction', 'task_type': 'instance_segmentation',
    }).get_json()
    headers = {'X-Project-ID': project['project_id']}
    classes = client.post('/api/classes', headers=headers, json={'classes': [{'name': 'Cell'}]}).get_json()['classes']
    image = {'identity': 'd' * 64, 'width': 100, 'height': 100}
    endpoint = '/api/project/segmentation'
    document = client.post(endpoint, headers=headers, json={'action': 'load', 'image': image}).get_json()['document']
    document['next_object_id'] = 3
    neighbor = {'id': 2, 'class_id': classes[0]['id'], 'source': 'imported', 'edited': False,
                'geometry': {'type': 'rectangle', 'points': [[85, 85], [95, 95]]}, 'labelme': {'group_id': 9}}
    points = correction(OUTLINE, anchor(OUTLINE, 0, .5), anchor(OUTLINE, 1, .5), [[40, 5]])['points']
    document['annotations'] = [{'id': 1, 'class_id': classes[0]['id'], 'source': 'manual', 'edited': True,
                                'geometry': {'type': 'polygon', 'points': points}, 'labelme': {'group_id': 7}}, neighbor]
    exported = client.post(endpoint, headers=headers, json={
        'action': 'export_labelme', 'image': image, 'document': document, 'image_name': 'cells.png',
    })
    assert exported.status_code == 200
    raw = exported.get_json()['labelme']
    assert raw['shapes'][0]['points'] == points
    assert raw['shapes'][0]['group_id'] == 7
    assert raw['shapes'][0]['microscopy_studio']['source'] == 'manual'
    assert raw['shapes'][0]['microscopy_studio']['edited'] is True
    imported = client.post(endpoint, headers=headers, json={
        'action': 'import_labelme', 'image': image, 'image_name': 'cells.png', 'labelme': raw, 'next_object_id': 1, 'revision': None,
    })
    assert imported.status_code == 200, imported.get_json()
    restored = imported.get_json()['document']['annotations']
    assert restored[0]['geometry']['points'] == points
    assert restored[0]['id'] == 1
    assert restored[0]['class_id'] == classes[0]['id']
    assert restored[0]['labelme']['group_id'] == 7
    for key in ('id', 'class_id', 'source', 'edited', 'geometry'):
        assert restored[1][key] == neighbor[key]
    assert restored[1]['labelme']['group_id'] == 9
