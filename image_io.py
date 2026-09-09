import io
import os

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename


def _positive_int_env(name, default):
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


MAX_DECODED_IMAGE_PIXELS = _positive_int_env("MAX_DECODED_IMAGE_PIXELS", 25_000_000)
ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".apng", ".bmp", ".dib",
    ".tif", ".tiff", ".webp", ".gif", ".jp2", ".j2k", ".jpc", ".jpf",
    ".jpx", ".j2c", ".pbm", ".pgm", ".ppm", ".pnm", ".pcx", ".tga",
    ".icb", ".vda", ".vst", ".sgi", ".rgb", ".rgba", ".bw", ".ico",
    ".qoi", ".xbm",
}
ALLOWED_PIL_IMAGE_FORMATS = {
    "JPEG", "PNG", "BMP", "DIB", "TIFF", "WEBP", "GIF", "JPEG2000",
    "PPM", "PCX", "TGA", "SGI", "ICO", "QOI", "XBM",
}


def _uploaded_image_extension(file_storage):
    filename = secure_filename(file_storage.filename or "")
    return os.path.splitext(filename)[1].lower()


def _validate_uploaded_image_file(file_storage):
    extension = _uploaded_image_extension(file_storage)
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        raise ValueError(f"unsupported image extension; allowed extensions are: {allowed}")

    # Browser/OS MIME guesses vary for formats such as TGA and PNM. The decoder
    # validates the actual encoded format instead of trusting the MIME label.


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


def _select_image_page(image, context):
    """Accept a 2D TIFF with an overview, without treating a stack as one image."""
    frame_count = getattr(image, "n_frames", 1)
    if frame_count == 1:
        return
    error = f"{context} contains multiple frames or pages; export a single 2D image first."
    if image.format != "TIFF" or frame_count != 2:
        raise ValueError(error)

    pages = []
    for index in range(frame_count):
        image.seek(index)
        pages.append((image.size, image.mode, image.tag_v2.get(254, 0), image.tag_v2.get(255)))
    primary = max(range(frame_count), key=lambda i: pages[i][0][0] * pages[i][0][1])
    overview = 1 - primary
    (width, height), mode, flags, old_type = pages[primary]
    (thumb_width, thumb_height), thumb_mode, thumb_flags, thumb_old_type = pages[overview]
    _validate_decoded_image_size(width, height, context=context)
    # A mask or another full-size plane is not a thumbnail. Require matching aspect ratio.
    if (flags != 0 or old_type not in (None, 1)
            or thumb_flags not in (0, 1) or thumb_old_type not in (None, 1, 2)
            or mode != thumb_mode or thumb_width >= width or thumb_height >= height
            or abs(thumb_width * height - thumb_height * width) > max(width, height)):
        raise ValueError(error)

    if not (thumb_flags & 1 or thumb_old_type == 2):
        # Some microscope exporters omit TIFF's reduced-image flag. Only accept
        # a small overview when its pixels also match the downsampled main image.
        if max(thumb_width, thumb_height) > 256 or thumb_width * 4 > width or thumb_height * 4 > height:
            raise ValueError(error)
        image.seek(overview)
        thumbnail = ImageOps.exif_transpose(image).convert("RGB")
        image.seek(primary)
        reduced = ImageOps.exif_transpose(image).convert("RGB").resize(
            thumbnail.size, Image.Resampling.LANCZOS
        )
        difference = np.abs(np.asarray(reduced, dtype=np.int16) - np.asarray(thumbnail, dtype=np.int16))
        # Allow minor resampling/encoding differences on the 8-bit display scale.
        if float(difference.mean()) > 3:
            raise ValueError(error)
    image.seek(primary)


def _decode_pil_rgb_image(image_bytes, context="image"):
    """Return the canonical 2D pixels used by display, preprocessing, and SAM."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.format not in ALLOWED_PIL_IMAGE_FORMATS:
                allowed = ", ".join(sorted(ALLOWED_PIL_IMAGE_FORMATS))
                raise ValueError(f"{context} format must be one of: {allowed}")
            _select_image_page(image, context)
            _validate_decoded_image_size(image.width, image.height, context=context)
            rgb_image = ImageOps.exif_transpose(image).convert("RGB")
            _validate_decoded_image_size(rgb_image.width, rgb_image.height, context=context)
            # Do not carry EXIF orientation into the PNG preview for the browser
            # to apply again. All output coordinates refer to these RGB pixels.
            rgb_image.info.clear()
            return rgb_image
    except (UnidentifiedImageError, OSError, SyntaxError, IndexError, Image.DecompressionBombError) as error:
        raise ValueError(f"Failed to decode {context}; the file is corrupt or its codec is unavailable.") from error


def _decode_cv2_bgr_image(image_bytes, context="image"):
    rgb_image = _decode_pil_rgb_image(image_bytes, context=context)
    return cv2.cvtColor(np.asarray(rgb_image), cv2.COLOR_RGB2BGR)
