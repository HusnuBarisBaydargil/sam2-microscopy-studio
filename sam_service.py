import os
import threading

import cv2
import numpy as np
import torch
from hydra.utils import instantiate
from omegaconf import OmegaConf

from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator

DEFAULT_SAM_DEVICE = os.environ.get("SAM_DEVICE", "auto").strip().lower() or "auto"
SUPPORTED_SAM_DEVICES = {"auto", "cuda", "cpu"}

DEFAULT_SAM_PRESET = "cell_1920x1440"
SAM_PRESETS = {
    "cell_1920x1440": {
        "label": "Cell 1920x1440",
        "description": "Current default tuned for the original cell workflow.",
        "params": {
            "points_per_side": 64,
            "crop_n_layers": 2,
            "min_mask_region_area": 400,
            "crop_overlap_ratio": 0.4,
            "crop_n_points_downscale_factor": 2,
            "points_per_batch": 64,
            "pred_iou_thresh": 0.92,
            "stability_score_thresh": 0.92,
            "stability_score_offset": 1.0,
            "box_nms_thresh": 0.5,
            "crop_nms_thresh": 0.5,
            "use_m2m": True,
            "area_mode": "pixels",
            "min_overall_area": 300,
            "max_overall_area": 30000,
        },
    },
    "general_balanced": {
        "label": "General balanced",
        "description": "Moderate density for varied image types.",
        "params": {
            "points_per_side": 32,
            "crop_n_layers": 1,
            "min_mask_region_area": 100,
            "crop_overlap_ratio": 0.35,
            "crop_n_points_downscale_factor": 2,
            "points_per_batch": 64,
            "pred_iou_thresh": 0.88,
            "stability_score_thresh": 0.90,
            "stability_score_offset": 1.0,
            "box_nms_thresh": 0.5,
            "crop_nms_thresh": 0.5,
            "use_m2m": True,
            "area_mode": "percent",
            "min_overall_area": 0.02,
            "max_overall_area": 5.0,
        },
    },
    "small_image_512": {
        "label": "Small image 512",
        "description": "Lower area filters and moderate density for small images.",
        "params": {
            "points_per_side": 32,
            "crop_n_layers": 1,
            "min_mask_region_area": 20,
            "crop_overlap_ratio": 0.35,
            "crop_n_points_downscale_factor": 2,
            "points_per_batch": 64,
            "pred_iou_thresh": 0.88,
            "stability_score_thresh": 0.88,
            "stability_score_offset": 1.0,
            "box_nms_thresh": 0.5,
            "crop_nms_thresh": 0.5,
            "use_m2m": True,
            "area_mode": "pixels",
            "min_overall_area": 20,
            "max_overall_area": 6000,
        },
    },
    "high_recall": {
        "label": "High recall",
        "description": "More permissive filtering; can be slower and noisier.",
        "params": {
            "points_per_side": 64,
            "crop_n_layers": 2,
            "min_mask_region_area": 50,
            "crop_overlap_ratio": 0.45,
            "crop_n_points_downscale_factor": 2,
            "points_per_batch": 64,
            "pred_iou_thresh": 0.82,
            "stability_score_thresh": 0.86,
            "stability_score_offset": 1.0,
            "box_nms_thresh": 0.45,
            "crop_nms_thresh": 0.45,
            "use_m2m": True,
            "area_mode": "percent",
            "min_overall_area": 0.005,
            "max_overall_area": 8.0,
        },
    },
    "fast_preview": {
        "label": "Fast preview",
        "description": "Lower density and no crop layers for quick first pass.",
        "params": {
            "points_per_side": 24,
            "crop_n_layers": 0,
            "min_mask_region_area": 100,
            "crop_overlap_ratio": 0.3,
            "crop_n_points_downscale_factor": 2,
            "points_per_batch": 64,
            "pred_iou_thresh": 0.90,
            "stability_score_thresh": 0.92,
            "stability_score_offset": 1.0,
            "box_nms_thresh": 0.5,
            "crop_nms_thresh": 0.5,
            "use_m2m": True,
            "area_mode": "percent",
            "min_overall_area": 0.02,
            "max_overall_area": 5.0,
        },
    },
}

SAM_NUMERIC_LIMITS = {
    "points_per_side": ("int", 8, 128),
    "crop_n_layers": ("int", 0, 3),
    "min_mask_region_area": ("int", 0, 1000000),
    "crop_overlap_ratio": ("float", 0.0, 0.9),
    "crop_n_points_downscale_factor": ("int", 1, 8),
    "points_per_batch": ("int", 16, 256),
    "pred_iou_thresh": ("float", 0.0, 1.0),
    "stability_score_thresh": ("float", 0.0, 1.0),
    "stability_score_offset": ("float", 0.0, 2.0),
    "box_nms_thresh": ("float", 0.0, 1.0),
    "crop_nms_thresh": ("float", 0.0, 1.0),
}


