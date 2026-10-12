"""Convert SAM contours to the editor's single, simple polygon representation."""

import cv2
import numpy as np

from segmentation_io import MAX_POLYGON_POINTS, normalize_geometry, normalize_polygon


def polygon_proposals(masks, width, height):
    proposals, skipped = [], 0
    for mask in masks:
        if not mask.get("polygon_supported", False):
            skipped += 1
            continue
        contour = np.asarray(mask["contour"], dtype=np.float32).reshape(-1, 1, 2)
        # Bound approximation to two source pixels. Never replace a failed outline
        # with its convex hull: that can join distinct cells or erase concavities.
        for tolerance in (0.5, 1.0, 2.0):
            points = cv2.approxPolyDP(contour, tolerance, True).reshape(-1, 2).tolist()
            if not 3 <= len(points) <= MAX_POLYGON_POINTS:
                continue
            try:
                geometry, bbox, area = normalize_polygon({"type": "polygon", "points": points}, width, height)
            except ValueError:
                continue
            proposals.append({"id": len(proposals) + 1, "geometry": geometry, "bbox": bbox, "area": area})
            break
        else:
            skipped += 1
    return proposals, skipped


def geometry_mask(geometry, width, height):
    """Rasterize validated editor geometry at source-image resolution."""
    geometry, _, _ = normalize_geometry(geometry, width, height)
    mask = np.zeros((height, width), dtype=np.uint8)
    points = np.rint(geometry["points"]).astype(np.int32)
    if geometry["type"] == "polygon":
        cv2.fillPoly(mask, [points], 1)
    elif geometry["type"] == "rectangle":
        cv2.rectangle(mask, tuple(points[0]), tuple(points[1]), 1, -1)
    else:
        radius = round(float(np.linalg.norm(np.asarray(geometry["points"][1]) - geometry["points"][0])))
        cv2.circle(mask, tuple(points[0]), radius, 1, -1)
    return mask


def mask_contour(mask):
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) != 1:
        return {"polygon_supported": False}
    return {"polygon_supported": True, "contour": contours[0].reshape(-1, 2).tolist()}


def merge_geometries(geometries, width, height):
    if not isinstance(geometries, list) or not 2 <= len(geometries) <= 100:
        raise ValueError("Select 2–100 touching or overlapping objects to merge.")
    union = np.zeros((height, width), dtype=np.uint8)
    for geometry in geometries:
        union |= geometry_mask(geometry, width, height)
    proposals, skipped = polygon_proposals([mask_contour(union)], width, height)
    if skipped or not proposals:
        raise ValueError("Merge needs one connected outline without holes. Select touching or overlapping objects.")
    return proposals[0]["geometry"]
