import copy
import json

import pytest
from PIL import Image

from labelme_io import (
    export_labelme,
    import_labelme,
    inspect_labelme,
    labelme_review_status,
)
from segmentation_io import (
    load_segmentation_document,
    normalize_segmentation_document,
    save_segmentation_document,
)

PROJECT = "556c5503-90bf-4319-9d08-06d56e1e69cd"
IMAGE = {"identity": "a" * 64, "width": 100, "height": 80}
CLASSES = [{"id": 3, "name": "Cell"}, {"id": 8, "name": "Nucleus"}]
CONTEXT = {"project_id": PROJECT, "image_identity": IMAGE["identity"], "image_size": (100, 80), "class_ids": [3, 8]}


def sample():
    return {"version": "5.7.0", "imagePath": "cells.tif", "imageData": None,
            "imageWidth": 100, "imageHeight": 80, "flags": {"reviewed": True}, "description": "field notes",
            "shapes": [{"label": "Cell", "shape_type": "polygon", "points": [[1.5, 2], [30, 2], [30, 25], [1.5, 25]],
                        "group_id": 12, "description": "keep this", "flags": {"difficult": True}, "custom": {"score": 0.9}}]}


def imported(raw=None):
    doc = import_labelme(raw or sample(), image=IMAGE, image_name="cells.tif", project_id=PROJECT,
                         classes=CLASSES, next_object_id=7)
    return normalize_segmentation_document(doc, **CONTEXT)


def test_external_shape_changes_and_other_projects_require_review():
    doc = imported()
    doc['annotations'][0]['geometry']['points'][1][0] = 30.0
    doc['review_status'] = 'reviewed'
    raw = export_labelme(doc, CLASSES, 'cells.tif')
    assert labelme_review_status(raw, PROJECT) == 'reviewed'
    assert imported(raw)['review_status'] == 'reviewed'
    raw['shapes'][0]['points'][1][0] = 30  # JSON.stringify preserves value, not Python's number type.
    assert imported(raw)['review_status'] == 'reviewed'
    assert labelme_review_status(raw, 'another-project') == 'in_progress'
    changed = copy.deepcopy(raw)
    changed['microscopy_studio']['project_id'] = 'another-project'
    assert labelme_review_status(changed, 'another-project') == 'in_progress'
    changed = copy.deepcopy(raw)
    changed['microscopy_studio']['image']['identity'] = 'b' * 64
    assert labelme_review_status(changed, PROJECT) == 'in_progress'
    changed = copy.deepcopy(raw)
    changed['shapes'][0]['points'][0][0] = 2
    assert imported(changed)['review_status'] == 'in_progress'
    changed = copy.deepcopy(raw)
    changed['shapes'] = []
    assert imported(changed)['review_status'] == 'unreviewed'
    # Legacy Labelme flags are not explicit Studio review decisions.
    assert labelme_review_status(sample(), PROJECT) == 'in_progress'


def test_polygon_metadata_and_precision_survive_autosave_and_export(tmp_path):
    raw = sample()
    original = copy.deepcopy(raw)
    doc = imported(raw)
    path = tmp_path / 'cells.studio.json'
    saved = save_segmentation_document(path, doc, classes=CLASSES, image_path='cells.tif', **CONTEXT)
    assert load_segmentation_document(path, **CONTEXT) == saved == doc
    exported = export_labelme(doc, CLASSES, 'cells.tif')
    assert exported['shapes'][0]['points'] == raw['shapes'][0]['points']
    for key in ('label', 'group_id', 'flags', 'description', 'custom'):
        assert exported['shapes'][0][key] == raw['shapes'][0][key]
    assert exported['flags'] == raw['flags']
    assert exported['description'] == raw['description']
    assert exported['imageData'] is None
    assert json.loads(path.read_text())['shapes'] == exported['shapes']
    assert raw == original


def test_legacy_files_migrate_on_save_with_backup_and_stable_ids(tmp_path):
    doc = imported()
    path = tmp_path / 'legacy.studio.json'
    save_segmentation_document(path, doc, **CONTEXT)
    legacy = path.read_bytes()
    loaded = load_segmentation_document(path, **CONTEXT)
    save_segmentation_document(path, loaded, classes=CLASSES, image_path='cells.tif', **CONTEXT)
    assert 'shapes' in json.loads(path.read_text())
    assert (tmp_path / 'legacy.studio.json.bak').read_bytes() == legacy
    assert load_segmentation_document(path, **CONTEXT) == loaded
    path.write_text('{broken')
    assert load_segmentation_document(path, **CONTEXT) == loaded


@pytest.mark.parametrize('kind', ['ellipse', 'line', 'point', 'linestrip', 'mask', 'oriented_rectangle'])
def test_unsupported_shape_rejects_entire_import(kind):
    raw = sample()
    raw['shapes'].append({**raw['shapes'][0], 'shape_type': kind})
    with pytest.raises(ValueError, match='Unsupported Labelme shapes: 2'):
        imported(raw)