class SamInferenceBusyError(RuntimeError):
    pass


class SamInferenceTimeoutError(RuntimeError):
    pass


def default_sam_settings():
    return {
        "preset": DEFAULT_SAM_PRESET,
        "params": dict(SAM_PRESETS[DEFAULT_SAM_PRESET]["params"]),
    }


def sam_presets_response():
    return [
        {
            "key": key,
            "label": preset["label"],
            "description": preset["description"],
            "params": dict(preset["params"]),
        }
        for key, preset in SAM_PRESETS.items()
    ]


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _coerce_number(value, key, value_type):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be a number")
    return int(round(number)) if value_type == "int" else number


def _normalize_bounded_number(value, key, value_type, minimum, maximum, warnings):
    number = _coerce_number(value, key, value_type)
    original = number
    if number < minimum:
        number = minimum
    if number > maximum:
        number = maximum
    if number != original:
        warnings.append(f"{key} was clamped to {number}.")
    return number


def normalize_sam_settings(raw_settings=None):
    raw_settings = raw_settings if isinstance(raw_settings, dict) else {}
    preset = str(raw_settings.get("preset") or DEFAULT_SAM_PRESET).strip()
    if preset not in SAM_PRESETS and preset != "custom":
        preset = DEFAULT_SAM_PRESET

    base_preset = DEFAULT_SAM_PRESET if preset == "custom" else preset
    base_params = dict(SAM_PRESETS[base_preset]["params"])
    raw_params = raw_settings.get("params")
    if not isinstance(raw_params, dict):
        raw_params = {}

    params = {}
    warnings = []
    for key, (value_type, minimum, maximum) in SAM_NUMERIC_LIMITS.items():
        value = raw_params.get(key, base_params.get(key))
        params[key] = _normalize_bounded_number(value, key, value_type, minimum, maximum, warnings)

    params["use_m2m"] = _coerce_bool(raw_params.get("use_m2m", base_params.get("use_m2m", True)))
    area_mode = str(raw_params.get("area_mode", base_params.get("area_mode", "pixels"))).strip().lower()
    params["area_mode"] = "percent" if area_mode == "percent" else "pixels"

    area_minimum = 0.0
    area_maximum = 100.0 if params["area_mode"] == "percent" else 100000000.0
    params["min_overall_area"] = _normalize_bounded_number(
        raw_params.get("min_overall_area", base_params.get("min_overall_area", 0)),
        "min_overall_area",
        "float",
        area_minimum,
        area_maximum,
        warnings,
    )
    params["max_overall_area"] = _normalize_bounded_number(
        raw_params.get("max_overall_area", base_params.get("max_overall_area", area_maximum)),
        "max_overall_area",
        "float",
        area_minimum,
        area_maximum,
        warnings,
    )
    if params["min_overall_area"] > params["max_overall_area"]:
        raise ValueError("min_overall_area cannot be greater than max_overall_area")

    warnings.extend(_sam_risk_warnings(params))
    return {"preset": preset, "params": params, "warnings": warnings}


def _sam_risk_warnings(params):
    warnings = []
    if params["points_per_side"] > 96:
        warnings.append("points_per_side above 96 can be slow and memory intensive.")
    if params["crop_n_layers"] > 2:
        warnings.append("crop_n_layers above 2 can greatly increase runtime and GPU memory usage.")
    if params["points_per_batch"] > 128:
        warnings.append("points_per_batch above 128 can trigger GPU out-of-memory errors.")
    if params["pred_iou_thresh"] < 0.75:
        warnings.append("low pred_iou_thresh can produce many noisy masks.")
    if params["stability_score_thresh"] < 0.75:
        warnings.append("low stability_score_thresh can produce unstable masks.")
    return warnings


def effective_filter_areas(image_np, params):
    if params["area_mode"] == "percent":
        image_area = float(image_np.shape[0] * image_np.shape[1])
        min_area = int(round(image_area * params["min_overall_area"] / 100.0))
        max_area = int(round(image_area * params["max_overall_area"] / 100.0))
    else:
        min_area = int(round(params["min_overall_area"]))
        max_area = int(round(params["max_overall_area"]))
    return max(0, min_area), max(0, max_area)


def normalize_sam_device(value=None):
    default_device = DEFAULT_SAM_DEVICE if DEFAULT_SAM_DEVICE in SUPPORTED_SAM_DEVICES else "auto"
    device = str(value or default_device).strip().lower()
    if device not in SUPPORTED_SAM_DEVICES:
        supported = ", ".join(sorted(SUPPORTED_SAM_DEVICES))
        raise ValueError(f"sam_device must be one of: {supported}")
    return device


