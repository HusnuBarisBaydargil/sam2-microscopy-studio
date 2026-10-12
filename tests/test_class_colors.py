import json
import re
import subprocess
from pathlib import Path

from test_frontend_canvas_renderer import _node_executable

from annotation_io import (
    _classes_with_annotation_labels,
    _normalize_classes,
    generate_class_color,
)
from project_manifest import (
    create_project_manifest,
    load_or_create_project_manifest,
    save_project_manifest,
)


def test_generated_colors_extend_palette_and_match_browser():
    used = set()
    colors = []
    for index in range(2000):
        color = generate_class_color(index, used)
        assert re.fullmatch(r"#[0-9a-f]{6}", color)
        assert color not in used
        used.add(color)
        colors.append(color)
    result = subprocess.run([_node_executable(), '-e', r"""
const fs=require('fs');global.window={};
eval(fs.readFileSync('static/frontendConfig.js','utf8'));
const colors=[],used=new Set();
for(let i=0;i<2000;i++){const color=window.SAM2FrontendConfig.generateClassColor(i,used);colors.push(color);used.add(color);}
process.stdout.write(JSON.stringify(colors));
"""], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == colors


def test_no_class_truncation_in_normalization_or_annotation_import():
    raw = [{'name': f'Class {index}'} for index in range(1200)]
    classes = _normalize_classes(raw)
    assert len(classes) == 1200
    assert len({item['color'] for item in classes}) == 1200
    imported = _classes_with_annotation_labels([], [{'class': item['name']} for item in raw])
    assert len(imported) == 1200
    assert len({item['color'] for item in imported}) == 1200


def test_legacy_segmentation_colors_repaired_and_persisted(tmp_path):
    options = dict(project_root=str(tmp_path), default_annotation_output_dir='annotations', allow_absolute_annotation_dir=False)
    original = [{'name': 'A', 'color': '#67d7c3'}, {'name': 'B', 'color': '#67D7C3'}, {'name': 'C', 'color': '#ff0000'}]
    manifest = create_project_manifest(classes=original, task_type='instance_segmentation', **options)
    assert len({item['color'].lower() for item in manifest['classes']}) == 3
    assert manifest['classes'][0]['color'] == '#67d7c3'
    assert manifest['classes'][2]['color'] == '#ff0000'
    path = tmp_path / 'project.json'
    saved = save_project_manifest(manifest, path, **options)
    assert load_or_create_project_manifest(path, **options) == saved
    # Simulate an older project on disk, before automatic distinct colors existed.
    saved['classes'][1]['color'] = '#67D7C3'
    path.write_text(json.dumps(saved), encoding='utf-8')
    repaired = load_or_create_project_manifest(path, **options)
    assert len({item['color'].lower() for item in repaired['classes']}) == 3
    assert [item['id'] for item in repaired['classes']] == [item['id'] for item in saved['classes']]
    assert json.loads(path.read_text(encoding='utf-8')) == repaired
    assert load_or_create_project_manifest(path, **options) == repaired
    assert original[1]['color'] == '#67D7C3'


def test_api_saves_and_reopens_more_than_500_classes(client, app_module):
    raw = [{'name': f'Cell {index}'} for index in range(1100)]
    response = client.post('/api/classes', json={'classes': raw})
    assert response.status_code == 200
    saved = response.get_json()['classes']
    assert len(saved) == 1100
    assert len({item['color'] for item in saved}) == 1100
    app_module.PROJECT_MANIFEST = None
    assert client.get('/api/classes').get_json()['classes'] == saved


def test_segmentation_drawing_shortcuts_migrate_without_changing_detection(tmp_path):
    options = dict(project_root=str(tmp_path), default_annotation_output_dir='annotations', allow_absolute_annotation_dir=False)
    raw = [{'name': f'Class {key}', 'hotkey': key} for key in ['1', '2', '3', '4', 'a']]
    detection = create_project_manifest(classes=raw, task_type='bounding_box', **options)
    assert [c['hotkey'] for c in detection['classes']] == ['1', '2', '3', '4', 'a']
    segmentation = create_project_manifest(classes=raw, task_type='instance_segmentation', **options)
    assert [c['hotkey'] for c in segmentation['classes']] == ['', '', '', '4', 'a']
    path = tmp_path / 'project.json'
    saved = save_project_manifest(segmentation, path, **options)
    saved['classes'][0]['hotkey'] = '1'
    path.write_text(json.dumps(saved), encoding='utf-8')
    loaded = load_or_create_project_manifest(path, **options)
    assert loaded['classes'][0]['hotkey'] == ''
    assert [c['id'] for c in loaded['classes']] == [c['id'] for c in saved['classes']]
    assert json.loads(path.read_text(encoding='utf-8')) == loaded
