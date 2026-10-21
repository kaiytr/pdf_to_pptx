"""Opening and validating PDF documents with PyMuPDF."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from app.utils.error_handler import (
    InvalidPDFError,
    PDFOpenError,
    PDFPasswordIncorrect,
    PDFPasswordRequired,
)
from app.utils.file_utils import is_probably_pdf


@dataclass(frozen=True)
class PDFPageSize:
    """Page dimensions in PDF points (1/72 inch), after rotation."""

    width: float
    height: float


@dataclass(frozen=True)
class PDFInfo:
    path: Path
    page_count: int
    file_size: int
    page_sizes: tuple
    title: str = ""
    encrypted: bool = False

    @property
    def first_page_size(self) -> PDFPageSize:
        return self.page_sizes[0]

    @property
    def has_mixed_page_sizes(self) -> bool:
        if not self.page_sizes:
            return False
        first = self.page_sizes[0]
        return any(
            abs(page.width - first.width) > 1 or abs(page.height - first.height) > 1
            for page in self.page_sizes[1:]
        )


def _read_page_sizes(doc: "fitz.Document") -> tuple:
    sizes = []
    for page in doc:
        rect = page.rect
        # A page with no content may report an empty rect; fall back to media box.
        if rect.width <= 0 or rect.height <= 0:
            rect = page.mediabox
        sizes.append(PDFPageSize(abs(rect.width), abs(rect.height)))
    return tuple(sizes)


def open_pdf(path: Path, password: Optional[str] = None) -> "fitz.Document":
    """Open *path* and return an authenticated PyMuPDF document.

    The caller owns the returned document and must close it. A clear
    :class:`AppError` subclass is raised for every expected failure.
    """

    path = Path(path)
    if not path.exists():
        raise PDFOpenError("PDF 파일을 찾을 수 없습니다.")
    if not path.is_file():
        raise PDFOpenError("선택한 경로가 파일이 아닙니다.")
    if path.suffix.lower() != ".pdf":
        raise InvalidPDFError("PDF 파일만 선택할 수 있습니다.")
    if path.stat().st_size == 0:
        raise InvalidPDFError("파일이 비어 있습니다.")
    if not is_probably_pdf(path):
        raise InvalidPDFError("PDF 형식이 아니거나 파일이 손상되었습니다.")

    try:
        doc = fitz.open(str(path))
    except Exception as exc:  # PyMuPDF raises several message-only types
        raise PDFOpenError(
            "PDF 파일을 열 수 없습니다. 파일이 손상되었는지 확인해 주세요.",
            detail=str(exc),
        ) from exc

    try:
        if doc.needs_pass:
            if not password:
                raise PDFPasswordRequired()
            if not doc.authenticate(password):
                raise PDFPasswordIncorrect()
        if doc.page_count <= 0:
            raise InvalidPDFError("페이지가 없는 PDF는 변환할 수 없습니다.")
        if doc.is_closed:
            raise PDFOpenError("PDF 문서가 정상적으로 열리지 않았습니다.")
        return doc
    except Exception:
        doc.close()
        raise


def get_pdf_info(path: Path, password: Optional[str] = None) -> PDFInfo:
    """Open a PDF briefly and collect metadata for the UI."""

    path = Path(path)
    doc = open_pdf(path, password)
    try:
        metadata = doc.metadata or {}
        info = PDFInfo(
            path=path,
            page_count=doc.page_count,
            file_size=path.stat().st_size,
            page_sizes=_read_page_sizes(doc),
            title=(metadata.get("title") or "").strip(),
            encrypted=bool(doc.needs_pass or doc.is_encrypted),
        )
        if not info.page_sizes:
            raise InvalidPDFError("페이지 크기 정보를 읽을 수 없습니다.")
        return info
    finally:
        doc.close()
