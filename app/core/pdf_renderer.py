"""Rendering PDF pages to images for the original-preservation mode."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz

from app.utils.error_handler import AppError

# Avoid allocating hundreds of megabytes for one gigantic page.
MAX_PIXELS = 50_000_000
MIN_DPI = 72


@dataclass
class RenderResult:
    data: bytes
    width: int
    height: int
    dpi: int
    downscaled: bool = False


def render_page(page: "fitz.Page", dpi: int) -> RenderResult:
    """Render a page to PNG bytes, reducing DPI if the bitmap would be huge."""

    if dpi < MIN_DPI:
        dpi = MIN_DPI

    page_rect = page.rect
    width_pt = max(abs(page_rect.width), 1.0)
    height_pt = max(abs(page_rect.height), 1.0)
    effective_dpi = dpi
    scale = effective_dpi / 72.0
    estimated_pixels = (width_pt * scale) * (height_pt * scale)
    downscaled = False
    if estimated_pixels > MAX_PIXELS:
        scale = (MAX_PIXELS / (width_pt * height_pt)) ** 0.5
        effective_dpi = max(MIN_DPI, int(72 * scale))
        scale = effective_dpi / 72.0
        downscaled = True

    try:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    except Exception as exc:
        raise AppError("PDF 페이지를 이미지로 렌더링하지 못했습니다.", detail=str(exc)) from exc

    try:
        data = pixmap.tobytes("png")
    except Exception as exc:
        raise AppError("렌더링된 이미지를 저장하지 못했습니다.", detail=str(exc)) from exc
    finally:
        del pixmap

    return RenderResult(
        data=data,
        width=int(width_pt * scale),
        height=int(height_pt * scale),
        dpi=effective_dpi,
        downscaled=downscaled,
    )


def render_page_to_file(page: "fitz.Page", dpi: int, destination: Path) -> RenderResult:
    """Render a page and write the PNG to *destination*."""

    result = render_page(page, dpi)
    destination = Path(destination)
    try:
        destination.write_bytes(result.data)
    except OSError as exc:
        raise AppError("렌더링 이미지를 임시 파일로 저장하지 못했습니다.", detail=str(exc)) from exc
    return result


def render_thumbnail(page: "fitz.Page", max_width: int = 720) -> Optional[bytes]:
    """Render a small preview image (PNG bytes) for the UI."""

    try:
        rect = page.rect
        if rect.width <= 0:
            return None
        scale = min(2.0, max(0.1, max_width / rect.width))
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        try:
            return pixmap.tobytes("png")
        finally:
            del pixmap
    except Exception:
        return None
