"""Image extraction safeguards and coordinate handling."""

from __future__ import annotations

import io

import fitz
import pytest
from PIL import Image

from app.core import object_extractor


def test_page_rotation_is_applied_to_extracted_objects(rotated_pdf):
    doc = fitz.open(str(rotated_pdf))
    try:
        extracted = object_extractor.extract_page(doc, 0)
    finally:
        doc.close()

    assert extracted.width == pytest.approx(842)
    assert extracted.height == pytest.approx(595)

    block = next(
        block
        for block in extracted.text_blocks
        if "Rotated page text"
        in "".join(span.text for line in block.lines for span in line.spans)
    )
    # The text was at the top-left of the portrait page, so after a 90°
    # clockwise rotation it must be near the top-right of the landscape page.
    assert block.bbox[0] > 700
    assert block.bbox[1] < 150
    assert block.bbox[2] <= extracted.width + 0.5
    assert block.bbox[3] <= extracted.height + 0.5

    assert extracted.drawings
    for drawing in extracted.drawings:
        assert 0 <= drawing.bbox[0] <= extracted.width
        assert 0 <= drawing.bbox[1] <= extracted.height


def test_large_image_is_downscaled(monkeypatch):
    monkeypatch.setattr(object_extractor, "MAX_IMAGE_PIXELS", 1_000)
    monkeypatch.setattr(object_extractor, "MAX_IMAGE_SIDE", 40)
    source = io.BytesIO()
    Image.new("RGB", (100, 100), (30, 60, 120)).save(source, format="PNG")

    data, extension, resized = object_extractor._limit_image_size(
        source.getvalue(), "png"
    )

    assert resized is True
    with Image.open(io.BytesIO(data)) as image:
        assert max(image.size) <= 40
        assert extension in {"png", "jpeg"}


def test_small_image_is_kept_unchanged():
    source = io.BytesIO()
    Image.new("RGB", (32, 32), (30, 60, 120)).save(source, format="PNG")
    original = source.getvalue()

    data, extension, resized = object_extractor._limit_image_size(original, "png")

    assert resized is False
    assert data == original
    assert extension == "png"
