"""High-level conversion pipeline with progress and cancellation."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from app.core.pdf_loader import open_pdf
from app.core.pptx_builder import BuildSummary, PPTXBuilder
from app.models.conversion_options import (
    ConversionMode,
    ConversionOptions,
    ConversionResult,
    PageFailure,
    parse_page_range,
)
from app.services.validation_service import (
    validate_output_path,
    validate_pptx,
    validate_source_pdf,
)
from app.utils.error_handler import AppError, ConversionCancelled, format_exception


@dataclass
class ProgressInfo:
    percent: int
    phase: str
    message: str
    current: int = 0
    total: int = 0
    page_number: Optional[int] = None


ProgressCallback = Callable[[ProgressInfo], None]


@dataclass
class _PagePlan:
    total: int
    indexes: List[int]
    page_width: float
    page_height: float


class ConversionService:
    """Convert one PDF into a PPTX file.

    The service is UI-agnostic. It reports progress through a callback and
    checks a ``threading.Event``-like object for cancellation between pages.
    """

    def convert(
        self,
        source_path: Path,
        options: ConversionOptions,
        password: Optional[str] = None,
        progress: Optional[ProgressCallback] = None,
        cancel_event=None,
    ) -> ConversionResult:
        started = time.monotonic()
        source_path = Path(source_path)
        output_path = Path(options.output_path)

        def report(
            percent: int,
            phase: str,
            message: str,
            current: int = 0,
            total: int = 0,
            page_number: Optional[int] = None,
        ) -> None:
            if progress:
                progress(
                    ProgressInfo(
                        percent=max(0, min(100, percent)),
                        phase=phase,
                        message=message,
                        current=current,
                        total=total,
                        page_number=page_number,
                    )
                )

        def check_cancelled() -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise ConversionCancelled()

        report(2, "preparing", "PDF 파일을 확인하는 중…")
        validate_source_pdf(source_path, password)
        validate_output_path(output_path, allow_overwrite=True)
        check_cancelled()

        doc = open_pdf(source_path, password)
        temp_path = output_path.parent / f".slidebridge_{uuid.uuid4().hex}.pptx"
        try:
            total_pages = doc.page_count
            try:
                indexes = parse_page_range(options.page_range, total_pages)
            except ValueError as exc:
                raise AppError(str(exc)) from exc

            first_page = doc.load_page(indexes[0])
            plan = _PagePlan(
                total=total_pages,
                indexes=indexes,
                page_width=abs(first_page.rect.width),
                page_height=abs(first_page.rect.height),
            )
            report(
                5,
                "preparing",
                f"{len(indexes)}페이지 변환을 준비했습니다.",
                total=len(indexes),
            )
            check_cancelled()

            builder = PPTXBuilder(options, plan.page_width, plan.page_height)
            failures: List[PageFailure] = []
            converted = 0

            for position, page_index in enumerate(plan.indexes, start=1):
                check_cancelled()
                page_number = page_index + 1
                percent = 5 + int((position - 1) / max(1, len(plan.indexes)) * 85)
                report(
                    percent,
                    "rendering" if options.mode is ConversionMode.ORIGINAL else "extracting",
                    f"페이지 {page_number} 변환 중… ({position}/{len(plan.indexes)})",
                    current=position - 1,
                    total=len(plan.indexes),
                    page_number=page_number,
                )
                try:
                    slide_count_before = len(builder.presentation.slides)
                    if options.mode is ConversionMode.ORIGINAL:
                        page = doc.load_page(page_index)
                        builder.add_original_page(page)
                    else:
                        builder.add_editable_page(doc, page_index)
                    converted += 1
                except ConversionCancelled:
                    raise
                except Exception as exc:
                    failures.append(PageFailure(page_number=page_number, message=format_exception(exc)))
                    # Drop a partially built slide so the slide count matches
                    # the reported successful pages.
                    try:
                        while len(builder.presentation.slides) > slide_count_before:
                            builder.discard_last_slide()
                    except Exception:
                        pass
                report(
                    min(90, 5 + int(position / max(1, len(plan.indexes)) * 85)),
                    "rendering" if options.mode is ConversionMode.ORIGINAL else "extracting",
                    f"페이지 {page_number} 완료 ({position}/{len(plan.indexes)})",
                    current=position,
                    total=len(plan.indexes),
                    page_number=page_number,
                )

            if converted == 0:
                detail = "\n".join(f"p.{f.page_number}: {f.message}" for f in failures[:5])
                raise AppError(
                    "모든 페이지 변환에 실패했습니다. PDF 내용을 확인해 주세요.",
                    detail=detail or None,
                )

            check_cancelled()
            report(92, "saving", "PPTX 파일을 생성하는 중…")
            summary: BuildSummary = builder.save(temp_path)
            check_cancelled()

            report(96, "validating", "출력 파일을 검증하는 중…")
            validate_pptx(temp_path, expected_slides=converted)

            check_cancelled()
            try:
                os.replace(temp_path, output_path)
            except OSError as exc:
                raise AppError(
                    "최종 파일을 저장하지 못했습니다. 같은 이름의 파일이 열려 있지 않은지 확인해 주세요.",
                    detail=str(exc),
                ) from exc

            warnings = list(summary.warnings)
            if failures:
                warnings.insert(
                    0,
                    f"{len(failures)}페이지를 변환하지 못했습니다: "
                    + ", ".join(str(f.page_number) for f in failures[:10]),
                )
            if options.mode is ConversionMode.EDITABLE:
                warnings.append(
                    "편집 가능 모드는 텍스트·이미지·단순 도형을 재구성합니다. "
                    "복잡한 그래픽과 글꼴 모양은 원본과 다를 수 있습니다."
                )

            report(100, "done", "변환 완료", current=converted, total=len(plan.indexes))
            return ConversionResult(
                output_path=output_path,
                total_pages=total_pages,
                converted_pages=converted,
                requested_pages=plan.indexes,
                failed_pages=failures,
                warnings=warnings,
                elapsed_seconds=time.monotonic() - started,
            )
        finally:
            doc.close()
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
