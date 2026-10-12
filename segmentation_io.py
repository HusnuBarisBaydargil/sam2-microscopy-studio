"""Versioned, lossless polygon documents, independent of dataset export formats."""

import json
import math
import uuid
from copy import deepcopy

from atomic_io import atomic_write_file, read_with_backup
from review_io import validate_review_status

SCHEMA_VERSION = 1
MAX_OBJECTS = 10000
MAX_POLYGON_POINTS = 512
MAX_IMAGE_DIMENSION = 1000000


def _integer(value, name, maximum=None):
    if type(value) is not int or value < 1 or (maximum and value > maximum):
        raise ValueError(f"{name} must be a positive integer within supported limits")
    return value


def _fields(value, required, optional=()):
    if not isinstance(value, dict):
        raise ValueError("Expected an object")
    if not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError("Missing or unsupported document fields")


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, p):
    return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])


def _intersects(a, b, c, d):
    abc, abd, cda, cdb = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    if ((abc > 0 > abd) or (abd > 0 > abc)) and ((cda > 0 > cdb) or (cdb > 0 > cda)):
        return True
    return any((
        abc == 0 and _on_segment(a, b, c), abd == 0 and _on_segment(a, b, d),
        cda == 0 and _on_segment(c, d, a), cdb == 0 and _on_segment(c, d, b),
    ))


def normalize_polygon(geometry, width, height):
    """Preserve vertex order/precision; reject invalid geometry rather than repair it."""
    _fields(geometry, ("type", "points"))
    if geometry["type"] != "polygon":
        raise ValueError("Only polygon geometry is supported in this schema")
    points = geometry["points"]
    if not isinstance(points, list) or not 3 <= len(points) <= MAX_POLYGON_POINTS:
        raise ValueError(f"Polygon needs 3 to {MAX_POLYGON_POINTS} points")
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Each polygon point must contain x and y")
        for value, limit in zip(point, (width, height)):
            if type(value) not in (int, float) or not 0 <= value <= limit or not math.isfinite(value):
                raise ValueError("Polygon coordinates must be finite numbers inside the image")
    if len({tuple(point) for point in points}) != len(points):
        numbers = ", ".join(str(index + 1) for index, point in enumerate(points) if points.count(point) > 1)
        raise ValueError(f"Points {numbers} overlap at the same location. Move or remove the extra point. To close the outline, use Finish instead of adding the first point again.")
    count = len(points)
    for i, a in enumerate(points):
        b = points[(i + 1) % count]
        c = points[(i + 2) % count]
        if _cross(a, b, c) == 0 and sum((a[k] - b[k]) * (c[k] - b[k]) for k in (0, 1)) > 0:
            raise ValueError("Polygon edges must not overlap")
        for j in range(i + 2, count):
            if i == 0 and j == count - 1:
                continue
            if _intersects(a, b, points[j], points[(j + 1) % count]):
                raise ValueError("Polygon must not self-intersect or touch itself")
    area = abs(sum(_cross(points[0], points[i], points[i + 1]) for i in range(1, count - 1))) / 2
    if area == 0:
        raise ValueError("Polygon must have positive area")
    xs, ys = zip(*points)
    bbox = [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]
    return {"type": "polygon", "points": [point.copy() for point in points]}, bbox, area


def manual_split_polygon(geometry, start, end, cut_points, width, height):
    """Cut a polygon without rasterization, simplification or boundary changes."""
    original, _, original_area = normalize_polygon(geometry, width, height)
    points = original["points"]

    def anchor(value):
        _fields(value, ("edge", "t"))
        edge, fraction = value["edge"], value["t"]
        if type(edge) is not int or not 0 <= edge < len(points):
            raise ValueError("Cut anchor edge is outside the polygon")
        if type(fraction) not in (int, float) or not math.isfinite(fraction) or not 0 <= fraction < 1:
            raise ValueError("Cut anchor position must be between 0 and 1 (exclusive)")
        a, b = points[edge], points[(edge + 1) % len(points)]
        return edge + fraction, [a[i] + fraction * (b[i] - a[i]) for i in (0, 1)]

    begin, first = anchor(start)
    finish, last = anchor(end)
    if first == last:
        raise ValueError("Choose two different cut anchors")
    if not isinstance(cut_points, list) or len(cut_points) > MAX_POLYGON_POINTS - 2:
        raise ValueError(f"Cut supports at most {MAX_POLYGON_POINTS - 2} interior points")
    if any(not isinstance(point, list) or len(point) != 2 for point in cut_points):
        raise ValueError("Each cut point must contain x and y")

    def arc(from_position, to_position, a, b):
        limit = to_position if to_position > from_position else to_position + len(points)
        return [a] + [points[vertex % len(points)] for vertex in range(math.floor(from_position) + 1, math.ceil(limit))] + [b]

    def signed_area(vertices):
        return sum(_cross(vertices[0], vertices[i], vertices[i + 1]) for i in range(1, len(vertices) - 1)) / 2

    forward = arc(begin, finish, first, last)
    backward = arc(finish, begin, last, first)
    candidates = [forward + cut_points[::-1], [first] + cut_points + [last] + backward[1:-1]]
    result, total_area = [], 0
    for vertices in candidates:
        child, _, area = normalize_polygon({"type": "polygon", "points": vertices}, width, height)
        if signed_area(child["points"]) * signed_area(points) <= 0:
            raise ValueError("Cut must stay inside the original outline")
        result.append(child)
        total_area += area
    if not math.isclose(total_area, original_area, rel_tol=1e-9, abs_tol=1e-8):
        raise ValueError("Cut must divide the original outline without adding or removing area")
    return result