@pytest.mark.parametrize('change', [
    {'imageWidth': 101}, {'imageHeight': True}, {'imagePath': 'other.tif'}, {'shapes': {}},
    {'flags': {'reviewed': 'yes'}},
])
def test_image_and_document_validation(change):
    with pytest.raises(ValueError):
        imported({**sample(), **change})


def test_bad_polygon_unknown_class_and_identity_rejected():
    raw = sample()
    raw['shapes'][0]['points'] = [[0, 0], [20, 20], [0, 20], [20, 0]]
    with pytest.raises(ValueError, match='Shape 1'):
        imported(raw)
    raw = sample()
    raw['shapes'][0]['label'] = 'New cell'
    with pytest.raises(ValueError, match='Could not create class'):
        imported(raw)
    exported = export_labelme(imported(), CLASSES, 'cells.tif')
    exported['microscopy_studio']['image']['identity'] = 'b' * 64
    with pytest.raises(ValueError, match='different source image'):
        imported(exported)


def test_relative_path_never_reads_files_and_embedded_pixels_are_not_imported():
    raw = sample()
    raw['imagePath'] = r'..\images\cells.tif'
    raw['imageData'] = 'ignored-image-bytes'
    assert inspect_labelme(raw, IMAGE, 'cells.tif') == ['Cell']
    assert 'imageData' not in imported(raw).get('labelme', {})


def test_installed_labelme_can_read_and_write_our_polygons(tmp_path):
    # Optional integration check; Labelme/Qt are not application dependencies.
    label_file = pytest.importorskip('labelme.label_file')
    Image.new('RGB', (100, 80)).save(tmp_path / 'cells.tif')
    path = tmp_path / 'cells.json'
    raw = export_labelme(imported(), CLASSES, 'cells.tif')
    path.write_text(json.dumps(raw), encoding='utf-8')
    labelme = label_file.LabelFile(str(path))
    assert labelme.shapes[0]['points'] == sample()['shapes'][0]['points']
    assert labelme.shapes[0]['label'] == 'Cell'
    shape = labelme.shapes[0]
    labelme_shapes = [{**shape['other_data'], **{k: v for k, v in shape.items() if k != 'other_data'}}]
    returned = tmp_path / 'labelme-saved.json'
    labelme.save(str(returned), labelme_shapes, 'cells.tif', 80, 100,
                 otherData=labelme.otherData, flags=labelme.flags)
    roundtrip = imported(json.loads(returned.read_text()))
    assert roundtrip['annotations'][0]['geometry'] == imported()['annotations'][0]['geometry']
    assert roundtrip['annotations'][0]['labelme']['group_id'] == 12


@pytest.mark.parametrize('kind,points,area', [
    ('rectangle', [[30, 25], [10, 5]], 400),
    ('circle', [[40, 40], [50, 40]], 314.1592653589793),
])
def test_native_shapes_round_trip(kind, points, area, tmp_path):
    raw = sample()
    raw['shapes'][0].update(shape_type=kind, points=points)
    doc = imported(raw)
    assert doc['annotations'][0]['area'] == pytest.approx(area)
    path = tmp_path / 'shapes.json'
    save_segmentation_document(path, doc, classes=CLASSES, image_path='cells.tif', **CONTEXT)
    assert load_segmentation_document(path, **CONTEXT) == doc
    shape = export_labelme(doc, CLASSES, 'cells.tif')['shapes'][0]
    assert shape['shape_type'] == kind
    assert shape['points'] == points
    assert shape['group_id'] == 12


@pytest.mark.parametrize('kind,points', [
    ('rectangle', [[10, 10], [10, 30]]),
    ('circle', [[10, 10], [10, 10]]),
    ('circle', [[5, 5], [20, 5]]),
    ('circle', [[40, 40], [float('nan'), 40]]),
    ('rectangle', [[1, 1], [2, 2], [3, 3]]),
])
def test_invalid_native_shapes_are_rejected(kind, points):
    raw = sample()
    raw['shapes'][0].update(shape_type=kind, points=points)
    with pytest.raises(ValueError):
        imported(raw)


@pytest.mark.parametrize('length', [65, 128])
def test_long_class_names_round_trip(length, tmp_path):
    from annotation_io import _normalize_classes

    classes = _normalize_classes([{'id': 3, 'name': 'N' * length}])
    raw = sample()
    raw['shapes'][0]['label'] = classes[0]['name']
    doc = import_labelme(raw, image=IMAGE, image_name='cells.tif', project_id=PROJECT,
                         classes=classes, next_object_id=7)
    path = tmp_path / 'long-name.json'
    saved = save_segmentation_document(path, doc, classes=classes, image_path='cells.tif', **CONTEXT)
    loaded = load_segmentation_document(path, **CONTEXT)
    assert loaded == saved
    exported = export_labelme(loaded, classes, 'cells.tif')
    assert inspect_labelme(exported, IMAGE, 'cells.tif') == ['N' * length]


def test_labelme_rejects_names_above_shared_limit():
    raw = sample()
    raw['shapes'][0]['label'] = 'N' * 129
    with pytest.raises(ValueError, match='128 characters'):
        inspect_labelme(raw, IMAGE, 'cells.tif')
