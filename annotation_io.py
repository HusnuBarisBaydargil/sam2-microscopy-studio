import csv
import json
import os
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

import numpy as np

SUPPORTED_ANNOTATION_FORMATS = {
    "csv": {"label": "Simple CSV", "extension": "csv"},
    "csv_rich": {"label": "Rich CSV", "extension": "csv"},
    "yolo": {"label": "YOLO TXT", "extension": "txt"},
    "coco": {"label": "COCO JSON", "extension": "json"},
    "voc": {"label": "Pascal VOC XML", "extension": "xml"},
}


def _positive_int_env(name, default):
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


MAX_ANNOTATIONS_PER_SAVE = _positive_int_env("MAX_ANNOTATIONS_PER_SAVE", 100000)
MAX_CLASSES_PER_PROJECT = _positive_int_env("MAX_CLASSES_PER_PROJECT", 500)
MAX_CLASS_NAME_LENGTH = _positive_int_env("MAX_CLASS_NAME_LENGTH", 128)
MAX_BBOX_ABS_VALUE = float(_positive_int_env("MAX_BBOX_ABS_VALUE", 1000000000))

DEFAULT_CLASS_COLORS = [
    "#39d353",
    "#9ca3af",
    "#58a6ff",
    "#f2cc60",
    "#ff7b72",
    "#d2a8ff",
    "#56d4dd",
    "#ffa657",
]


def _spreadsheet_safe_cell(value):
    text = str(value if value is not None else "")
    return f"'{text}" if re.match(r"^\s*[=+\-@]", text) else text


def _normalize_annotation_format(value):
    annotation_format = str(value or "csv").strip().lower()
    if annotation_format not in SUPPORTED_ANNOTATION_FORMATS:
        supported = ", ".join(SUPPORTED_ANNOTATION_FORMATS.keys())
        raise ValueError(f"annotation_format must be one of: {supported}")
    return annotation_format


def _is_clean_text(value):
    return all(ord(char) >= 32 and ord(char) != 127 for char in value)


def _normalize_class_name(value, fallback="Unlabeled"):
    class_name = str(value or fallback).strip() or fallback
    if len(class_name) > MAX_CLASS_NAME_LENGTH:
        raise ValueError(f"class name cannot exceed {MAX_CLASS_NAME_LENGTH} characters")
    if not _is_clean_text(class_name):
        raise ValueError("class name cannot contain control characters")
    return class_name


def _normalize_class_color(value):
    color = str(value or "#9ca3af").strip()
    if len(color) > 32 or not color.startswith("#") or not _is_clean_text(color):
        return "#9ca3af"
    return color


def _normalize_hotkey(value):
    hotkey = str(value or "").strip().lower()[:1]
    return hotkey if _is_clean_text(hotkey) else ""


def _normalize_classes(raw_classes):
    if not isinstance(raw_classes, list):
        return []

    normalized_classes = []
    seen_names = set()
    for item in raw_classes[:MAX_CLASSES_PER_PROJECT]:
        if not isinstance(item, dict):
            continue
        try:
            name = _normalize_class_name(item.get("name"), fallback="")
        except ValueError:
            continue
        if not name or name in seen_names:
            continue
        color = _normalize_class_color(item.get("color"))
        hotkey = _normalize_hotkey(item.get("hotkey"))
        normalized_classes.append({"name": name, "color": color, "hotkey": hotkey})
        seen_names.add(name)

    return normalized_classes


