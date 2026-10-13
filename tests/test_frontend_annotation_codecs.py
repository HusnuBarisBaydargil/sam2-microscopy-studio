import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


EXTRACTED_CODEC_FUNCTIONS = [
    "buildAnnotationCsv",
    "buildAnnotationYolo",
    "buildAnnotationCoco",
    "buildAnnotationVoc",
    "parseAnnotationCsv",
    "parseAnnotationYolo",
    "parseAnnotationCoco",
    "parseAnnotationVoc",
    "normalizeImportedBbox",
    "annotationFromRecord",
]


def test_annotation_codecs_load_after_config_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    config_tag = '<script src="static/frontendConfig.js"></script>'
    codecs_tag = '<script src="static/annotationCodecs.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert config_tag in index_html
    assert codecs_tag in index_html
    assert script_tag in index_html
    assert index_html.index(config_tag) < index_html.index(codecs_tag)
    assert index_html.index(codecs_tag) < index_html.index(script_tag)


def test_main_script_uses_extracted_annotation_codecs_without_duplicate_bodies():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")
    workflow_js = (STATIC_DIR / "annotationWorkflowController.js").read_text(encoding="utf-8")

    assert "const annotationCodecs = window.SAM2AnnotationCodecs;" in script_js
    assert "annotationWorkflowController.buildAnnotationExport(" in script_js
    assert "annotationWorkflowController.parseAnnotationFile(" in script_js
    assert "annotationCodecs.buildAnnotationExport(" in workflow_js
    assert "annotationCodecs.parseAnnotationFile(" in workflow_js
    for function_name in EXTRACTED_CODEC_FUNCTIONS:
        assert f"function {function_name}(" not in script_js


def _node_executable():
    node = shutil.which("node")
    if node:
        return node

    bundled_node = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "bin"
        / "node.exe"
    )
    if bundled_node.exists():
        return str(bundled_node)

    return None


