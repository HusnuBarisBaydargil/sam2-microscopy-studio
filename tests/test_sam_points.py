import io
import json

import cv2
import numpy as np
import pytest


def test_point_api_validates_and_uses_preprocessing(client, app_module, monkeypatch):
    previous = client.get('/api/project/manifest').get_json()
    project = client.post('/api/project/projects', headers={'X-Project-ID': previous['project_id']}, json={
        'action': 'new', 'name': 'Prompt test', 'task_type': 'instance_segmentation',
    }).get_json()
    headers = {'X-Project-ID': project['project_id']}
    pixels = np.full((40, 50, 3), 64, dtype=np.uint8)
    image = cv2.imencode('.png', pixels)[1].tobytes()
    calls = []
    monkeypatch.setattr(app_module.sam_model_handler, 'is_ready', lambda: True)
    def predict(rgb, settings, points, project_id):
        calls.append((rgb, points, project_id))
        return [{'polygon_supported': True, 'contour': [[5, 5], [20, 5], [20, 20], [5, 20]]}]
    monkeypatch.setattr(app_module, '_run_sam_inference_with_limits', predict)
    def post(points, request_headers=headers):
        return client.post('/api/run_sam', headers=request_headers, data={
            'image': (io.BytesIO(image), 'cells.png'), 'output': 'polygons', 'points': json.dumps(points),
            'preprocess_method': 'gamma', 'preprocess_params': json.dumps({'gamma': 2}),
        })
    response = post([[10, 10, 1], [30, 30, 0]])
    assert response.status_code == 200
    assert len(response.get_json()['proposals']) == 1
    assert calls[0][1:] == ([[10, 10, 1], [30, 30, 0]], project['project_id'])
    assert not np.array_equal(calls[0][0], pixels)
    for points in ([], [[1, 1, 0]], [[50, 1, 1]], [[1, -1, 1]], [[True, 1, 1]],
                   [[1, 1, True]], [[1, 1, 2]], [[1, 1]], [[float('nan'), 1, 1]],
                   [[10**1000, 1, 1]], [[1, 1, 1]] * 65, {'x': 1}):
        assert post(points).status_code == 400
    assert len(calls) == 1
    assert post([[1, 1, 1]], {}).status_code == 409
    assert post([[1, 1, 1]], {'X-Project-ID': 'stale'}).status_code == 409
    monkeypatch.setattr(app_module, '_run_sam_inference_with_limits', lambda *args: [{'polygon_supported': False}])
    assert post([[1, 1, 1]]).status_code == 422
    monkeypatch.setattr(app_module.sam_model_handler, 'is_ready', lambda: False)
    assert post([[1, 1, 1]]).status_code == 503


def test_predictor_reuses_only_matching_embeddings_and_preserves_topology(monkeypatch):
    import sam_service
    instances = []
    mask = np.zeros((40, 50), dtype=np.uint8)
    mask[5:20, 5:20] = 1
    class Predictor:
        def __init__(self, model):
            self.model = model
            self.images = []
            self.calls = []
            instances.append(self)
        def set_image(self, image):
            self.images.append(image.copy())
        def predict(self, **kwargs):
            self.calls.append(kwargs)
            return np.array([mask]), np.array([.9]), None
    monkeypatch.setattr(sam_service, 'SAM2ImagePredictor', Predictor)
    handler = sam_service.SAMModelHandler('', '', requested_device='cpu', skip_model_load=True)
    handler.model = object()
    image = np.zeros((40, 50, 3), dtype=np.uint8)
    assert handler.predict_points(image, [[10, 10, 1]], 'one')[0]['polygon_supported']
    handler.predict_points(image, [[10, 10, 1], [25, 25, 0]], 'one')
    assert len(instances[0].images) == 1
    assert instances[0].calls[1]['point_labels'].tolist() == [1, 0]
    assert instances[0].calls[0]['multimask_output'] is True
    assert instances[0].calls[1]['multimask_output'] is False
    handler.predict_points(image + 1, [[10, 10, 1]], 'one')
    handler.predict_points(image + 1, [[10, 10, 1]], 'two')
    assert len(instances[0].images) == 3
    handler.model = object()
    handler.predict_points(image, [[10, 10, 1]], 'two')
    assert len(instances) == 2
    mask[10:12, 10:12] = 0
    assert not handler.predict_points(image, [[10, 10, 1]], 'two')[0]['polygon_supported']
    mask[:] = 0
    assert not handler.predict_points(image, [[10, 10, 1]], 'two')[0]['polygon_supported']


def test_prompt_failure_releases_inference_slot(app_module, monkeypatch):
    import threading
    semaphore = threading.BoundedSemaphore(1)
    monkeypatch.setattr(app_module, 'SAM_INFERENCE_SEMAPHORE', semaphore)
    def fail(*args):
        raise RuntimeError('prediction failed')
    monkeypatch.setattr(app_module.sam_model_handler, 'predict_points', fail)
    with pytest.raises(RuntimeError, match='prediction failed'):
        app_module._run_sam_inference_with_limits(np.zeros((10, 10, 3)), {}, [[1, 1, 1]], 'project')
    assert semaphore.acquire(blocking=False)
    semaphore.release()


