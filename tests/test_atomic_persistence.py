import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

from annotation_io import (
    _count_annotation_file,
    _read_annotation_file,
    _write_annotation_file,
)
from annotation_paths import load_project_classes, save_project_classes
from atomic_io import atomic_write_file, backup_path, read_with_backup

REPO_ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def temporary_target(suffix):
    descriptor, raw_path = tempfile.mkstemp(prefix=".pytest-atomic-", suffix=suffix, dir=REPO_ROOT)
    os.close(descriptor)
    target = Path(raw_path)
    target.unlink()
    try:
        yield target
    finally:
        for candidate in (target, Path(backup_path(target))):
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass
        for candidate in target.parent.glob(f".{target.name}.*.tmp"):
            candidate.unlink()


def _validated_text(path):
    value = Path(path).read_text(encoding="utf-8")
    if value not in {"one", "two", "three"}:
        raise ValueError("invalid test content")
    return value


def test_atomic_write_preserves_previous_version_and_survives_failed_writes():
    with temporary_target(".txt") as target:
        atomic_write_file(
            target,
            lambda path: Path(path).write_text("one", encoding="utf-8"),
            validator=_validated_text,
        )
        assert target.read_text(encoding="utf-8") == "one"
        assert not Path(backup_path(target)).exists()

        atomic_write_file(
            target,
            lambda path: Path(path).write_text("two", encoding="utf-8"),
            validator=_validated_text,
        )
        assert target.read_text(encoding="utf-8") == "two"
        assert Path(backup_path(target)).read_text(encoding="utf-8") == "one"

        def interrupted_write(path):
            Path(path).write_text("partial", encoding="utf-8")
            raise OSError("simulated interruption")

        with pytest.raises(OSError, match="simulated interruption"):
            atomic_write_file(target, interrupted_write, validator=_validated_text)
        assert target.read_text(encoding="utf-8") == "two"
        assert Path(backup_path(target)).read_text(encoding="utf-8") == "one"

        with pytest.raises(ValueError, match="invalid test content"):
            atomic_write_file(
                target,
                lambda path: Path(path).write_text("invalid", encoding="utf-8"),
                validator=_validated_text,
            )
        assert target.read_text(encoding="utf-8") == "two"
        assert Path(backup_path(target)).read_text(encoding="utf-8") == "one"

        target.write_text("corrupt", encoding="utf-8")
        assert read_with_backup(target, _validated_text) == "one"
        atomic_write_file(
            target,
            lambda path: Path(path).write_text("three", encoding="utf-8"),
            validator=_validated_text,
        )
        assert target.read_text(encoding="utf-8") == "three"
        assert Path(backup_path(target)).read_text(encoding="utf-8") == "one"


@pytest.mark.parametrize(
    ("annotation_format", "suffix", "corrupt_content"),
    [
        ("csv", ".csv", "not,a,valid,header\n"),
        ("csv_rich", ".csv", "not,a,valid,header\n"),
        ("yolo", ".txt", "not valid\n"),
        ("coco", ".json", "{"),
        ("voc", ".xml", "<annotation>"),
    ],
)
def test_annotation_formats_fall_back_to_previous_valid_save(annotation_format, suffix, corrupt_content):
    classes = [
        {"name": "first", "color": "#39d353", "hotkey": "f"},
        {"name": "second", "color": "#58a6ff", "hotkey": "s"},
    ]
    first_annotations = [{"id": 1, "bbox": [10, 5, 20, 15], "class": "first", "type": "manual"}]
    second_annotations = [{"id": 1, "bbox": [20, 10, 25, 20], "class": "second", "type": "manual"}]

    with temporary_target(suffix) as target:
        for annotations in (first_annotations, second_annotations):
            _write_annotation_file(
                target,
                "cells.png",
                annotations,
                annotation_format,
                image_size=(100, 80),
                classes=classes,
            )

        assert Path(backup_path(target)).exists()
        target.write_text(corrupt_content, encoding="utf-8")
        recovered = _read_annotation_file(
            target,
            annotation_format,
            image_name="cells.png",
            image_size=(100, 80),
            classes=classes,
        )
        assert recovered[0]["class"] == "first"
        assert _count_annotation_file(target, annotation_format) == 1


def test_project_classes_fall_back_to_previous_valid_save():
    with temporary_target(".classes.json") as classes_path:
        first_classes = [{"name": "first", "color": "#39d353", "hotkey": "f"}]
        second_classes = [{"name": "second", "color": "#58a6ff", "hotkey": "s"}]
        save_project_classes(first_classes, classes_path)
        save_project_classes(second_classes, classes_path)
        classes_path.write_text("{", encoding="utf-8")
        assert load_project_classes(classes_path) == first_classes


def test_project_settings_fall_back_to_previous_valid_save():
    pytest.importorskip("hydra")
    from project_config import load_project_settings, save_project_settings

    with temporary_target(".settings.json") as settings_path:
        common = {
            "project_root": str(REPO_ROOT),
            "default_annotation_output_dir": "annotations",
            "allow_absolute_annotation_dir": False,
        }
        first_settings = {"annotation_output_dir": "annotations/first", "annotation_format": "csv"}
        second_settings = {"annotation_output_dir": "annotations/second", "annotation_format": "coco"}
        save_project_settings(first_settings, settings_path, **common)
        save_project_settings(second_settings, settings_path, **common)
        settings_path.write_text(json.dumps(["invalid settings shape"]), encoding="utf-8")
        recovered = load_project_settings(settings_path, **common)
        assert recovered["annotation_output_dir"] == "annotations/first"
        assert recovered["annotation_format"] == "csv"