def normalize_geometry(geometry, width, height):
    """Keep Labelme's native two-point rectangles and circles lossless."""
    _fields(geometry, ("type", "points"))
    kind = geometry["type"]
    if kind == "polygon":
        return normalize_polygon(geometry, width, height)
    if kind not in ("rectangle", "circle"):
        raise ValueError("Unsupported geometry type")
    points = geometry["points"]
    if not isinstance(points, list) or len(points) != 2:
        raise ValueError(f"{kind} needs exactly two points")
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Each shape point must contain x and y")
        for value, limit in zip(point, (width, height)):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= limit:
                raise ValueError("Shape coordinates must be finite numbers inside the image")
    (x1, y1), (x2, y2) = points
    if kind == "rectangle":
        bbox = [min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)]
        area = bbox[2] * bbox[3]
    else:
        radius = math.hypot(x2 - x1, y2 - y1)
        bbox = [x1 - radius, y1 - radius, 2 * radius, 2 * radius]
        if x1 - radius < 0 or y1 - radius < 0 or x1 + radius > width or y1 + radius > height:
            raise ValueError("Circle must fit inside the image")
        area = math.pi * radius * radius
    if area <= 0:
        raise ValueError("Shape must have positive area")
    return {"type": kind, "points": deepcopy(points)}, bbox, area


def normalize_segmentation_document(document, *, project_id, image_identity, image_size, class_ids):
    """Validate against the intended project/image and its current stable class IDs."""
    _fields(document, ("schema_version", "task_type", "project_id", "image", "next_object_id", "annotations"), ("labelme", "review_status"))
    if type(document["schema_version"]) is not int or document["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported segmentation schema_version")
    if document["task_type"] != "instance_segmentation":
        raise ValueError("Expected instance_segmentation task_type")
    try:
        uuid.UUID(project_id)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("project_id must be a UUID") from None
    if document["project_id"] != project_id:
        raise ValueError("Document belongs to another project")
    image = document["image"]
    _fields(image, ("identity", "width", "height"))
    if not isinstance(image_identity, str) or not image_identity.strip() or image["identity"] != image_identity:
        raise ValueError("Document belongs to another image or has no image identity")
    width = _integer(image["width"], "image width", MAX_IMAGE_DIMENSION)
    height = _integer(image["height"], "image height", MAX_IMAGE_DIMENSION)
    if (width, height) != tuple(image_size):
        raise ValueError("Document dimensions do not match the image")
    valid_classes = {_integer(value, "class ID") for value in class_ids}
    next_id = _integer(document["next_object_id"], "next_object_id")
    annotations = document["annotations"]
    if not isinstance(annotations, list) or len(annotations) > MAX_OBJECTS:
        raise ValueError("annotations must be a list within the object limit")
    result, used_ids = [], set()
    for annotation in annotations:
        _fields(annotation, ("id", "class_id", "geometry"), ("source", "edited", "bbox", "area", "labelme"))
        object_id = _integer(annotation["id"], "object ID")
        if object_id in used_ids or object_id >= next_id:
            raise ValueError("Object IDs must be unique and smaller than next_object_id")
        used_ids.add(object_id)
        class_id = _integer(annotation["class_id"], "class ID")
        if class_id not in valid_classes:
            raise ValueError("Object references an unknown class ID")
        source = annotation.get("source", "manual")
        edited = annotation.get("edited", False)
        if source not in ("manual", "sam2", "imported") or type(edited) is not bool:
            raise ValueError("Invalid object source or edited flag")
        geometry, bbox, area = normalize_geometry(annotation["geometry"], width, height)
        result.append({"id": object_id, "class_id": class_id, "geometry": geometry,
                       "source": source, "edited": edited, "bbox": bbox, "area": area})
        if "labelme" in annotation:
            result[-1]["labelme"] = _metadata(annotation["labelme"])
    normalized = {"schema_version": SCHEMA_VERSION, "task_type": "instance_segmentation",
            "project_id": project_id, "image": image.copy(), "next_object_id": next_id,
            "annotations": result}
    if "labelme" in document:
        normalized["labelme"] = _metadata(document["labelme"])
    if "review_status" in document:
        normalized["review_status"] = validate_review_status(document["review_status"], result, image_identity, image_size)
    return normalized


def _metadata(value):
    if not isinstance(value, dict):
        raise ValueError("Labelme metadata must be an object")
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError("Labelme metadata must contain finite JSON values") from None
    return deepcopy(value)


def load_segmentation_document(path, **context):
    def read(candidate):
        with open(candidate, encoding="utf-8") as file:
            return decode_segmentation_document(json.load(file), **context)

    return read_with_backup(path, read)


def decode_segmentation_document(raw, **context):
    """Read legacy native files and our Labelme-compatible autosaves."""
    if isinstance(raw, dict) and "shapes" in raw:
        from labelme_io import decode_autosave

        raw = decode_autosave(raw)
    return normalize_segmentation_document(raw, **context)


def save_segmentation_document(path, document, *, classes=None, image_path=None, **context):
    normalized = normalize_segmentation_document(document, **context)
    payload = normalized
    if classes is not None:
        from labelme_io import export_labelme

        payload = export_labelme(normalized, classes, image_path or "image.png")

    def validate(candidate):
        with open(candidate, encoding="utf-8") as file:
            decode_segmentation_document(json.load(file), **context)

    def write(candidate):
        with open(candidate, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, allow_nan=False)

    atomic_write_file(path, write, validator=validate)
    return normalized
