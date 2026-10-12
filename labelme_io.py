"""Labelme polygon interchange, without requiring Labelme or Qt at runtime."""

import hashlib
import json
from copy import deepcopy
from pathlib import PureWindowsPath

from annotation_io import MAX_CLASS_NAME_LENGTH
from review_io import default_review_status, validate_review_status
from segmentation_io import MAX_OBJECTS, normalize_geometry

STUDIO_KEY = "microscopy_studio"
ROOT_FIELDS = {"version", "imagePath", "imageData", "imageWidth", "imageHeight", "shapes", STUDIO_KEY}
SHAPE_FIELDS = {"label", "points", "shape_type", STUDIO_KEY}


def image_basename(value):
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError("An image filename is required")
    name = PureWindowsPath(value).name
    if name in ("", ".", ".."):
        raise ValueError("An image filename is required")
    return name


def _flags(value):
    if value is not None and (not isinstance(value, dict) or any(type(v) is not bool for v in value.values())):
        raise ValueError("Labelme flags must be an object of boolean values")


def inspect_labelme(raw, image, image_name):
    """Validate the entire file before any class or annotation is changed."""
    if not isinstance(raw, dict) or not isinstance(raw.get("shapes"), list):
        raise ValueError("Expected Labelme JSON with a shapes list")
    if len(raw["shapes"]) > MAX_OBJECTS:
        raise ValueError("Too many shapes in Labelme JSON")
    for field, expected in (("imageWidth", image["width"]), ("imageHeight", image["height"])):
        if type(raw.get(field)) is not int or raw[field] != expected:
            raise ValueError("Labelme image dimensions do not match the open image")
    if image_basename(raw.get("imagePath")) != image_basename(image_name):
        raise ValueError("Labelme imagePath does not match the open image filename")
    _flags(raw.get("flags"))
    studio = raw.get(STUDIO_KEY)
    if isinstance(studio, dict) and isinstance(studio.get("image"), dict):
        if studio["image"].get("identity") != image["identity"]:
            raise ValueError("This Labelme file was exported for a different source image")
    unsupported = []
    labels = []
    for index, shape in enumerate(raw["shapes"], 1):
        if not isinstance(shape, dict):
            raise ValueError(f"Shape {index} must be an object")
        kind = shape.get("shape_type", "polygon")
        if kind not in ("polygon", "rectangle", "circle") or shape.get("mask") is not None:
            unsupported.append(f"{index} ({'mask' if shape.get('mask') is not None else kind})")
            continue
        label = shape.get("label")
        if not isinstance(label, str) or not label.strip() or label != label.strip() or len(label) > MAX_CLASS_NAME_LENGTH:
            raise ValueError(f"Shape {index} needs a non-empty class label of at most {MAX_CLASS_NAME_LENGTH} characters, without surrounding spaces")
        _flags(shape.get("flags"))
        group = shape.get("group_id")
        if group is not None and type(group) is not int:
            raise ValueError(f"Shape {index}: group_id must be an integer or null")
        if shape.get("description") is not None and not isinstance(shape["description"], str):
            raise ValueError(f"Shape {index}: description must be text")
        try:
            normalize_geometry({"type": kind, "points": shape.get("points")}, image["width"], image["height"])
        except ValueError as error:
            raise ValueError(f"Shape {index} ({label}): {error}") from None
        if label not in labels:
            labels.append(label)
    if unsupported:
        raise ValueError("Unsupported Labelme shapes: " + ", ".join(unsupported[:20]) +
                         ". Only polygons, rectangles and circles can be imported. Nothing was imported.")
    return labels


def import_labelme(raw, *, image, image_name, project_id, classes, next_object_id):
    inspect_labelme(raw, image, image_name)
    class_ids = {item["name"]: item["id"] for item in classes}
    annotations = []
    for shape in raw["shapes"]:
        if shape["label"] not in class_ids:
            raise ValueError(f"Could not create class: {shape['label']}")
        annotations.append({"id": next_object_id, "class_id": class_ids[shape["label"]],
                            "source": "imported", "edited": False,
                            "geometry": {"type": shape.get("shape_type", "polygon"), "points": deepcopy(shape["points"])},
                            "labelme": {k: deepcopy(v) for k, v in shape.items() if k not in SHAPE_FIELDS}})
        next_object_id += 1
    return {"schema_version": 1, "task_type": "instance_segmentation", "project_id": project_id,
            "image": deepcopy(image), "next_object_id": next_object_id, "annotations": annotations,
            "labelme": {k: deepcopy(v) for k, v in raw.items() if k not in ROOT_FIELDS},
            **({"review_status": labelme_review_status(raw, project_id)} if isinstance(raw.get(STUDIO_KEY), dict)
               and "review_status" in raw[STUDIO_KEY] else {})}


