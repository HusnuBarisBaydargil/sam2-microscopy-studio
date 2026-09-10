import json

import pytest

from review_io import (
    invalidate_review,
    load_review,
    save_review,
    validate_review_status,
)


@pytest.fixture
def review_file(tmp_path):
    path = tmp_path / "image.csv"
    path.write_text("annotations", encoding="utf-8")
    context = {
        "project_id": "project-a", "image_identity": "image-a:123", "image_size": (100, 80),
        "classes": [{"id": 1, "name": "cell", "color": "red"}],
    }
    return path, context


@pytest.mark.parametrize("status,annotations", [("reviewed", [{}]), ("confirmed_empty", [])])
def test_review_round_trip(review_file, status, annotations):
    path, context = review_file
    save_review(path, status, **context)
    assert load_review(path, annotations, **context) == status


@pytest.mark.parametrize("change", ["file", "project_id", "image_identity", "image_size", "classes", "corrupt", "invalidated"])
def test_stale_reviews_fall_back(review_file, change):
    path, context = review_file
    save_review(path, "reviewed", **context)
    if change == "file":
        path.write_text("different annotations", encoding="utf-8")
    elif change == "corrupt":
        path.with_name(path.name + ".review.json").write_text("broken", encoding="utf-8")
    elif change == "invalidated":
        invalidate_review(path)
    else:
        context[change] = {"project_id": "other", "image_identity": "other", "image_size": (10, 10),
                           "classes": [{"id": 1, "name": "renamed"}]}[change]
    assert load_review(path, [{}], **context) == "in_progress"
    assert load_review(path, [], **context) == "unreviewed"


def test_display_class_changes_preserve_review(review_file):
    path, context = review_file
    save_review(path, "reviewed", **context)
    context["classes"][0].update(color="blue", hotkey="x")
    assert load_review(path, [{}], **context) == "reviewed"


def test_missing_sidecar_never_infers_review(review_file):
    path, context = review_file
    assert load_review(path, [{}], **context) == "in_progress"
    assert load_review(path, [], **context) == "unreviewed"


def test_identity_is_hashed_in_sidecar(review_file):
    path, context = review_file
    save_review(path, "reviewed", **context)
    serialized = path.with_name(path.name + ".review.json").read_text(encoding="utf-8")
    assert context["image_identity"] not in serialized
    assert len(json.loads(serialized)["image_identity_sha256"]) == 64
    assert load_review(path, [{}], **context) == "reviewed"


@pytest.mark.parametrize("status,annotations,identity,size", [
    ("reviewed", [], "id", (10, 10)), ("confirmed_empty", [{}], "id", (10, 10)),
    ("reviewed", [{}], None, (10, 10)), ("confirmed_empty", [], "id", None),
    ("confirmed_empty", [], "id", (0, 10)), ("bogus", [], "id", (10, 10)),
])
def test_invalid_completion_rejected(status, annotations, identity, size):
    with pytest.raises(ValueError):
        validate_review_status(status, annotations, identity, size)


def test_sidecar_backup_is_not_used(review_file):
    path, context = review_file
    save_review(path, "reviewed", **context)
    sidecar = path.with_name(path.name + ".review.json")
    backup = path.with_name(path.name + ".review.json.bak")
    backup.write_text(sidecar.read_text(encoding="utf-8"), encoding="utf-8")
    sidecar.write_text(json.dumps({"review_status": "unreviewed"}), encoding="utf-8")
    assert load_review(path, [{}], **context) == "in_progress"