def test_annotation_codecs_round_trip_supported_formats():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute annotationCodecs.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        function plain(value) {
            return JSON.parse(JSON.stringify(value));
        }

        const context = { window: {} };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync('static/frontendConfig.js', 'utf8'), context);
        vm.runInContext(fs.readFileSync('static/annotationCodecs.js', 'utf8'), context);

        const codecs = context.window.SAM2AnnotationCodecs;
        assert.ok(codecs);
        assert.strictEqual(codecs.normalizeAnnotationFormat('unknown'), 'csv');
        assert.strictEqual(codecs.formatFromFileName('cells_annotations_rich.csv'), 'csv_rich');
        assert.strictEqual(codecs.annotationDownloadName('cells.tif', 'voc'), 'cells.xml');

        const imageRecord = {
            name: 'cells.tif',
            displayPath: 'plate/cells.tif',
            originalImage: { width: 200, height: 100 }
        };
        const classes = [
            { name: 'nucleus', color: '#39d353', hotkey: 'n' },
            { name: 'cell membrane', color: '#58a6ff', hotkey: 'm' }
        ];
        const annotations = [
            {
                id: 7,
                bbox: [10, 5, 40, 20],
                class: 'nucleus',
                type: 'manual',
                contour: [[10, 5], [50, 5], [50, 25]],
                mask_area: 750,
                source: 'sam',
                predicted_iou: 0.91,
                stability_score: 0.87
            },
            {
                id: 8,
                bbox: [100, 50, 20, 10],
                class: 'cell membrane',
                type: 'loaded'
            }
        ];

        function exportAndParse(format) {
            const exported = codecs.buildAnnotationExport(
                imageRecord.name,
                annotations,
                format,
                imageRecord,
                { classes }
            );
            const parsed = codecs.parseAnnotationFile(exported.content, format, imageRecord, {
                classes,
                imageNames: [imageRecord.name, imageRecord.displayPath]
            });
            return { exported, parsed: plain(parsed) };
        }

        function assertBoxesClose(actual, expected, tolerance = 0.0001) {
            assert.strictEqual(actual.length, expected.length);
            actual.forEach((value, index) => {
                assert.ok(
                    Math.abs(value - expected[index]) <= tolerance,
                    `${actual} differs from ${expected} at index ${index}`
                );
            });
        }

        for (const format of ['csv', 'csv_rich', 'yolo', 'coco', 'voc']) {
            const { parsed } = exportAndParse(format);
            assert.strictEqual(parsed.annotations.length, annotations.length, format);
            assert.strictEqual(parsed.annotations[0].class, 'nucleus', format);
            assert.strictEqual(parsed.annotations[1].class, 'cell membrane', format);
            assertBoxesClose(parsed.annotations[0].bbox, [10, 5, 40, 20]);
            assertBoxesClose(parsed.annotations[1].bbox, [100, 50, 20, 10]);
        }

        const csvRich = exportAndParse('csv_rich').parsed;
        assert.deepStrictEqual(csvRich.annotations[0].contour, [[10, 5], [50, 5], [50, 25]]);
        assert.strictEqual(csvRich.annotations[0].mask_area, 750);
        assert.strictEqual(csvRich.annotations[0].source, 'sam');
        assert.strictEqual(csvRich.annotations[0].predicted_iou, 0.91);
        assert.strictEqual(csvRich.annotations[0].stability_score, 0.87);

        const coco = exportAndParse('coco').parsed;
        assert.deepStrictEqual(coco.annotations[0].contour, [[10, 5], [50, 5], [50, 25]]);
        assert.strictEqual(coco.annotations[0].mask_area, 750);

        const staleCoco = JSON.parse(codecs.buildAnnotationExport(
            imageRecord.name,
            [{
                ...annotations[0],
                bbox: [60, 5, 40, 20]
            }],
            'coco',
            imageRecord,
            { classes }
        ).content);
        assert.strictEqual(staleCoco.annotations[0].segmentation, undefined);
        assert.strictEqual(staleCoco.annotations[0].mask_area, undefined);
        assert.strictEqual(staleCoco.annotations[0].area, 800);
        assert.strictEqual(staleCoco.annotations[0].source, 'sam');
        assert.strictEqual(staleCoco.annotations[0].predicted_iou, 0.91);

        const stableClasses = [
            { id: 9, name: 'nucleus', color: '#39d353', hotkey: 'n' },
            { id: 4, name: 'cell membrane', color: '#58a6ff', hotkey: 'm' }
        ];
        const stableYolo = codecs.buildAnnotationExport(
            imageRecord.name,
            annotations,
            'yolo',
            imageRecord,
            { classes: stableClasses }
        ).content;
        assert.deepStrictEqual(stableYolo.trim().split(/\r?\n/).map(line => line.split(' ')[0]), ['8', '3']);
        const parsedStableYolo = codecs.parseAnnotationFile(stableYolo, 'yolo', imageRecord, {
            classes: stableClasses,
            imageNames: [imageRecord.name]
        });
        assert.deepStrictEqual(plain(parsedStableYolo.annotations.map(item => item.class)), [
            'nucleus',
            'cell membrane'
        ]);

        const stableCoco = JSON.parse(codecs.buildAnnotationExport(
            imageRecord.name,
            annotations,
            'coco',
            imageRecord,
            { classes: stableClasses }
        ).content);
        assert.deepStrictEqual(stableCoco.categories.map(category => category.id), [9, 4]);
        assert.deepStrictEqual(stableCoco.annotations.map(annotation => annotation.category_id), [9, 4]);

        for (const format of ['csv', 'csv_rich', 'yolo', 'coco', 'voc']) {
            const exported = codecs.buildAnnotationExport(
                imageRecord.name,
                [],
                format,
                imageRecord,
                { classes }
            );
            const parsed = plain(codecs.parseAnnotationFile(exported.content, format, imageRecord, {
                classes,
                imageNames: [imageRecord.name]
            }));
            assert.strictEqual(parsed.annotations.length, 0, `empty ${format}`);
        }
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)


