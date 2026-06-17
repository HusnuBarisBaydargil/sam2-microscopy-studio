import io
import os

import cv2
import numpy as np
from PIL import Image
from werkzeug.utils import secure_filename


def _positive_int_env(name, default):
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


MAX_DECODED_IMAGE_PIXELS = _positive_int_env("MAX_DECODED_IMAGE_PIXELS", 25_000_000)
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/bmp",
    "image/x-ms-bmp",
    "image/tiff",
    "image/x-tiff",
}
ALLOWED_PIL_IMAGE_FORMATS = {"JPEG", "PNG", "BMP", "TIFF"}


def _uploaded_image_extension(file_storage):
    filename = secure_filename(file_storage.filename or "")
    return os.path.splitext(filename)[1].lower()


def _validate_uploaded_image_file(file_storage):
    extension = _uploaded_image_extension(file_storage)
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        raise ValueError(f"unsupported image extension; allowed extensions are: {allowed}")

    mimetype = (file_storage.mimetype or "").lower()
    if mimetype and mimetype != "application/octet-stream" and mimetype not in ALLOWED_IMAGE_MIME_TYPES:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_MIME_TYPES))
        raise ValueError(f"unsupported image MIME type; allowed MIME types are: {allowed}")


def _decoded_pixel_count(width, height):
    try:
        width = int(width)
        height = int(height)
    except (TypeError, ValueError):
        raise ValueError("image dimensions must be numeric")
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
    return width * height


def _validate_decoded_image_size(width, height, context="image"):
    pixel_count = _decoded_pixel_count(width, height)
    if pixel_count > MAX_DECODED_IMAGE_PIXELS:
        raise ValueError(
            f"{context} has {pixel_count} decoded pixels; limit is {MAX_DECODED_IMAGE_PIXELS}."
        )


def _inspect_encoded_image_size(image_bytes, context="image"):
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.format not in ALLOWED_PIL_IMAGE_FORMATS:
                allowed = ", ".join(sorted(ALLOWED_PIL_IMAGE_FORMATS))
                raise ValueError(f"{context} format must be one of: {allowed}")
            _validate_decoded_image_size(image.width, image.height, context=context)
    except ValueError:
        raise
    except Exception:
        return


def _decode_pil_rgb_image(image_bytes, context="image"):
    with Image.open(io.BytesIO(image_bytes)) as image:
        if image.format not in ALLOWED_PIL_IMAGE_FORMATS:
            allowed = ", ".join(sorted(ALLOWED_PIL_IMAGE_FORMATS))
            raise ValueError(f"{context} format must be one of: {allowed}")
        _validate_decoded_image_size(image.width, image.height, context=context)
        return image.convert("RGB")


def _decode_cv2_bgr_image(image_bytes, context="image"):
    _inspect_encoded_image_size(image_bytes, context=context)
    image_array = np.frombuffer(image_bytes, np.uint8)
    bgr_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if bgr_image is None:
        raise ValueError("Failed to decode image")
    height, width = bgr_image.shape[:2]
    _validate_decoded_image_size(width, height, context=context)
    return bgr_image
