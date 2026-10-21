"""PDF opening, metadata and analysis tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.pdf_analyzer import analyze_pdf
from app.core.pdf_loader import get_pdf_info, open_pdf
from app.utils.error_handler import (
    InvalidPDFError,
    PDFOpenError,
    PDFPasswordIncorrect,
    PDFPasswordRequired,
)


def test_loads_valid_pdf(sample_pdf: Path):
    info = get_pdf_info(sample_pdf)
    assert info.page_count == 3
    assert info.file_size > 0
    assert info.first_page_size.width == pytest.approx(595, abs=1)
    assert info.first_page_size.height == pytest.approx(842, abs=1)
    assert info.title == "DeckForge Sample"
    assert info.has_mixed_page_sizes is False


def test_open_pdf_returns_readable_document(sample_pdf: Path):
    doc = open_pdf(sample_pdf)
    try:
        assert doc.page_count == 3
        assert "DeckForge Test Page 1" in doc.load_page(0).get_text()
    finally:
        doc.close()


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(PDFOpenError):
        get_pdf_info(tmp_path / "does-not-exist.pdf")


def test_non_pdf_extension_raises(tmp_path: Path):
    path = tmp_path / "document.txt"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(InvalidPDFError):
        get_pdf_info(path)


def test_empty_file_raises(tmp_path: Path):
    path = tmp_path / "zero.pdf"
    path.write_bytes(b"")
    with pytest.raises(InvalidPDFError):
        get_pdf_info(path)


def test_corrupt_pdf_raises(corrupt_pdf: Path):
    with pytest.raises((InvalidPDFError, PDFOpenError)):
        get_pdf_info(corrupt_pdf)


def test_pdf_without_pages_raises(empty_pdf: Path):
    with pytest.raises(InvalidPDFError):
        get_pdf_info(empty_pdf)


def test_encrypted_pdf_requires_password(encrypted_pdf: Path):
    with pytest.raises(PDFPasswordRequired):
        get_pdf_info(encrypted_pdf)


def test_encrypted_pdf_rejects_wrong_password(encrypted_pdf: Path):
    with pytest.raises(PDFPasswordIncorrect):
        get_pdf_info(encrypted_pdf, "wrong")


def test_encrypted_pdf_opens_with_password(encrypted_pdf: Path):
    info = get_pdf_info(encrypted_pdf, "user-secret")
    assert info.page_count == 1
    assert info.encrypted is True


def test_analysis_reports_warnings_for_mixed_sizes(mixed_size_pdf: Path):
    analysis = analyze_pdf(mixed_size_pdf)
    assert analysis.info.has_mixed_page_sizes is True
    assert any("크기가 다릅니다" in warning for warning in analysis.warnings)
    assert analysis.has_text is True


def test_analysis_detects_scanned_document(scanned_pdf: Path):
    analysis = analyze_pdf(scanned_pdf)
    assert analysis.is_probably_scanned is True
    assert analysis.has_text is False
    assert any("스캔" in warning for warning in analysis.warnings)


def test_analysis_extracts_korean_text(sample_pdf: Path):
    analysis = analyze_pdf(sample_pdf)
    assert analysis.has_text is True
    doc = open_pdf(sample_pdf)
    try:
        assert "한글 텍스트 테스트" in doc.load_page(0).get_text()
    finally:
        doc.close()