class SAMModelHandler:
    def __init__(self, cfg_path, checkpoint_path, requested_device=None, skip_model_load=False, display_path=str):
        self.model = None
        self.cfg_path = cfg_path
        self.checkpoint_path = checkpoint_path
        self.requested_device = normalize_sam_device(requested_device)
        self.skip_model_load = skip_model_load
        self.display_path = display_path
        self.device = torch.device("cpu")
        self.last_error = None
        self._lock = threading.RLock()
        if self.skip_model_load:
            try:
                self.device = self._resolve_device(self.requested_device)
            except Exception as e:
                self.last_error = str(e)
                print(f"FATAL: {self.last_error}")
            print("INFO: SKIP_SAM_MODEL_LOAD=1; SAM2 model initialization skipped.")
        else:
            self._initialize_model()

    def _resolve_device(self, requested_device):
        if requested_device == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if requested_device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested for SAM2, but CUDA is not available.")
        return torch.device(requested_device)

    def _initialize_model(self):
        with self._lock:
            self.model = None
            self.last_error = None
            try:
                self.device = self._resolve_device(self.requested_device)
            except Exception as e:
                self.last_error = str(e)
                print(f"FATAL: {self.last_error}")
                return

        if not os.path.exists(self.cfg_path):
            self.last_error = f"SAM2 config not found: {self.display_path(self.cfg_path)}"
            print(f"FATAL: {self.last_error}")
            print("FATAL: Place sam2.1_hiera_l.yaml under models/ or update SAM_CONFIG_PATH.")
            return
        if not os.path.exists(self.checkpoint_path):
            self.last_error = f"SAM2 checkpoint not found: {self.display_path(self.checkpoint_path)}"
            print(f"FATAL: {self.last_error}")
            print("FATAL: Place sam2.1_hiera_large.pt under models/ or update SAM_CHECKPOINT_PATH.")
            return

        try:
            cfg = OmegaConf.load(self.cfg_path)
            model = instantiate(cfg.model, _recursive_=True)

            state_dict = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)["model"]
            model.load_state_dict(state_dict)

            model = model.to(self.device)
            model.eval()
            with self._lock:
                self.model = model

            print(f"INFO: SUCCESS: SAM2 model loaded successfully on {self.device}.")
        except Exception as e:
            self.last_error = f"Could not load SAM2 model. Error: {e}"
            print(f"FATAL: {self.last_error}")
            with self._lock:
                self.model = None

    def set_requested_device(self, requested_device):
        requested_device = normalize_sam_device(requested_device)
        if requested_device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested for SAM2, but CUDA is not available.")
        with self._lock:
            if requested_device == self.requested_device and self.device == self._resolve_device(requested_device):
                return
            self.requested_device = requested_device
        if self.skip_model_load:
            with self._lock:
                self.device = self._resolve_device(self.requested_device)
            return
        self._initialize_model()

    def status(self):
        with self._lock:
            return {
                "mode": self.requested_device,
                "active": str(self.device),
                "cuda_available": torch.cuda.is_available(),
                "ready": self.is_ready(),
                "model_load_skipped": self.skip_model_load,
                "error": self.last_error,
            }

    def is_ready(self):
        return self.model is not None

    def generate_masks(self, image_np, sam_settings):
        with self._lock:
            if not self.is_ready():
                raise RuntimeError("SAM2 model is not initialized.")
            params = sam_settings["params"]
            mask_generator = SAM2AutomaticMaskGenerator(
                model=self.model,
                points_per_side=params["points_per_side"],
                crop_n_layers=params["crop_n_layers"],
                min_mask_region_area=params["min_mask_region_area"],
                points_per_batch=params["points_per_batch"],
                pred_iou_thresh=params["pred_iou_thresh"],
                stability_score_thresh=params["stability_score_thresh"],
                stability_score_offset=params["stability_score_offset"],
                box_nms_thresh=params["box_nms_thresh"],
                crop_nms_thresh=params["crop_nms_thresh"],
                crop_overlap_ratio=params["crop_overlap_ratio"],
                crop_n_points_downscale_factor=params["crop_n_points_downscale_factor"],
                use_m2m=params["use_m2m"],
            )
            raw_masks = mask_generator.generate(image_np)
        filtered_masks = []
        min_area, max_area = effective_filter_areas(image_np, params)
        for mask_data in raw_masks:
            if not (min_area <= mask_data["area"] <= max_area):
                continue
            contours, _ = cv2.findContours(mask_data["segmentation"].astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            largest_contour = max(contours, key=cv2.contourArea)
            contour_points = largest_contour.reshape(-1, 2).tolist()
            bounding_box = cv2.boundingRect(largest_contour)
            filtered_masks.append({
                "contour": contour_points,
                "bbox": list(bounding_box),
                "mask_area": int(mask_data.get("area", 0)),
                "source": "sam2",
                "predicted_iou": float(mask_data["predicted_iou"]) if "predicted_iou" in mask_data else None,
                "stability_score": float(mask_data["stability_score"]) if "stability_score" in mask_data else None,
            })
        return filtered_masks