def _classes_with_annotation_labels(raw_classes, annotations):
    classes = _normalize_classes(raw_classes)
    seen_names = {class_info["name"] for class_info in classes}
    used_hotkeys = {class_info["hotkey"] for class_info in classes if class_info.get("hotkey")}

    for annotation in annotations:
        if len(classes) >= MAX_CLASSES_PER_PROJECT:
            break
        try:
            class_name = _normalize_class_name(annotation.get("class"))
        except ValueError:
            continue
        if class_name in seen_names:
            continue

        hotkey = ""
        for candidate in (class_name.lower().replace(" ", "") + "abcdefghijklmnopqrstuvwxyz0123456789"):
            if candidate.isalnum() and candidate not in used_hotkeys:
                hotkey = candidate
                break

        if hotkey:
            used_hotkeys.add(hotkey)
        classes.append({
            "name": class_name,
            "color": DEFAULT_CLASS_COLORS[len(classes) % len(DEFAULT_CLASS_COLORS)],
            "hotkey": hotkey,
        })
        seen_names.add(class_name)

    return classes


def _parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_finite_number(value):
    return isinstance(value, (int, float)) and np.isfinite(value)


def _normalize_bbox(raw_bbox, field_name="bbox", allow_flip=False):
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        raise ValueError(f"{field_name} must contain four numeric values")

    try:
        bbox = [float(value) for value in raw_bbox]
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must contain only numeric values")

    if not all(_is_finite_number(value) for value in bbox):
        raise ValueError(f"{field_name} values must be finite numbers")

    if allow_flip:
        if bbox[2] < 0:
            bbox[0] += bbox[2]
            bbox[2] = abs(bbox[2])
        if bbox[3] < 0:
            bbox[1] += bbox[3]
            bbox[3] = abs(bbox[3])

    if bbox[2] <= 0 or bbox[3] <= 0:
        raise ValueError(f"{field_name} width and height must be greater than zero")

    if any(abs(value) > MAX_BBOX_ABS_VALUE for value in bbox):
        raise ValueError(f"{field_name} values are too large")

    return bbox


def _image_size_from_values(width, height, required=False, context="annotations"):
    image_width = _parse_float(width)
    image_height = _parse_float(height)
    if (
        _is_finite_number(image_width)
        and _is_finite_number(image_height)
        and image_width > 0
        and image_height > 0
    ):
        return int(round(image_width)), int(round(image_height))
    if required:
        raise ValueError(f"image width and height are required for {context}")
    return None


def _clamp_bbox_to_image(raw_bbox, image_size, field_name="bbox"):
    bbox = _normalize_bbox(raw_bbox, field_name=field_name, allow_flip=True)
    dimensions = _image_size_from_values(
        *(image_size or (None, None)),
        required=False,
        context=field_name,
    )
    if not dimensions:
        return bbox

    image_width, image_height = dimensions
    x, y, w, h = bbox
    x_min = max(0.0, min(float(image_width), x))
    y_min = max(0.0, min(float(image_height), y))
    x_max = max(0.0, min(float(image_width), x + w))
    y_max = max(0.0, min(float(image_height), y + h))

    if x_max <= x_min or y_max <= y_min:
        raise ValueError(f"{field_name} is outside the image bounds")

    return [x_min, y_min, x_max - x_min, y_max - y_min]


def _clamp_annotations_to_image(annotations, image_size):
    dimensions = _image_size_from_values(
        *(image_size or (None, None)),
        required=False,
        context="annotations",
    )
    if not dimensions:
        return annotations, 0

    clamped_annotations = []
    changed_count = 0
    for index, annotation in enumerate(annotations):
        original_bbox = annotation.get("bbox")
        clamped_bbox = _clamp_bbox_to_image(
            original_bbox,
            dimensions,
            field_name=f"annotations[{index}].bbox",
        )
        normalized_bbox = _normalize_bbox(
            original_bbox,
            field_name=f"annotations[{index}].bbox",
            allow_flip=True,
        )
        bbox_changed = any(abs(normalized_bbox[item] - clamped_bbox[item]) > 1e-9 for item in range(4))
        if bbox_changed:
            changed_count += 1
        clamped_annotation = {**annotation, "bbox": clamped_bbox}
        if bbox_changed:
            clamped_annotation.pop("contour", None)
            clamped_annotation.pop("mask_area", None)
        clamped_annotations.append(clamped_annotation)

    return clamped_annotations, changed_count


