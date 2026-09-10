import base64
import io
import json
import re
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, TiffImagePlugin, features
from werkzeug.datastructures import FileStorage

import image_io


def encoded_image(format, *, orientation=None, mode="RGB", size=(32, 32)):
    pixels = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    pixels[: size[1] // 2, : size[0] // 3] = (220, 30, 10)
    pixels[size[1] // 2 :, size[0] // 3 :] = (20, 80, 200)
    if format == "QOI":
        # Pillow 11.1 reads QOI but has no encoder. Use literal RGB operations.
        header = b"qoif" + size[0].to_bytes(4, "big") + size[1].to_bytes(4, "big") + bytes([3, 0])
        chunks = b"".join(bytes([254]) + pixel.tobytes() for pixel in pixels.reshape(-1, 3))
        return header + chunks + bytes([0] * 7 + [1])
    image = Image.fromarray(pixels).convert(mode)
    options = {}
    if orientation is not None:
        exif = Image.Exif()
        exif[274] = orientation
        options["exif"] = exif
    buffer = io.BytesIO()
    image.save(buffer, format=format, **options)
    return buffer.getvalue()


def expected_orientation(rgb, orientation):
    # Independent NumPy geometry, including mirrored EXIF orientations.
    return {
        1: lambda x: x,
        2: lambda x: x[:, ::-1],
        3: lambda x: x[::-1, ::-1],
        4: lambda x: x[::-1],
        5: lambda x: x.transpose(1, 0, 2),
        6: lambda x: np.rot90(x, -1),
        7: lambda x: x.transpose(1, 0, 2)[::-1, ::-1],
        8: lambda x: np.rot90(x, 1),
    }[orientation](rgb)


def tiff_with_overview(*, overview_first=False, tagged=False, unrelated=False, orientation=1):
    primary = Image.open(io.BytesIO(encoded_image("PNG", size=(512, 384))))
    overview = primary.resize((128, 96), Image.Resampling.LANCZOS)
    if unrelated:
        overview = Image.new("RGB", overview.size, "green")
    for image in (primary, overview):
        image.tag_v2 = TiffImagePlugin.ImageFileDirectory_v2()
        image.tag_v2[274] = orientation
    overview.tag_v2[254] = 1 if tagged else 0
    pages = [overview, primary] if overview_first else [primary, overview]
    buffer = io.BytesIO()
    pages[0].save(buffer, format="TIFF", save_all=True, append_images=pages[1:], compression="tiff_lzw")
    return buffer.getvalue(), np.asarray(primary)


@pytest.mark.parametrize("overview_first", [False, True])
@pytest.mark.parametrize("tagged", [False, True])
@pytest.mark.parametrize("orientation", [1, 6, 8])
def test_tiff_overview_is_not_mistaken_for_a_stack(overview_first, tagged, orientation):
    data, primary = tiff_with_overview(overview_first=overview_first, tagged=tagged, orientation=orientation)
    expected = expected_orientation(primary, orientation)
    np.testing.assert_array_equal(np.asarray(image_io._decode_pil_rgb_image(data)), expected)
    np.testing.assert_array_equal(
        cv2.cvtColor(image_io._decode_cv2_bgr_image(data), cv2.COLOR_BGR2RGB), expected
    )


def test_unmarked_small_unrelated_tiff_page_is_not_discarded():
    data, _ = tiff_with_overview(unrelated=True)
    with pytest.raises(ValueError, match="multiple frames or pages"):
        image_io._decode_pil_rgb_image(data)


def test_tiff_overview_cannot_bypass_primary_pixel_limit(monkeypatch):
    data, _ = tiff_with_overview(overview_first=True)
    monkeypatch.setattr(image_io, "MAX_DECODED_IMAGE_PIXELS", 20_000)
    with pytest.raises(ValueError, match="decoded pixels"):
        image_io._decode_pil_rgb_image(data)


@pytest.mark.parametrize("format", ["JPEG", "PNG", "TIFF", "WEBP"])
@pytest.mark.parametrize("orientation", range(1, 9))
def test_decoders_apply_orientation_exactly_once(format, orientation):
    if format == "WEBP" and not features.check("webp"):
        pytest.skip("Pillow was built without WebP")
    untagged = encoded_image(format, size=(48, 32))
    tagged = encoded_image(format, orientation=orientation, size=(48, 32))
    baseline = np.asarray(Image.open(io.BytesIO(untagged)).convert("RGB"))
    expected = expected_orientation(baseline, orientation)
    display = image_io._decode_pil_rgb_image(tagged)
    inference = cv2.cvtColor(image_io._decode_cv2_bgr_image(tagged), cv2.COLOR_BGR2RGB)
    np.testing.assert_array_equal(np.asarray(display), expected)
    np.testing.assert_array_equal(inference, expected)
    assert display.size == (expected.shape[1], expected.shape[0])
    assert not display.info
    assert display.getexif().get(274) is None
    preview = io.BytesIO()
    display.save(preview, format="PNG")
    reopened = Image.open(io.BytesIO(preview.getvalue()))
    assert reopened.getexif().get(274) is None
    np.testing.assert_array_equal(np.asarray(reopened), expected)


FORMATS = [
    ("JPEG", ".jpg", "RGB"), ("PNG", ".png", "RGBA"),
    ("BMP", ".bmp", "RGB"), ("DIB", ".dib", "RGB"),
    ("TIFF", ".tiff", "L"), ("WEBP", ".webp", "RGB"),
    ("GIF", ".gif", "P"), ("JPEG2000", ".jp2", "RGB"),
    ("PPM", ".pbm", "1"), ("PPM", ".pgm", "L"), ("PPM", ".ppm", "RGB"),
    ("PCX", ".pcx", "RGB"), ("TGA", ".tga", "RGB"),
    ("SGI", ".sgi", "RGB"), ("ICO", ".ico", "RGB"),
    ("QOI", ".qoi", "RGB"), ("XBM", ".xbm", "1"),
]


@pytest.mark.parametrize("format,extension,mode", FORMATS)
def test_supported_formats_decode_identically(format, extension, mode):
    if format == "WEBP" and not features.check("webp"):
        pytest.skip("Pillow was built without WebP")
    if format == "JPEG2000" and not features.check("jpg_2000"):
        pytest.skip("Pillow was built without JPEG 2000")
    data = encoded_image(format, mode=mode)
    # MIME labels are advisory; content must still be decodable.
    upload = FileStorage(stream=io.BytesIO(data), filename="image" + extension, content_type="application/octet-stream")
    image_io._validate_uploaded_image_file(upload)
    display = image_io._decode_pil_rgb_image(data)
    inference = image_io._decode_cv2_bgr_image(data)
    assert display.mode == "RGB"
    assert display.size == (32, 32)
    np.testing.assert_array_equal(np.asarray(display), cv2.cvtColor(inference, cv2.COLOR_BGR2RGB))


@pytest.mark.parametrize("format", ["GIF", "TIFF", "PNG"])
def test_multiframe_images_are_explicitly_rejected(format):
    frames = [Image.new("RGB", (4, 3), color) for color in ["red", "blue"]]
    buffer = io.BytesIO()
    frames[0].save(buffer, format=format, save_all=True, append_images=frames[1:])
    for decode in [image_io._decode_pil_rgb_image, image_io._decode_cv2_bgr_image]:
        with pytest.raises(ValueError, match="multiple frames or pages"):
            decode(buffer.getvalue())


def test_invalid_content_and_pixel_limit_are_rejected(monkeypatch):
    for decode in [image_io._decode_pil_rgb_image, image_io._decode_cv2_bgr_image]:
        with pytest.raises(ValueError, match="Failed to decode"):
            decode(b"not an image")
        with pytest.raises(ValueError, match="Failed to decode"):
            decode(encoded_image("QOI")[:14])
    data = encoded_image("BMP")
    monkeypatch.setattr(image_io, "MAX_DECODED_IMAGE_PIXELS", 100)
    for decode in [image_io._decode_pil_rgb_image, image_io._decode_cv2_bgr_image]:
        with pytest.raises(ValueError, match="decoded pixels"):
            decode(data)


def test_frontend_and_upload_controls_accept_the_backend_extensions():
    root = Path(__file__).resolve().parents[1]
    config = (root / "static/frontendConfig.js").read_text()
    extension_block = re.search(r"const ALLOWED_IMAGE_EXTENSIONS = \[(.*?)\];", config, re.S).group(1)
    assert set(re.findall(r"'([^']+)'", extension_block)) == image_io.ALLOWED_IMAGE_EXTENSIONS
    html = (root / "static/index.html").read_text()
    for input_id in ["loadImageInput", "openFolderInput"]:
        tag = re.search(r'<input[^>]+id="' + input_id + r'"[^>]+>', html).group(0)
        accepted = re.search(r'accept="([^"]+)"', tag).group(1)
        assert set(accepted.split(",")) == image_io.ALLOWED_IMAGE_EXTENSIONS


@pytest.mark.parametrize("format,extension", [("JPEG", ".jpg"), ("TIFF", ".tif"), ("BMP", ".bmp"), ("WEBP", ".webp"), ("TIFF_OVERVIEW", ".tif")])
def test_api_display_dimensions_preprocess_and_sam_share_pixels(app_module, monkeypatch, format, extension):
    if format == "WEBP" and not features.check("webp"):
        pytest.skip("Pillow was built without WebP")
    monkeypatch.setattr(app_module, "API_AUTH_TOKEN", "")
    monkeypatch.setattr(app_module.sam_model_handler, "is_ready", lambda: True)
    captured = []
    monkeypatch.setattr(app_module, "_run_sam_inference_with_limits", lambda rgb, settings: captured.append(rgb.copy()) or [])
    client = app_module.app.test_client()
    data = (tiff_with_overview(orientation=6)[0] if format == "TIFF_OVERVIEW"
            else encoded_image(format, orientation=None if format == "BMP" else 6, size=(48, 32)))

    def post(path, **fields):
        response = client.post(path, data={"image": (io.BytesIO(data), "cells" + extension), **fields}, content_type="multipart/form-data")
        assert response.status_code == 200, response.get_json()
        return response.get_json()

    loaded = post("/api/load_image")
    info = post("/api/image_info")
    assert info == {"width": loaded["width"], "height": loaded["height"]}
    preview = np.asarray(Image.open(io.BytesIO(base64.b64decode(loaded["image_url"].split(",", 1)[1]))))
    processed = post("/api/preprocess", method="gamma", params=json.dumps({"gamma": 1.0}))
    processed_pixels = np.asarray(Image.open(io.BytesIO(base64.b64decode(processed["image"].split(",", 1)[1]))))
    np.testing.assert_array_equal(processed_pixels, preview)
    settings = json.dumps({"preset": "fast_preview"})
    post("/api/run_sam", sam_settings=settings)
    post("/api/run_sam", sam_settings=settings, preprocess_method="gamma", preprocess_params=json.dumps({"gamma": 1.0}))
    assert len(captured) == 2
    for pixels in captured:
        np.testing.assert_array_equal(pixels, preview)
