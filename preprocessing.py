import json

import cv2
import numpy as np

PREPROCESS_METHODS = {
    "clahe": "CLAHE",
    "gamma": "Gamma",
    "clahe_unsharp": "CLAHE + Unsharp",
    "gamma_unsharp": "Gamma + Unsharp",
    "retinex_mild": "Retinex mild",
}

PREPROCESS_DEFAULT_PARAMS = {
    "clahe_clip_limit": 2.0,
    "clahe_tile_grid_size": 8,
    "gamma": 1.2,
    "unsharp_amount": 0.8,
    "unsharp_radius": 1.2,
    "unsharp_threshold": 3,
    "retinex_strength": 0.55,
}


def _bounded_float(value, fallback, minimum, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if not np.isfinite(number):
        return fallback
    return min(max(number, minimum), maximum)


def _bounded_int(value, fallback, minimum, maximum):
    return int(round(_bounded_float(value, fallback, minimum, maximum)))


def _normalize_preprocess_method(value):
    method = str(value or "clahe").strip().lower()
    if method not in PREPROCESS_METHODS:
        raise ValueError(f"preprocess method must be one of: {', '.join(PREPROCESS_METHODS.keys())}")
    return method


def _normalize_preprocess_params(raw_params=None):
    raw_params = raw_params if isinstance(raw_params, dict) else {}
    params = dict(PREPROCESS_DEFAULT_PARAMS)
    params["clahe_clip_limit"] = _bounded_float(raw_params.get("clahe_clip_limit"), params["clahe_clip_limit"], 0.5, 8.0)
    params["clahe_tile_grid_size"] = _bounded_int(raw_params.get("clahe_tile_grid_size"), params["clahe_tile_grid_size"], 2, 32)
    params["gamma"] = _bounded_float(raw_params.get("gamma"), params["gamma"], 0.2, 3.0)
    params["unsharp_amount"] = _bounded_float(raw_params.get("unsharp_amount"), params["unsharp_amount"], 0.0, 3.0)
    params["unsharp_radius"] = _bounded_float(raw_params.get("unsharp_radius"), params["unsharp_radius"], 0.3, 6.0)
    params["unsharp_threshold"] = _bounded_int(raw_params.get("unsharp_threshold"), params["unsharp_threshold"], 0, 255)
    params["retinex_strength"] = _bounded_float(raw_params.get("retinex_strength"), params["retinex_strength"], 0.1, 1.0)
    return params


def _apply_clahe_bgr(bgr_image, params):
    lab_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab_image)
    tile_size = params["clahe_tile_grid_size"]
    clahe = cv2.createCLAHE(
        clipLimit=params["clahe_clip_limit"],
        tileGridSize=(tile_size, tile_size),
    )
    enhanced_l = clahe.apply(l_channel)
    merged_lab = cv2.merge([enhanced_l, a_channel, b_channel])
    return cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)


def _apply_gamma_bgr(bgr_image, params):
    gamma = max(params["gamma"], 0.01)
    lookup = ((np.arange(256, dtype=np.float32) / 255.0) ** (1.0 / gamma) * 255.0)
    return cv2.LUT(bgr_image, np.clip(lookup, 0, 255).astype(np.uint8))


def _apply_unsharp_bgr(bgr_image, params):
    amount = params["unsharp_amount"]
    if amount <= 0:
        return bgr_image
    blurred = cv2.GaussianBlur(bgr_image, (0, 0), sigmaX=params["unsharp_radius"])
    sharpened = cv2.addWeighted(bgr_image, 1.0 + amount, blurred, -amount, 0)
    threshold = params["unsharp_threshold"]
    if threshold <= 0:
        return sharpened
    delta = cv2.absdiff(bgr_image, blurred)
    mask = cv2.cvtColor(delta, cv2.COLOR_BGR2GRAY) > threshold
    return np.where(mask[:, :, None], sharpened, bgr_image)


def _apply_retinex_mild_bgr(bgr_image, params):
    image = bgr_image.astype(np.float32) + 1.0
    retinex = np.zeros_like(image)
    for sigma in (15, 80, 250):
        blur = cv2.GaussianBlur(image, (0, 0), sigmaX=sigma, sigmaY=sigma)
        retinex += np.log(image) - np.log(blur + 1.0)
    retinex /= 3.0

    normalized_channels = []
    for channel_index in range(3):
        channel = retinex[:, :, channel_index]
        normalized = cv2.normalize(channel, None, 0, 255, cv2.NORM_MINMAX)
        normalized_channels.append(normalized)
    retinex_bgr = cv2.merge(normalized_channels).astype(np.uint8)
    strength = params["retinex_strength"]
    return cv2.addWeighted(bgr_image, 1.0 - strength, retinex_bgr, strength, 0)


def _preprocess_bgr_image(bgr_image, method, params):
    method = _normalize_preprocess_method(method)
    params = _normalize_preprocess_params(params)

    if method == "clahe":
        processed = _apply_clahe_bgr(bgr_image, params)
    elif method == "gamma":
        processed = _apply_gamma_bgr(bgr_image, params)
    elif method == "clahe_unsharp":
        processed = _apply_unsharp_bgr(_apply_clahe_bgr(bgr_image, params), params)
    elif method == "gamma_unsharp":
        processed = _apply_unsharp_bgr(_apply_gamma_bgr(bgr_image, params), params)
    elif method == "retinex_mild":
        processed = _apply_retinex_mild_bgr(bgr_image, params)
    else:
        raise ValueError("unsupported preprocess method")

    return np.clip(processed, 0, 255).astype(np.uint8), params


def _preprocess_request_from_form(form):
    method = str(form.get("preprocess_method") or form.get("method") or "original").strip().lower()
    if method in ("", "original", "none"):
        return "original", {}

    raw_params = {}
    if form.get("preprocess_params"):
        try:
            raw_params = json.loads(form.get("preprocess_params"))
        except json.JSONDecodeError:
            raise ValueError("preprocess_params must be valid JSON")
    elif form.get("params"):
        try:
            raw_params = json.loads(form.get("params"))
        except json.JSONDecodeError:
            raise ValueError("params must be valid JSON")

    return _normalize_preprocess_method(method), raw_params


def _apply_optional_preprocessing_for_sam(bgr_image, form):
    method, raw_params = _preprocess_request_from_form(form)
    if method == "original":
        return bgr_image, {"method": "original", "label": "Original", "params": {}}

    processed_bgr, params = _preprocess_bgr_image(bgr_image, method, raw_params)
    return processed_bgr, {
        "method": method,
        "label": PREPROCESS_METHODS[method],
        "params": params,
    }