def _normalize_contour(raw_contour, field_name="contour"):
    if raw_contour in (None, ""):
        return None
    if isinstance(raw_contour, str):
        try:
            raw_contour = json.loads(raw_contour)
        except json.JSONDecodeError:
            raise ValueError(f"{field_name} must be valid JSON")
    if not isinstance(raw_contour, list):
        raise ValueError(f"{field_name} must be a list of points")

    contour = []
    for point_index, point in enumerate(raw_contour):
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise ValueError(f"{field_name}[{point_index}] must contain x and y")
        try:
            x = float(point[0])
            y = float(point[1])
        except (TypeError, ValueError):
            raise ValueError(f"{field_name}[{point_index}] must contain numeric x and y")
        if not _is_finite_number(x) or not _is_finite_number(y):
            raise ValueError(f"{field_name}[{point_index}] values must be finite")
        if abs(x) > MAX_BBOX_ABS_VALUE or abs(y) > MAX_BBOX_ABS_VALUE:
            raise ValueError(f"{field_name}[{point_index}] values are too large")
        contour.append([x, y])

    if len(contour) < 3:
        return None
    return contour


def _optional_finite_number(value):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if _is_finite_number(number) else None


def _contour_matches_bbox(contour, bbox, tolerance=1.5):
    if not contour or not bbox:
        return False
    x, y, width, height = _normalize_bbox(bbox)
    x_values = [point[0] for point in contour]
    y_values = [point[1] for point in contour]
    contour_bounds = (min(x_values), min(y_values), max(x_values), max(y_values))
    bbox_bounds = (x, y, x + width, y + height)
    return all(
        abs(contour_value - bbox_value) <= tolerance
        for contour_value, bbox_value in zip(contour_bounds, bbox_bounds)
    )


def _segmentation_from_contour(contour):
    normalized = _normalize_contour(contour)
    if not normalized:
        return None
    return [[coordinate for point in normalized for coordinate in point]]


def _contour_from_coco_segmentation(segmentation):
    if not isinstance(segmentation, list) or not segmentation:
        return None
    polygon = segmentation[0] if isinstance(segmentation[0], list) else segmentation
    if not isinstance(polygon, list) or len(polygon) < 6:
        return None
    points = []
    for index in range(0, len(polygon) - 1, 2):
        points.append([polygon[index], polygon[index + 1]])
    return _normalize_contour(points)


def _annotation_mask_metadata(annotation, bbox=None):
    metadata = {}
    raw_contour_present = annotation.get("contour") not in (None, "")
    contour_is_consistent = True

    try:
        contour = _normalize_contour(annotation.get("contour"))
    except ValueError:
        contour = None
    if raw_contour_present and (not contour or (bbox is not None and not _contour_matches_bbox(contour, bbox))):
        contour_is_consistent = False
    if contour:
        if contour_is_consistent:
            metadata["contour"] = contour

    for source_key, target_key in (
        ("mask_area", "mask_area"),
        ("predicted_iou", "predicted_iou"),
        ("stability_score", "stability_score"),
    ):
        if target_key == "mask_area" and not contour_is_consistent:
            continue
        number = _optional_finite_number(annotation.get(source_key))
        if number is not None:
            metadata[target_key] = number

    source = str(annotation.get("source") or "").strip()[:64]
    if source and _is_clean_text(source):
        metadata["source"] = source

    return metadata