def labelme_review_status(raw, project_id):
    """Completion belongs to this project and these exact saved shapes."""
    metadata = raw.get(STUDIO_KEY)
    shapes = raw.get("shapes", [])
    fallback = default_review_status(shapes)
    if not isinstance(metadata, dict) or metadata.get("project_id") != project_id:
        return fallback
    image = metadata.get("image")
    if not isinstance(image, dict):
        return fallback
    if metadata.get("review_hash") != _review_hash(shapes, metadata.get("project_id"), image):
        return fallback
    return validate_review_status(metadata.get("review_status"), shapes, image.get("identity"),
                                  (image.get("width"), image.get("height")))


def _review_hash(shapes, project_id, image):
    # Browser JSON round trips turn 20.0 into 20 without changing the shape.
    def normalize(value):
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return int(value) if isinstance(value, float) and value.is_integer() else value

    context = {"shapes": shapes, "project_id": project_id, "image": image}
    return hashlib.sha256(json.dumps(normalize(context), sort_keys=True, allow_nan=False).encode()).hexdigest()


def export_labelme(document, classes, image_path):
    names = {item["id"]: item["name"] for item in classes}
    shapes = []
    for item in document["annotations"]:
        shapes.append({"flags": {}, "group_id": None, "description": "", "mask": None,
                       **deepcopy(item.get("labelme", {})), "label": names[item["class_id"]],
                       "points": deepcopy(item["geometry"]["points"]), "shape_type": item["geometry"]["type"],
                       STUDIO_KEY: {**{key: item[key] for key in ("id", "class_id", "source", "edited")},
                                    "labelme_keys": list(item["labelme"]) if "labelme" in item else None}})
    return {"flags": {}, **deepcopy(document.get("labelme", {})), "version": "5.5.0",
            "imagePath": image_basename(image_path), "imageData": None,
            "imageWidth": document["image"]["width"], "imageHeight": document["image"]["height"],
            "shapes": shapes,
            STUDIO_KEY: {**{key: deepcopy(document[key]) for key in
                         ("schema_version", "task_type", "project_id", "image", "next_object_id")},
                         "labelme_keys": list(document["labelme"]) if "labelme" in document else None,
                         **({"review_status": document["review_status"]} if "review_status" in document else {}),
                         "review_hash": _review_hash(shapes, document["project_id"], document["image"])}}


def decode_autosave(raw):
    """App autosaves carry IDs/provenance as optional Labelme extension fields."""
    metadata = raw.get(STUDIO_KEY)
    if not isinstance(metadata, dict):
        raise ValueError("External Labelme files must be opened with Import Labelme JSON")
    document = deepcopy(metadata)
    document.pop("review_hash", None)
    if "review_status" in metadata:
        document["review_status"] = labelme_review_status(raw, metadata.get("project_id"))
    root_keys = document.pop("labelme_keys", None)
    if raw.get("imageWidth") != document.get("image", {}).get("width") or raw.get("imageHeight") != document.get("image", {}).get("height"):
        raise ValueError("Autosave image dimensions do not match")
    if not isinstance(raw.get("shapes"), list):
        raise ValueError("Invalid autosave shapes")
    document["annotations"] = []
    for shape in raw["shapes"]:
        if not isinstance(shape, dict) or shape.get("shape_type") not in ("polygon", "rectangle", "circle") or not isinstance(shape.get(STUDIO_KEY), dict):
            raise ValueError("This file was changed outside the app; use Import Labelme JSON")
        annotation = {**deepcopy(shape[STUDIO_KEY]), "geometry": {"type": shape["shape_type"], "points": shape.get("points")}}
        keys = annotation.pop("labelme_keys", None)
        extra = {k: deepcopy(v) for k, v in shape.items() if k not in SHAPE_FIELDS}
        if keys is not None:
            if not isinstance(keys, list) or any(not isinstance(key, str) or key not in extra for key in keys):
                raise ValueError("Invalid autosave shape metadata")
            annotation["labelme"] = {key: extra[key] for key in keys}
        document["annotations"].append(annotation)
    extra = {k: deepcopy(v) for k, v in raw.items() if k not in ROOT_FIELDS}
    if root_keys is not None:
        if not isinstance(root_keys, list) or any(not isinstance(key, str) or key not in extra for key in root_keys):
            raise ValueError("Invalid autosave metadata")
        document["labelme"] = {key: extra[key] for key in root_keys}
    return document