def test_split_predictions_are_disjoint_clipped_and_all_or_nothing(monkeypatch):
    import sam_service
    from sam_polygons import polygon_proposals
    calls = []
    class Predictor:
        def __init__(self, model): self.model = model
        def set_image(self, image): pass
        def predict(self, **kwargs):
            calls.append(kwargs)
            index = int(np.argmax(kwargs["point_labels"]))
            logits = np.tile(np.arange(50, dtype=np.float32), (40, 1))
            return np.array([25 - logits if index == 0 else logits - 24]), None, None
    monkeypatch.setattr(sam_service, 'SAM2ImagePredictor', Predictor)
    handler = sam_service.SAMModelHandler('', '', requested_device='cpu', skip_model_load=True)
    handler.model = object()
    parent = {"type": "rectangle", "points": [[5, 5], [45, 35]]}
    image = np.zeros((40, 50, 3), dtype=np.uint8)
    masks = handler.predict_points(image, [[10, 20, 1], [35, 20, 1]], 'test', parent)
    proposals, skipped = polygon_proposals(masks, 50, 40)
    assert len(proposals) == 2 and skipped == 0
    assert proposals[0]['bbox'][0] == 5 and proposals[1]['bbox'][0] == 25
    assert calls[0]['point_labels'].tolist() == [1, 0]
    assert calls[1]['point_labels'].tolist() == [0, 1]
    for points in ([[1, 1, 1], [35, 20, 1]], [[10, 20, 1]] * 2):
        with pytest.raises(ValueError, match='distinct include'):
            handler.predict_points(image, points, 'test', parent)


def test_merge_preview_and_split_api_are_read_only(client, app_module, monkeypatch):
    previous = client.get('/api/project/manifest').get_json()
    project = client.post('/api/project/projects', headers={'X-Project-ID': previous['project_id']}, json={
        'action': 'new', 'name': 'Split merge', 'task_type': 'instance_segmentation',
    }).get_json()
    headers = {'X-Project-ID': project['project_id']}
    image = {'identity': 'b' * 64, 'width': 50, 'height': 40}
    def rect(x1, x2):
        return {'type': 'rectangle', 'points': [[x1, 5], [x2, 30]]}
    payload = {'action': 'merge_preview', 'image': image, 'geometries': [rect(5, 25), rect(20, 45)]}
    result = client.post('/api/project/segmentation', headers=headers, json=payload)
    assert result.status_code == 200
    assert result.get_json()['geometry']['type'] == 'polygon'
    payload['geometries'] = [rect(5, 15), rect(25, 45)]
    assert client.post('/api/project/segmentation', headers=headers, json=payload).status_code == 400
    assert client.post('/api/project/segmentation', json=payload).status_code == 409
    loaded = client.post('/api/project/segmentation', headers=headers, json={'action': 'load', 'image': image}).get_json()
    assert loaded['revision'] is None and loaded['document']['annotations'] == []
    monkeypatch.setattr(app_module.sam_model_handler, 'is_ready', lambda: True)
    calls = []
    def predict(*args, **kwargs):
        calls.append(kwargs)
        return [{'polygon_supported': True, 'contour': [[5, 5], [15, 5], [15, 30], [5, 30]]},
                {'polygon_supported': True, 'contour': [[25, 5], [45, 5], [45, 30], [25, 30]]}]
    monkeypatch.setattr(app_module, '_run_sam_inference_with_limits', predict)
    pixels = cv2.imencode('.png', np.zeros((40, 50, 3), dtype=np.uint8))[1].tobytes()
    def split(points, geometry=rect(5, 45)):
        return client.post('/api/run_sam', headers=headers, data={'image': (io.BytesIO(pixels), 'cells.png'),
            'output': 'polygons', 'points': json.dumps(points), 'split_geometry': json.dumps(geometry)})
    assert split([[10, 20, 1], [35, 20, 1]]).status_code == 200
    assert calls[0]['split_geometry'] == rect(5, 45)
    assert split([[10, 20, 1]]).status_code == 400
    assert split([[10, 20, 1], [35, 20, 0]]).status_code == 400
    assert split([[10, 20, 1], [35, 20, 1]], {}).status_code == 400
    monkeypatch.setattr(app_module, '_run_sam_inference_with_limits', lambda *args, **kwargs: predict()[0:1])
    assert split([[10, 20, 1], [35, 20, 1]]).status_code == 422


def test_merge_does_not_fill_holes_or_bridge_disjoint_regions():
    from sam_polygons import merge_geometries
    def rect(x1, y1, x2, y2):
        return {'type': 'rectangle', 'points': [[x1, y1], [x2, y2]]}
    ring = [rect(5, 5, 30, 10), rect(5, 25, 30, 30), rect(5, 5, 10, 30), rect(25, 5, 30, 30)]
    with pytest.raises(ValueError, match='connected outline'):
        merge_geometries(ring, 40, 40)
    for geometries in ([], [ring[0]], [ring[0]] * 101):
        with pytest.raises(ValueError, match='Select'):
            merge_geometries(geometries, 40, 40)