def _normalize_annotation_payload(annotation, index):
    if not isinstance(annotation, dict):
        raise ValueError(f"annotations[{index}] must be an object")

    bbox = _normalize_bbox(annotation.get("bbox"), field_name=f"annotations[{index}].bbox")
    class_name = _normalize_class_name(annotation.get("class"))
    annotation_id = annotation.get("id", index + 1)
    try:
        annotation_id_number = float(annotation_id)
    except (TypeError, ValueError):
        raise ValueError(f"annotations[{index}].id must be a positive integer")
    if (
        not _is_finite_number(annotation_id_number)
        or annotation_id_number <= 0
        or not annotation_id_number.is_integer()
    ):
        raise ValueError(f"annotations[{index}].id must be a positive integer")
    annotation_id = int(annotation_id_number)

    annotation_type = str(annotation.get("type") or "manual").strip()[:64]
    if not _is_clean_text(annotation_type):
        annotation_type = "manual"

    normalized = {
        "id": annotation_id,
        "bbox": bbox,
        "class": class_name,
        "type": annotation_type,
    }
    normalized.update(_annotation_mask_metadata(annotation, bbox=bbox))
    return normalized


def _normalize_annotations_payload(annotations):
    if not isinstance(annotations, list):
        raise ValueError("annotations must be a list")
    if len(annotations) > MAX_ANNOTATIONS_PER_SAVE:
        raise ValueError(f"annotations cannot contain more than {MAX_ANNOTATIONS_PER_SAVE} items")
    return [
        _normalize_annotation_payload(annotation, index)
        for index, annotation in enumerate(annotations)
    ]


def _annotation_from_csv_row(row, fallback_id):
    normalized = {str(key).strip().lower(): value for key, value in row.items() if key is not None}
    class_name = (
        normalized.get("class_label")
        or normalized.get("class")
        or normalized.get("label")
        or normalized.get("category")
        or ""
    ).strip()

    if {"x_min", "y_min", "x_max", "y_max"}.issubset(normalized):
        x_min = _parse_float(normalized.get("x_min"))
        y_min = _parse_float(normalized.get("y_min"))
        x_max = _parse_float(normalized.get("x_max"))
        y_max = _parse_float(normalized.get("y_max"))
        if None in (x_min, y_min, x_max, y_max):
            return None
        bbox = [x_min, y_min, x_max - x_min, y_max - y_min]
    elif {"x", "y", "w", "h"}.issubset(normalized):
        x = _parse_float(normalized.get("x"))
        y = _parse_float(normalized.get("y"))
        w = _parse_float(normalized.get("w"))
        h = _parse_float(normalized.get("h"))
        if None in (x, y, w, h):
            return None
        bbox = [x, y, w, h]
    else:
        return None

    try:
        bbox = _normalize_bbox(bbox, field_name="CSV bbox", allow_flip=True)
        class_name = _normalize_class_name(class_name)
    except ValueError:
        return None

    parsed_id = _parse_float(normalized.get("id"))
    annotation_id = int(parsed_id) if _is_finite_number(parsed_id) and parsed_id > 0 else fallback_id
    annotation = {
        "id": annotation_id,
        "bbox": bbox,
        "class": class_name or "Unlabeled",
        "type": "loaded",
    }
    metadata_input = {
        "contour": normalized.get("contour") or normalized.get("segmentation"),
        "mask_area": normalized.get("mask_area"),
        "source": normalized.get("source"),
        "predicted_iou": normalized.get("predicted_iou"),
        "stability_score": normalized.get("stability_score"),
    }
    annotation.update(_annotation_mask_metadata(metadata_input, bbox=bbox))
    return annotation


def _read_annotation_csv(path):
    annotations = []
    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for index, row in enumerate(reader, start=1):
            annotation = _annotation_from_csv_row(row, index)
            if annotation:
                annotations.append(annotation)
    return annotations


