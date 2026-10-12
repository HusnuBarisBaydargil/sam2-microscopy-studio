import hashlib
import io
import json

import cv2
import numpy as np

from sam_polygons import polygon_proposals
from segmentation_io import normalize_polygon


def test_conversion_preserves_concavity_and_skips_unsupported_geometry():
    concave = [[10, 10], [40, 10], [40, 20], [20, 20], [20, 40], [10, 40]]
    proposals, skipped = polygon_proposals([
        {"polygon_supported": True, "contour": concave},
        {"polygon_supported": False, "contour": concave},
        {"polygon_supported": True, "contour": [[0, 0], [20, 20], [0, 20], [20, 0]]},
        {"polygon_supported": True, "contour": [[-10, 0], [10, 0], [0, 10]]},
    ], 100, 100)
    assert len(proposals) == 1
    assert skipped == 3
    assert proposals[0]["area"] == 500
    assert proposals[0]["id"] == 1
    normalize_polygon(proposals[0]["geometry"], 100, 100)


def test_dense_contour_becomes_editable_polygon():
    mask = np.zeros((512, 512), dtype=np.uint8)
    cv2.circle(mask, (250, 250), 180, 1, -1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    assert len(contours[0]) > 512
    proposals, skipped = polygon_proposals([
        {"polygon_supported": True, "contour": contours[0].reshape(-1, 2).tolist()},
    ], 512, 512)
    assert skipped == 0
    assert 3 <= len(proposals[0]["geometry"]["points"]) <= 512


def test_generator_flags_holes_and_multiple_components_without_changing_detection(monkeypatch):
    import sam_service

    simple = np.zeros((100, 100), dtype=np.uint8)
    simple[10:40, 10:40] = 1
    hole = simple.copy()
    hole[20:30, 20:30] = 0
    disconnected = simple.copy()
    disconnected[60:70, 60:70] = 1
    raw = [{"segmentation": mask, "area": int(mask.sum())} for mask in (simple, hole, disconnected)]

    class Generator:
        def __init__(self, **kwargs):
            pass

        def generate(self, image):
            return raw

    monkeypatch.setattr(sam_service, "SAM2AutomaticMaskGenerator", Generator)
    handler = sam_service.SAMModelHandler("", "", requested_device="cpu", skip_model_load=True)
    handler.model = object()
    settings = sam_service.normalize_sam_settings({"params": {"min_overall_area": 0}})
    result = handler.generate_masks(np.zeros((100, 100, 3), dtype=np.uint8), settings)
    assert [item["polygon_supported"] for item in result] == [True, False, False]
    assert all(item["bbox"] == [10, 10, 30, 30] for item in result)
    assert result[0]["contour"] == result[1]["contour"] == result[2]["contour"]


def test_real_route_proposals_identity_preprocessing_and_batch_persistence(client, app_module, monkeypatch):
    previous = client.get('/api/project/manifest').get_json()
    project = client.post('/api/project/projects', headers={'X-Project-ID': previous['project_id']}, json={
        'action': 'new', 'name': 'SAM polygons', 'task_type': 'instance_segmentation',
    }).get_json()
    headers = {'X-Project-ID': project['project_id']}
    classes = client.post('/api/classes', headers=headers, json={'classes': [{'name': 'Cell'}]}).get_json()['classes']
    pixels = np.full((80, 100, 3), 64, dtype=np.uint8)
    encoded = cv2.imencode('.png', pixels)[1].tobytes()
    captured = []
    masks = [{'polygon_supported': True, 'contour': points} for points in (
        [[10, 10], [30, 10], [30, 30], [10, 30]],
        [[15, 15], [45, 15], [45, 45], [15, 45]],
    )]
    monkeypatch.setattr(app_module.sam_model_handler, 'is_ready', lambda: True)
    monkeypatch.setattr(app_module, '_run_sam_inference_with_limits', lambda rgb, settings: captured.append(rgb) or masks)
    response = client.post('/api/run_sam', headers=headers, data={
        'image': (io.BytesIO(encoded), 'cells.png'), 'output': 'polygons',
        'sam_settings': json.dumps({'preset': 'fast_preview'}),
        'preprocess_method': 'gamma', 'preprocess_params': json.dumps({'gamma': 2}),
    })
    assert response.status_code == 200
    result = response.get_json()
    assert result['image'] == {'identity': hashlib.sha256(encoded).hexdigest(), 'width': 100, 'height': 80}
    assert len(result['proposals']) == 2  # overlapping objects are not suppressed
    assert not np.array_equal(captured[0], pixels)
    image = result['image']
    document = client.post('/api/project/segmentation', headers=headers, json={'action': 'load', 'image': image}).get_json()['document']
    assert document['annotations'] == []  # inference never saves annotations
    document['annotations'] = [{'id': p['id'], 'class_id': classes[0]['id'], 'geometry': p['geometry'],
                                'source': 'sam2', 'edited': False} for p in result['proposals']]
    document['next_object_id'] = 3
    saved = client.post('/api/project/segmentation', headers=headers, json={
        'action': 'save', 'image': image, 'document': document, 'revision': None,
    })
    assert saved.status_code == 200
    reopened = client.post('/api/project/segmentation', headers=headers, json={'action': 'load', 'image': image}).get_json()
    assert reopened['document'] == saved.get_json()['document']
    assert all(item['source'] == 'sam2' for item in reopened['document']['annotations'])


def test_detection_project_cannot_request_polygon_proposals(client):
    assert client.post('/api/run_sam', data={'output': 'polygons'}).status_code == 409
