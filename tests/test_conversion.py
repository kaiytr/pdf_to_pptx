"""End-to-end conversion tests for both modes, progress and failures."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from app.core.pptx_builder import PPTXBuilder, compute_slide_size
from app.core.object_extractor import ExtractedPage
from app.models.conversion_options import (
    ConversionMode,
    ConversionOptions,
    ImageQuality,
    SlideRatio,
)
from app.services.conversion_service import ConversionService
from app.services.validation_service import validate_pptx
from app.utils.error_handler import (
    AppError,
    ConversionCancelled,
    PDFPasswordRequired,
)

A4_RATIO = 595 / 842


def _convert(
    source: Path,
    output: Path,
    mode: ConversionMode = ConversionMode.ORIGINAL,
    ratio: SlideRatio = SlideRatio.ORIGINAL,
    quality: ImageQuality = ImageQuality.STANDARD,
    page_range: str = "",
    password: str | None = None,
    progress=None,
    cancel_event=None,
):
    service = ConversionService()
    return service.convert(
        source,
        ConversionOptions(
            output_path=output,
            mode=mode,
            ratio=ratio,
            quality=quality,
            page_range=page_range,
        ),
        password=password,
        progress=progress,
        cancel_event=cancel_event,
    )


def _slide_texts(presentation: Presentation) -> list[str]:
    texts = []
    for slide in presentation.slides:
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                texts.append(shape.text_frame.text)
    return texts


def _pictures(slide):
    return [shape for shape in slide.shapes if shape.shape_type == MSO_SHAPE_TYPE.PICTURE]


def _assert_shapes_inside_slide(presentation: Presentation, tolerance: int = 2) -> None:
    for slide in presentation.slides:
        for shape in slide.shapes:
            assert shape.left >= 0
            assert shape.top >= 0
            assert shape.left + shape.width <= presentation.slide_width + tolerance
            assert shape.top + shape.height <= presentation.slide_height + tolerance


def test_original_mode_creates_one_slide_per_page(sample_pdf: Path, tmp_path: Path):
    output = tmp_path / "original.pptx"
    result = _convert(sample_pdf, output)

    assert output.exists()
    assert result.converted_pages == 3
    assert result.failed_pages == []
    validate_pptx(output, expected_slides=3)

    presentation = Presentation(str(output))
    assert len(presentation.slides) == 3
    for slide in presentation.slides:
        assert len(_pictures(slide)) == 1
    assert presentation.slide_width / presentation.slide_height == pytest.approx(
        A4_RATIO, rel=1e-3
    )
    assert not list(tmp_path.glob(".slidebridge_*.pptx"))


def test_original_mode_widescreen(sample_pdf: Path, tmp_path: Path):
    output = tmp_path / "widescreen.pptx"
    _convert(sample_pdf, output, ratio=SlideRatio.WIDESCREEN, page_range="1")
    presentation = Presentation(str(output))
    assert presentation.slide_width / presentation.slide_height == pytest.approx(
        16 / 9, rel=1e-3
    )
    assert len(presentation.slides) == 1


def test_original_mode_standard_ratio(sample_pdf: Path, tmp_path: Path):
    output = tmp_path / "standard.pptx"
    _convert(sample_pdf, output, ratio=SlideRatio.STANDARD, page_range="1")
    presentation = Presentation(str(output))
    assert presentation.slide_width / presentation.slide_height == pytest.approx(
        4 / 3, rel=1e-3
    )


def test_editable_mode_builds_text_images_and_shapes(sample_pdf: Path, tmp_path: Path):
    output = tmp_path / "editable.pptx"
    result = _convert(sample_pdf, output, mode=ConversionMode.EDITABLE)

    assert result.converted_pages == 3
    validate_pptx(output, expected_slides=3)
    presentation = Presentation(str(output))
    texts = _slide_texts(presentation)
    joined = "\n".join(texts)
    assert "SlideBridge Test Page 1" in joined
    assert "SlideBridge Test Page 2" in joined
    assert "한글 텍스트 테스트" in joined
    assert "Editable text extraction test." in joined

    first_slide = presentation.slides[0]
    assert len(_pictures(first_slide)) >= 1
    assert len(first_slide.shapes) >= 4
    # Page 2 adds a line and a freeform polyline.
    assert len(presentation.slides[1].shapes) >= len(first_slide.shapes) + 1


def test_editable_mode_high_quality_produces_larger_images(sample_pdf: Path, tmp_path: Path):
    standard = tmp_path / "standard_quality.pptx"
    high = tmp_path / "high_quality.pptx"
    _convert(
        sample_pdf,
        standard,
        mode=ConversionMode.ORIGINAL,
        quality=ImageQuality.STANDARD,
        page_range="1",
    )
    _convert(
        sample_pdf,
        high,
        mode=ConversionMode.ORIGINAL,
        quality=ImageQuality.HIGH,
        page_range="1",
    )
    assert high.stat().st_size > standard.stat().st_size


def test_page_range_and_order(sample_pdf: Path, tmp_path: Path):
    output = tmp_path / "range.pptx"
    result = _convert(sample_pdf, output, mode=ConversionMode.EDITABLE, page_range="3,1")
    assert result.converted_pages == 2
    presentation = Presentation(str(output))
    assert len(presentation.slides) == 2
    first_texts = "\n".join(
        shape.text_frame.text
        for shape in presentation.slides[0].shapes
        if shape.has_text_frame
    )
    second_texts = "\n".join(
        shape.text_frame.text
        for shape in presentation.slides[1].shapes
        if shape.has_text_frame
    )
    assert "SlideBridge Test Page 3" in first_texts
    assert "SlideBridge Test Page 1" in second_texts


def test_progress_is_monotonic_and_completes(sample_pdf: Path, tmp_path: Path):
    events = []
    output = tmp_path / "progress.pptx"
    result = _convert(
        sample_pdf,
        output,
        mode=ConversionMode.EDITABLE,
        progress=events.append,
    )
    percents = [event.percent for event in events]
    assert percents == sorted(percents)
    assert percents[-1] == 100
    assert any(event.phase == "saving" for event in events)
    assert any(event.phase == "validating" for event in events)
    assert any(event.phase == "done" for event in events)
    assert events[-1].current == result.converted_pages
    assert result.elapsed_seconds >= 0


def test_cancellation_before_start_leaves_no_output(sample_pdf: Path, tmp_path: Path):
    output = tmp_path / "cancelled.pptx"
    cancel_event = threading.Event()
    cancel_event.set()
    with pytest.raises(ConversionCancelled):
        _convert(sample_pdf, output, cancel_event=cancel_event)
    assert not output.exists()
    assert not list(tmp_path.glob(".slidebridge_*.pptx"))


def test_invalid_page_range_fails_cleanly(sample_pdf: Path, tmp_path: Path):
    output = tmp_path / "invalid.pptx"
    with pytest.raises(AppError):
        _convert(sample_pdf, output, page_range="9")
    assert not output.exists()


def test_missing_output_folder_fails_cleanly(sample_pdf: Path, tmp_path: Path):
    output = tmp_path / "missing" / "out.pptx"
    with pytest.raises(AppError):
        _convert(sample_pdf, output)
    assert not output.exists()


def test_encrypted_pdf_conversion(encrypted_pdf: Path, tmp_path: Path):
    output = tmp_path / "encrypted.pptx"
    with pytest.raises(PDFPasswordRequired):
        _convert(encrypted_pdf, output)
    assert not output.exists()

    result = _convert(encrypted_pdf, output, password="user-secret")
    assert result.converted_pages == 1
    validate_pptx(output, expected_slides=1)


def test_mixed_page_sizes_use_first_page_ratio(mixed_size_pdf: Path, tmp_path: Path):
    output = tmp_path / "mixed.pptx"
    result = _convert(mixed_size_pdf, output)
    assert result.converted_pages == 2
    presentation = Presentation(str(output))
    assert presentation.slide_width / presentation.slide_height == pytest.approx(
        A4_RATIO, rel=1e-3
    )
    # The landscape page is letterboxed instead of overflowing the portrait slide.
    _assert_shapes_inside_slide(presentation)


def test_mixed_page_sizes_letterbox_editable_content(
    mixed_size_pdf: Path, tmp_path: Path
):
    output = tmp_path / "mixed_editable.pptx"
    result = _convert(mixed_size_pdf, output, mode=ConversionMode.EDITABLE)
    assert result.converted_pages == 2
    presentation = Presentation(str(output))
    _assert_shapes_inside_slide(presentation)
    joined = "\n".join(_slide_texts(presentation))
    assert "Portrait page" in joined
    assert "Landscape page" in joined


def test_rotated_page_places_editable_objects_in_rotated_space(
    rotated_pdf: Path, tmp_path: Path
):
    output = tmp_path / "rotated.pptx"
    result = _convert(rotated_pdf, output, mode=ConversionMode.EDITABLE)

    assert result.converted_pages == 1
    validate_pptx(output, expected_slides=1)
    presentation = Presentation(str(output))
    assert presentation.slide_width / presentation.slide_height == pytest.approx(
        842 / 595, rel=1e-3
    )

    slide = presentation.slides[0]
    text_shapes = [
        shape
        for shape in slide.shapes
        if shape.has_text_frame and "Rotated page text" in shape.text_frame.text
    ]
    assert text_shapes
    # A 90° clockwise page rotation moves the top-left text to the top-right.
    text_shape = text_shapes[0]
    assert text_shape.left > presentation.slide_width / 2
    assert text_shape.top < presentation.slide_height / 2

    _assert_shapes_inside_slide(presentation)


def test_scanned_pdf_editable_mode_keeps_image(scanned_pdf: Path, tmp_path: Path):
    output = tmp_path / "scan.pptx"
    result = _convert(scanned_pdf, output, mode=ConversionMode.EDITABLE)
    assert result.converted_pages == 1
    presentation = Presentation(str(output))
    assert len(_pictures(presentation.slides[0])) == 1


def test_editable_falls_back_to_image_when_nothing_extracted(
    sample_pdf: Path, tmp_path: Path, monkeypatch
):
    def empty_extract(doc, page_index, max_images=400):
        return ExtractedPage(width=595, height=842)

    monkeypatch.setattr("app.core.pptx_builder.extract_page", empty_extract)
    output = tmp_path / "fallback.pptx"
    result = _convert(sample_pdf, output, mode=ConversionMode.EDITABLE, page_range="1")
    assert result.converted_pages == 1
    assert any("이미지로 대체" in warning for warning in result.warnings)
    presentation = Presentation(str(output))
    assert len(_pictures(presentation.slides[0])) == 1


def test_partial_page_failure_removes_partial_slide(
    sample_pdf: Path, tmp_path: Path, monkeypatch
):
    original_method = PPTXBuilder.add_editable_page
    calls = {"count": 0}

    def flaky(self, doc, page_index):
        calls["count"] += 1
        original_method(self, doc, page_index)
        if calls["count"] == 2:
            raise RuntimeError("simulated page failure")

    monkeypatch.setattr(PPTXBuilder, "add_editable_page", flaky)
    output = tmp_path / "partial.pptx"
    result = _convert(sample_pdf, output, mode=ConversionMode.EDITABLE)

    assert result.converted_pages == 2
    assert len(result.failed_pages) == 1
    assert result.failed_pages[0].page_number == 2
    assert any("1페이지를 변환하지 못했습니다" in warning for warning in result.warnings)
    validate_pptx(output, expected_slides=2)
    presentation = Presentation(str(output))
    assert len(presentation.slides) == 2
    joined = "\n".join(_slide_texts(presentation))
    assert "SlideBridge Test Page 1" in joined
    assert "SlideBridge Test Page 3" in joined
    assert "SlideBridge Test Page 2" not in joined


def test_existing_output_is_overwritten(sample_pdf: Path, tmp_path: Path):
    output = tmp_path / "overwrite.pptx"
    output.write_bytes(b"old content")
    result = _convert(sample_pdf, output, page_range="1")
    assert result.converted_pages == 1
    validate_pptx(output, expected_slides=1)
    assert not list(tmp_path.glob(".slidebridge_*.pptx"))


def test_validation_failure_cleans_temporary_file(
    sample_pdf: Path, tmp_path: Path, monkeypatch
):
    def fail_validation(path, expected_slides):
        raise AppError("forced validation failure")

    monkeypatch.setattr(
        "app.services.conversion_service.validate_pptx", fail_validation
    )
    output = tmp_path / "not-saved.pptx"
    with pytest.raises(AppError):
        _convert(sample_pdf, output, page_range="1")
    assert not output.exists()
    assert not list(tmp_path.glob(".slidebridge_*.pptx"))


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [
        (SlideRatio.WIDESCREEN, 16 / 9),
        (SlideRatio.STANDARD, 4 / 3),
        (SlideRatio.ORIGINAL, A4_RATIO),
    ],
)
def test_compute_slide_size(ratio: SlideRatio, expected: float):
    width, height = compute_slide_size(595, 842, ratio)
    assert width / height == pytest.approx(expected, rel=1e-3)
    assert 1 <= width / 914400 <= 56
    assert 1 <= height / 914400 <= 56