def _write_annotation_csv(path, image_name, annotations, include_metadata=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        header = [
            "source_image",
            "x_min",
            "y_min",
            "x_max",
            "y_max",
            "class_label",
        ]
        if include_metadata:
            header.extend([
                "contour",
                "mask_area",
                "source",
                "predicted_iou",
                "stability_score",
            ])
        writer.writerow(header)
        for annotation in annotations:
            x, y, w, h = _normalize_bbox(annotation.get("bbox"))
            row = [
                _spreadsheet_safe_cell(image_name),
                round(x),
                round(y),
                round(x + w),
                round(y + h),
                _spreadsheet_safe_cell(_normalize_class_name(annotation.get("class"))),
            ]
            if include_metadata:
                metadata = _annotation_mask_metadata(annotation, bbox=[x, y, w, h])
                row.extend([
                    json.dumps(metadata.get("contour", []), separators=(",", ":")) if metadata.get("contour") else "",
                    _format_number(metadata["mask_area"]) if "mask_area" in metadata else "",
                    _spreadsheet_safe_cell(metadata.get("source", "")),
                    _format_number(metadata["predicted_iou"]) if "predicted_iou" in metadata else "",
                    _format_number(metadata["stability_score"]) if "stability_score" in metadata else "",
                ])
            writer.writerow(row)


def _class_name_for_index(classes, class_index):
    if 0 <= class_index < len(classes):
        return classes[class_index]["name"]
    return f"class_{class_index}"


def _class_index_map(classes):
    return {class_info["name"]: index for index, class_info in enumerate(classes)}


def _format_number(value):
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _count_annotation_file(path, annotation_format="csv"):
    annotation_format = _normalize_annotation_format(annotation_format)
    if annotation_format in ("csv", "csv_rich"):
        return len(_read_annotation_csv(path))
    if annotation_format == "yolo":
        with open(path, "r", encoding="utf-8-sig") as file:
            return sum(
                1 for line in file
                if line.strip() and not line.lstrip().startswith("#") and len(line.split()) >= 5
            )
    if annotation_format == "coco":
        with open(path, "r", encoding="utf-8-sig") as file:
            data = json.load(file)
        annotations = data.get("annotations", []) if isinstance(data, dict) else []
        return len(annotations) if isinstance(annotations, list) else 0
    if annotation_format == "voc":
        root = ET.parse(path).getroot()
        return len(root.findall(".//object"))
    return 0


def _read_annotation_yolo(path, image_size, classes):
    image_width, image_height = _image_size_from_values(
        *(image_size or (None, None)),
        required=True,
        context="YOLO annotations",
    )
    annotations = []
    with open(path, "r", encoding="utf-8-sig") as file:
        for index, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                class_index = int(float(parts[0]))
                x_center = float(parts[1]) * image_width
                y_center = float(parts[2]) * image_height
                box_width = float(parts[3]) * image_width
                box_height = float(parts[4]) * image_height
                bbox = _normalize_bbox(
                    [
                        x_center - box_width / 2.0,
                        y_center - box_height / 2.0,
                        box_width,
                        box_height,
                    ],
                    field_name="YOLO bbox",
                )
                class_name = _normalize_class_name(_class_name_for_index(classes, class_index))
            except (TypeError, ValueError):
                continue
            annotations.append({
                "id": index,
                "bbox": bbox,
                "class": class_name,
                "type": "loaded",
            })
    return annotations


def _write_annotation_yolo(path, annotations, image_size, classes):
    image_width, image_height = _image_size_from_values(
        *(image_size or (None, None)),
        required=True,
        context="YOLO annotations",
    )
    annotations, _ = _clamp_annotations_to_image(annotations, (image_width, image_height))
    class_indices = _class_index_map(classes)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        for annotation in annotations:
            x, y, w, h = _normalize_bbox(annotation.get("bbox"))
            class_name = _normalize_class_name(annotation.get("class"))
            class_index = class_indices.get(class_name, 0)
            x_center = (x + w / 2.0) / image_width
            y_center = (y + h / 2.0) / image_height
            norm_width = w / image_width
            norm_height = h / image_height
            file.write(
                f"{class_index} {_format_number(x_center)} {_format_number(y_center)} "
                f"{_format_number(norm_width)} {_format_number(norm_height)}\n"
            )


def _matching_coco_image_ids(data, image_name):
    images = data.get("images", []) if isinstance(data, dict) else []
    if not isinstance(images, list):
        return set()
    if not images:
        return set()

    target = os.path.basename(image_name or "").lower()
    matched_ids = {
        image.get("id")
        for image in images
        if os.path.basename(str(image.get("file_name", ""))).lower() == target
    }
    if matched_ids:
        return matched_ids
    if len(images) == 1:
        return {images[0].get("id")}
    return set()


def _read_annotation_coco(path, image_name):
    with open(path, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        return []

    category_map = {}
    categories = data.get("categories", [])
    if isinstance(categories, list):
        for category in categories:
            if not isinstance(category, dict):
                continue
            category_id = category.get("id")
            name = str(category.get("name") or f"category_{category_id}").strip()
            category_map[category_id] = name

    image_ids = _matching_coco_image_ids(data, image_name)
    annotations = []
    raw_annotations = data.get("annotations", [])
    if not isinstance(raw_annotations, list):
        return annotations

    for index, raw_annotation in enumerate(raw_annotations, start=1):
        if not isinstance(raw_annotation, dict):
            continue
        if image_ids and raw_annotation.get("image_id") not in image_ids:
            continue
        try:
            bbox = _normalize_bbox(raw_annotation.get("bbox"), field_name="COCO bbox")
            category_id = raw_annotation.get("category_id")
            class_name = _normalize_class_name(category_map.get(category_id, f"category_{category_id}"))
        except ValueError:
            continue
        annotation_id = raw_annotation.get("id")
        if not isinstance(annotation_id, int) or annotation_id <= 0:
            annotation_id = index
        annotation = {
            "id": annotation_id,
            "bbox": bbox,
            "class": class_name,
            "type": "loaded",
        }
        try:
            contour = _contour_from_coco_segmentation(raw_annotation.get("segmentation"))
        except ValueError:
            contour = None
        metadata_input = {
            "contour": contour,
            "mask_area": raw_annotation.get("mask_area") or (raw_annotation.get("area") if contour else None),
            "source": raw_annotation.get("source"),
            "predicted_iou": raw_annotation.get("predicted_iou"),
            "stability_score": raw_annotation.get("stability_score"),
        }
        annotation.update(_annotation_mask_metadata(metadata_input, bbox=bbox))
        annotations.append(annotation)
    return annotations


def _write_annotation_coco(path, image_name, annotations, image_size, classes):
    image_size = _image_size_from_values(
        *(image_size or (None, None)),
        required=False,
        context="COCO annotations",
    )
    if image_size:
        annotations, _ = _clamp_annotations_to_image(annotations, image_size)
    image_width, image_height = image_size or (0, 0)
    class_indices = _class_index_map(classes)
    categories = [
        {"id": index + 1, "name": class_info["name"]}
        for index, class_info in enumerate(classes)
    ]
    coco_annotations = []
    for index, annotation in enumerate(annotations, start=1):
        x, y, w, h = _normalize_bbox(annotation.get("bbox"))
        class_name = _normalize_class_name(annotation.get("class"))
        category_id = class_indices.get(class_name, 0) + 1
        metadata = _annotation_mask_metadata(annotation, bbox=[x, y, w, h])
        segmentation = _segmentation_from_contour(metadata.get("contour"))
        area = metadata.get("mask_area", w * h)
        coco_annotation = {
            "id": index,
            "image_id": 1,
            "category_id": category_id,
            "bbox": [x, y, w, h],
            "area": area,
            "iscrowd": 0,
        }
        if segmentation:
            coco_annotation["segmentation"] = segmentation
        for key in ("source", "mask_area", "predicted_iou", "stability_score"):
            if key in metadata:
                coco_annotation[key] = metadata[key]
        coco_annotations.append(coco_annotation)
    payload = {
        "images": [{
            "id": 1,
            "file_name": image_name,
            "width": image_width,
            "height": image_height,
        }],
        "categories": categories,
        "annotations": coco_annotations,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def _read_annotation_voc(path):
    root = ET.parse(path).getroot()
    annotations = []
    for index, obj in enumerate(root.findall(".//object"), start=1):
        bndbox = obj.find("bndbox")
        if bndbox is None:
            continue
        try:
            x_min = _parse_float(bndbox.findtext("xmin"))
            y_min = _parse_float(bndbox.findtext("ymin"))
            x_max = _parse_float(bndbox.findtext("xmax"))
            y_max = _parse_float(bndbox.findtext("ymax"))
            if None in (x_min, y_min, x_max, y_max):
                continue
            bbox = _normalize_bbox([x_min, y_min, x_max - x_min, y_max - y_min], field_name="VOC bbox")
            class_name = _normalize_class_name(obj.findtext("name") or "Unlabeled")
        except ValueError:
            continue
        annotations.append({
            "id": index,
            "bbox": bbox,
            "class": class_name,
            "type": "loaded",
        })
    return annotations


def _write_annotation_voc(path, image_name, annotations, image_size):
    image_size = _image_size_from_values(
        *(image_size or (None, None)),
        required=False,
        context="VOC annotations",
    )
    if image_size:
        annotations, _ = _clamp_annotations_to_image(annotations, image_size)
    image_width, image_height = image_size or (0, 0)
    lines = [
        "<annotation>",
        f"  <filename>{xml_escape(image_name)}</filename>",
        "  <size>",
        f"    <width>{image_width}</width>",
        f"    <height>{image_height}</height>",
        "    <depth>3</depth>",
        "  </size>",
    ]
    for annotation in annotations:
        x, y, w, h = _normalize_bbox(annotation.get("bbox"))
        class_name = _normalize_class_name(annotation.get("class"))
        lines.extend([
            "  <object>",
            f"    <name>{xml_escape(class_name)}</name>",
            "    <pose>Unspecified</pose>",
            "    <truncated>0</truncated>",
            "    <difficult>0</difficult>",
            "    <bndbox>",
            f"      <xmin>{round(x)}</xmin>",
            f"      <ymin>{round(y)}</ymin>",
            f"      <xmax>{round(x + w)}</xmax>",
            f"      <ymax>{round(y + h)}</ymax>",
            "    </bndbox>",
            "  </object>",
        ])
    lines.append("</annotation>")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        file.write("\n".join(lines) + "\n")


def _read_annotation_file(path, annotation_format="csv", image_name="", image_size=None, classes=None):
    annotation_format = _normalize_annotation_format(annotation_format)
    classes = _normalize_classes(classes if classes is not None else [])
    if annotation_format in ("csv", "csv_rich"):
        return _read_annotation_csv(path)
    if annotation_format == "yolo":
        return _read_annotation_yolo(path, image_size, classes)
    if annotation_format == "coco":
        return _read_annotation_coco(path, image_name)
    if annotation_format == "voc":
        return _read_annotation_voc(path)
    return []


def _write_annotation_file(path, image_name, annotations, annotation_format="csv", image_size=None, classes=None):
    annotation_format = _normalize_annotation_format(annotation_format)
    classes = _normalize_classes(classes if classes is not None else [])
    normalized_image_size = _image_size_from_values(
        *(image_size or (None, None)),
        required=annotation_format == "yolo",
        context="YOLO annotations" if annotation_format == "yolo" else "annotations",
    )
    if normalized_image_size:
        annotations, _ = _clamp_annotations_to_image(annotations, normalized_image_size)
    if annotation_format == "csv":
        _write_annotation_csv(path, image_name, annotations, include_metadata=False)
    elif annotation_format == "csv_rich":
        _write_annotation_csv(path, image_name, annotations, include_metadata=True)
    elif annotation_format == "yolo":
        _write_annotation_yolo(path, annotations, normalized_image_size, classes)
    elif annotation_format == "coco":
        _write_annotation_coco(path, image_name, annotations, normalized_image_size, classes)
    elif annotation_format == "voc":
        _write_annotation_voc(path, image_name, annotations, normalized_image_size)
    else:
        raise ValueError("unsupported annotation format")