@pytest.mark.parametrize('annotation_format', ['csv', 'csv_rich', 'yolo', 'coco', 'voc'])
def test_detection_formats_preserve_distinct_128_character_class_names(annotation_format):
    node = _node_executable()
    if node is None:
        pytest.skip('Node.js is not available to execute annotationCodecs.js')
    script = r"""
const fs=require('fs'),assert=require('assert');global.window={};
for(const module of ['frontendConfig','annotationCodecs'])eval(fs.readFileSync('static/'+module+'.js','utf8'));
const codec=window.SAM2AnnotationCodecs,format='FORMAT';
const prefix='Microscopy '+ 'x'.repeat(53),suffix='&<>"\''+String.fromCharCode(181)+'y'.repeat(57);
const names=[prefix+suffix+'A',prefix+suffix+'B'];
assert(names.every(name=>name.length===128));assert.equal(names[0].slice(0,64),names[1].slice(0,64));
const classes=names.map((name,i)=>({id:[9,3][i],name,color:i?'#abcdef':'#123456',hotkey:i?'o':'c'}));
const annotations=names.map((name,i)=>({id:i+1,class:name,bbox:[10+i*30,10,20,20],type:'manual'}));
const image={name:'cells.png',originalImage:{width:100,height:100}};
const output=codec.buildAnnotationExport(image.name,annotations,format,image,{classes});
// These are standard exports: COCO/VOC must retain labels without a review sidecar.
const parsed=codec.parseAnnotationFile(output.content,format,image,{classes:classes.slice().reverse()});
assert.deepEqual(parsed.annotations.map(item=>item.class),names);
for(let i=0;i<annotations.length;i++)for(let j=0;j<4;j++)assert(Math.abs(parsed.annotations[i].bbox[j]-annotations[i].bbox[j])<1e-8);
if(format==='coco'){
 const data=JSON.parse(output.content);
 assert.deepEqual(data.categories.map(item=>[item.id,item.name]),classes.map(item=>[item.id,item.name]));
 assert.deepEqual(data.annotations.map(item=>item.category_id),[9,3]);
 const withSidecar=codec.parseAnnotationFile(output.content,format,image,{savedClasses:classes});
 assert.deepEqual(withSidecar.annotations.map(item=>item.class),names);
}
if(format==='yolo')assert.deepEqual(output.content.trim().split('\n').map(row=>Number(row.split(' ')[0])),[8,2]);
""".replace('FORMAT', annotation_format)
    subprocess.run([node, '-'], input=script, text=True, encoding='utf-8', cwd=REPO_ROOT, check=True)


@pytest.mark.parametrize('annotation_format', ['csv', 'csv_rich', 'yolo', 'coco', 'voc'])
def test_detection_exports_reject_unsupported_class_names_without_truncating(annotation_format):
    node = _node_executable()
    if node is None:
        pytest.skip('Node.js is not available to execute annotationCodecs.js')
    script = r"""
const fs=require('fs'),assert=require('assert');global.window={};
for(const module of ['frontendConfig','annotationCodecs'])eval(fs.readFileSync('static/'+module+'.js','utf8'));
const codec=window.SAM2AnnotationCodecs,format='FORMAT',image={name:'cells.png',originalImage:{width:100,height:100}};
const names=['x'.repeat(129),'x'.repeat(128)+'A','x'.repeat(128)+'B'];
for(const name of names){
 const annotations=[{id:1,class:name,bbox:[10,10,20,20]}],classes=[{id:9,name}];
 const before=JSON.stringify({annotations,classes});
 assert.throws(()=>codec.buildAnnotationExport(image.name,annotations,format,image,{classes}),/cannot exceed 128 characters/);
 assert.equal(JSON.stringify({annotations,classes}),before);
 // A caller-provided normalizer must not bypass the shared export validation.
 assert.throws(()=>codec.buildAnnotationExport(image.name,annotations,format,image,{classes,normalizeAnnotation:item=>item}),/cannot exceed 128 characters/);
}
// Python counts Unicode code points, so a supported name may occupy more UTF-16 units.
const name=String.fromCodePoint(0x1f52c).repeat(128),classes=[{id:9,name}],annotations=[{id:1,class:name,bbox:[10,10,20,20]}];
const output=codec.buildAnnotationExport(image.name,annotations,format,image,{classes});
assert.equal(codec.parseAnnotationFile(output.content,format,image,{classes}).annotations[0].class,name);
annotations[0].class+=String.fromCodePoint(0x1f52c);
assert.throws(()=>codec.buildAnnotationExport(image.name,annotations,format,image,{classes}),/cannot exceed 128 characters/);
""".replace('FORMAT', annotation_format)
    subprocess.run([node, '-'], input=script, text=True, encoding='utf-8', cwd=REPO_ROOT, check=True)
