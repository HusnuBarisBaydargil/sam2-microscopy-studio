import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


EXTRACTED_MATCHING_FUNCTIONS = [
    "duplicateImageStems",
    "hasDuplicateImageName",
    "localAnnotationCandidates",
    "localAnnotationCandidate",
]


def test_annotation_matching_loads_after_file_utils_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    file_utils_tag = '<script src="static/fileUtils.js"></script>'
    matching_tag = '<script src="static/annotationMatching.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert file_utils_tag in index_html
    assert matching_tag in index_html
    assert script_tag in index_html
    assert index_html.index(file_utils_tag) < index_html.index(matching_tag)
    assert index_html.index(matching_tag) < index_html.index(script_tag)


def test_main_script_uses_annotation_matching_without_duplicate_bodies():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const annotationMatching = window.SAM2AnnotationMatching;" in script_js
    for function_name in EXTRACTED_MATCHING_FUNCTIONS:
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


def test_annotation_matching_resolves_local_source_matches():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute annotationMatching.js")

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
        vm.runInContext(fs.readFileSync('static/fileUtils.js', 'utf8'), context);
        vm.runInContext(fs.readFileSync('static/annotationMatching.js', 'utf8'), context);

        const matching = context.window.SAM2AnnotationMatching;
        assert.ok(matching);

        const files = [
            { name: 'cells_annotations.csv', webkitRelativePath: 'Labels/cells_annotations.csv' },
            { name: 'Plate_A__cells_annotations.csv', webkitRelativePath: 'Labels/Plate_A__cells_annotations.csv' },
            { name: 'other_annotations.csv', webkitRelativePath: 'Labels/other_annotations.csv' }
        ];
        const source = matching.buildLocalAnnotationSource(files, { phiSafeMode: false });
        assert.strictEqual(source.mode, 'local');
        assert.strictEqual(source.displayName, '3 files from Labels');
        assert.strictEqual(source.fileMap.get('cells_annotations.csv').length, 1);
        assert.strictEqual(matching.localAnnotationSourceActive(source), true);
        assert.strictEqual(
            matching.annotationSourceTitle(source, { phiSafeMode: true }),
            'PHI-safe mode hides local annotation source paths.'
        );

        const images = [
            { id: 'a', name: 'cells.tif', displayPath: 'Plate A/cells.tif' },
            { id: 'b', name: 'cells.tif', displayPath: 'Plate B/cells.tif' },
            { id: 'c', name: 'other.tif', displayPath: 'Plate C/other.tif' }
        ];
        const duplicateStems = matching.duplicateImageStems(images);
        assert.deepStrictEqual(Array.from(duplicateStems), ['cells']);
        assert.strictEqual(matching.hasDuplicateImageName(images, images[0]), true);
        assert.strictEqual(matching.hasDuplicateImageName(images, images[2]), false);
        assert.strictEqual(matching.annotationMatchModeForImage(images[0], images, null), 'path');
        assert.strictEqual(matching.annotationMatchModeForImage(images[2], images, null), 'basename');
        assert.strictEqual(
            matching.annotationMatchModeForImage(images[0], images, { status: 'matched', match_mode: 'basename' }),
            'basename'
        );

        const duplicatePathMatch = matching.resolveLocalAnnotationMatch(
            images[0],
            duplicateStems,
            'csv',
            source.fileMap,
            {
                name: 'public-a.tif',
                displayPath: 'public-a.tif',
                annotationPath: path => `safe:${path}`
            }
        );
        assert.strictEqual(duplicatePathMatch.status, 'matched');
        assert.strictEqual(duplicatePathMatch.match_mode, 'path');
        assert.strictEqual(duplicatePathMatch.path, 'safe:Labels/Plate_A__cells_annotations.csv');
        assert.strictEqual(duplicatePathMatch.name, 'public-a.tif');
        assert.strictEqual(duplicatePathMatch.display_path, 'public-a.tif');

        const duplicateBaseOnly = matching.resolveLocalAnnotationMatch(
            images[1],
            duplicateStems,
            'csv',
            source.fileMap
        );
        assert.strictEqual(duplicateBaseOnly.status, 'ambiguous');
        assert.strictEqual(duplicateBaseOnly.match_mode, 'basename');
        assert.ok(duplicateBaseOnly.message.includes('Duplicate image name'));

        const baseMatch = matching.resolveLocalAnnotationMatch(
            images[2],
            duplicateStems,
            'csv',
            source.fileMap
        );
        assert.strictEqual(baseMatch.status, 'matched');
        assert.strictEqual(baseMatch.match_mode, 'basename');

        const duplicateFilesSource = matching.buildLocalAnnotationSource([
            { name: 'other_annotations.csv' },
            { name: 'other_annotations.csv' }
        ]);
        const ambiguousDuplicateFile = matching.resolveLocalAnnotationMatch(
            images[2],
            duplicateStems,
            'csv',
            duplicateFilesSource.fileMap
        );
        assert.strictEqual(ambiguousDuplicateFile.status, 'ambiguous');
        assert.strictEqual(ambiguousDuplicateFile.ambiguous, true);

        const summary = matching.summarizeMatchResults([
            duplicatePathMatch,
            duplicateBaseOnly,
            { status: 'missing' }
        ]);
        assert.deepStrictEqual(plain(summary), { total: 3, matched: 1, missing: 1, ambiguous: 1 });

        const matchesByImage = new Map([
            ['a', duplicatePathMatch],
            ['b', duplicateBaseOnly],
            ['c', { status: 'missing' }]
        ]);
        assert.deepStrictEqual(
            plain(matching.recomputeMatchSummaryFromMatches(images, matchesByImage)),
            { total: 3, matched: 1, missing: 1, ambiguous: 1 }
        );
        assert.strictEqual(matching.recomputeMatchSummaryFromMatches([], matchesByImage), null);
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
