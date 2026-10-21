"""Lightweight PDF analysis used to warn users before conversion."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import fitz

from app.core.pdf_loader import PDFInfo, get_pdf_info, open_pdf
from app.utils.error_handler import InvalidPDFError

# Very large PDFs are allowed, but we tell the user before they wait a long time.
PAGE_COUNT_WARNING = 100
PAGE_COUNT_LIMIT = 5000
LARGE_FILE_WARNING = 200 * 1024 * 1024  # 200 MB
ANALYSIS_SAMPLE_PAGES = 40


@dataclass
class PageAnalysis:
    page_number: int
    width: float
    height: float
    text_characters: int = 0
    image_count: int = 0
    drawing_count: int = 0


@dataclass
class PDFAnalysis:
    info: PDFInfo
    sampled_pages: List[PageAnalysis] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def sampled_page_count(self) -> int:
        return len(self.sampled_pages)

    @property
    def is_probably_scanned(self) -> bool:
        return bool(self.sampled_pages) and all(
            page.text_characters == 0 and page.image_count > 0 for page in self.sampled_pages
        )

    @property
    def has_text(self) -> bool:
        return any(page.text_characters > 0 for page in self.sampled_pages)

    @property
    def has_images(self) -> bool:
        return any(page.image_count > 0 for page in self.sampled_pages)


def analyze_pdf(path: Path, password: Optional[str] = None) -> PDFAnalysis:
    """Inspect the document and return user-facing warnings.

    Only a sample of pages is inspected so opening a huge PDF stays fast.
    """

    info = get_pdf_info(path, password)
    if info.page_count > PAGE_COUNT_LIMIT:
        raise InvalidPDFError(
            f"페이지가 너무 많습니다 ({info.page_count}페이지). "
            f"최대 {PAGE_COUNT_LIMIT}페이지까지 지원합니다."
        )

    analysis = PDFAnalysis(info=info)

    if info.page_count > PAGE_COUNT_WARNING:
        analysis.warnings.append(
            f"페이지가 많은 문서입니다 ({info.page_count}페이지). 변환에 시간이 걸릴 수 있습니다."
        )
    if info.file_size > LARGE_FILE_WARNING:
        analysis.warnings.append("파일 용량이 큽니다 (200MB 초과). 변환에 시간이 걸릴 수 있습니다.")
    if info.has_mixed_page_sizes:
        analysis.warnings.append(
            "페이지마다 크기가 다릅니다. 첫 페이지 비율을 기준으로 여백이 생길 수 있습니다."
        )
    if info.encrypted:
        analysis.warnings.append("암호로 보호된 PDF입니다. 변환은 가능하지만 일부 기능이 제한될 수 있습니다.")

    doc = open_pdf(path, password)
    try:
        sample_count = min(info.page_count, ANALYSIS_SAMPLE_PAGES)
        for page_index in range(sample_count):
            page = doc.load_page(page_index)
            try:
                text = page.get_text("text") or ""
                images = page.get_images(full=True) or []
                try:
                    drawings = page.get_drawings() or []
                except Exception:
                    drawings = []
                analysis.sampled_pages.append(
                    PageAnalysis(
                        page_number=page_index + 1,
                        width=abs(page.rect.width),
                        height=abs(page.rect.height),
                        text_characters=len(text.strip()),
                        image_count=len(images),
                        drawing_count=len(drawings),
                    )
                )
            except Exception:
                # Analysis is advisory; a page that cannot be sampled may
                # still be convertible, so do not abort the whole analysis.
                continue
    finally:
        doc.close()

    if not analysis.sampled_pages:
        raise InvalidPDFError("PDF 페이지 내용을 읽을 수 없습니다.")

    if analysis.is_probably_scanned:
        analysis.warnings.append(
            "텍스트가 거의 없는 스캔 문서로 보입니다. 편집 가능 모드에서는 이미지로 대체될 수 있습니다."
        )
    return analysis


def count_extractable_objects(doc: "fitz.Document", page_index: int) -> dict:
    """Return a rough object count for a page (used by the editable builder)."""

    page = doc.load_page(page_index)
    try:
        text_dict = page.get_text("dict")
        images = page.get_images(full=True)
        drawings = page.get_drawings()
    except Exception:
        return {"text_blocks": 0, "images": 0, "drawings": 0}
    return {
        "text_blocks": sum(1 for b in text_dict.get("blocks", []) if b.get("type") == 0),
        "images": len(images),
        "drawings": len(drawings),
    }
