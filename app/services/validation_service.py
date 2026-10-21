"""Validation of inputs and generated PPTX files."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Optional

from pptx import Presentation

from app.core.pdf_loader import PDFInfo, get_pdf_info
from app.utils.error_handler import AppError, InvalidPDFError, OutputPathError
from app.utils.file_utils import can_write_directory


REQUIRED_PPTX_PARTS = (
    "[Content_Types].xml",
    "ppt/presentation.xml",
    "ppt/slides/slide1.xml",
)


def validate_source_pdf(path: Path, password: Optional[str] = None) -> PDFInfo:
    """Validate that *path* is a PDF we can convert."""

    path = Path(path)
    info = get_pdf_info(path, password)
    if info.page_count <= 0:
        raise InvalidPDFError("페이지가 없는 PDF는 변환할 수 없습니다.")
    return info


def validate_output_path(path: Path, allow_overwrite: bool = True) -> Path:
    """Validate the destination before a conversion starts."""

    path = Path(path)
    if path.suffix.lower() != ".pptx":
        raise OutputPathError("출력 파일은 .pptx 확장자여야 합니다.")
    if path.exists() and path.is_dir():
        raise OutputPathError("출력 경로가 폴더입니다. 파일 이름을 지정해 주세요.")
    parent = path.parent if path.parent != Path("") else Path(".")
    writable, reason = can_write_directory(parent)
    if not writable:
        raise OutputPathError(reason)
    if path.exists() and not allow_overwrite:
        raise OutputPathError("같은 이름의 파일이 이미 있습니다.")
    return path


def validate_pptx(path: Path, expected_slides: int) -> None:
    """Check that the generated file is a real, readable PPTX.

    Raises :class:`AppError` when the file is missing, is not a ZIP/OPC
    package, lacks required parts, or has the wrong slide count.
    """

    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        raise AppError("출력 PPTX 파일이 생성되지 않았습니다.")
    if not zipfile.is_zipfile(path):
        raise AppError("출력 파일이 올바른 PPTX 형식이 아닙니다.")
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            missing = [part for part in REQUIRED_PPTX_PARTS if part not in names]
            if missing:
                raise AppError(
                    "출력 PPTX 파일의 필수 구성 요소가 누락되었습니다.",
                    detail=", ".join(missing),
                )
            bad = archive.testzip()
            if bad:
                raise AppError("출력 PPTX 파일이 손상되었습니다.", detail=bad)
    except zipfile.BadZipFile as exc:
        raise AppError("출력 파일이 손상된 ZIP 패키지입니다.", detail=str(exc)) from exc

    try:
        presentation = Presentation(str(path))
        slide_count = len(presentation.slides)
    except Exception as exc:
        raise AppError(
            "출력 PPTX 파일을 다시 열 수 없습니다. PowerPoint에서 열리지 않을 수 있습니다.",
            detail=str(exc),
        ) from exc
    if slide_count != expected_slides:
        raise AppError(
            f"슬라이드 수가 올바르지 않습니다 (예상 {expected_slides}장, 실제 {slide_count}장)."
        )
    if slide_count == 0:
        raise AppError("슬라이드가 없는 PPTX 파일은 저장할 수 없습니다.")
