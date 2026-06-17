"""Validate the runtime setup for the SAM2 annotation web app."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG = PROJECT_ROOT / "models" / "sam2.1_hiera_l.yaml"
MODEL_CHECKPOINT = PROJECT_ROOT / "models" / "sam2.1_hiera_large.pt"

REQUIRED_IMPORTS = {
    "cv2": "opencv-python-headless",
    "flask": "flask",
    "flask_cors": "flask-cors",
    "hydra": "hydra-core",
    "iopath": "iopath",
    "numpy": "numpy",
    "omegaconf": "omegaconf",
    "PIL": "pillow",
    "torch": "torch",
    "torchvision": "torchvision",
}


def check_imports() -> list[str]:
    errors = []
    for module_name, package_name in REQUIRED_IMPORTS.items():
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            errors.append(f"Missing or broken import {module_name!r} from {package_name}: {exc}")
    return errors


def check_models() -> list[str]:
    errors = []
    if not MODEL_CONFIG.exists():
        errors.append(f"Missing SAM2 config: {MODEL_CONFIG}")
    if not MODEL_CHECKPOINT.exists():
        errors.append(f"Missing SAM2 checkpoint: {MODEL_CHECKPOINT}")
    elif MODEL_CHECKPOINT.stat().st_size == 0:
        errors.append(f"SAM2 checkpoint is empty: {MODEL_CHECKPOINT}")
    return errors


def cuda_status() -> str:
    try:
        torch = importlib.import_module("torch")
        if torch.cuda.is_available():
            return f"CUDA available: {torch.cuda.get_device_name(0)}"
        return "CUDA not available; SAM2 will run on CPU."
    except Exception as exc:
        return f"CUDA status unavailable: {exc}"


def main() -> int:
    errors = check_imports() + check_models()
    if errors:
        print("Setup check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Setup check passed.")
    print(cuda_status())
    print(f"Project root: {PROJECT_ROOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
