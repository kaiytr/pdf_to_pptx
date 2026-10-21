"""Conversion options and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List


class ConversionMode(str, Enum):
    """How a PDF page is placed on a slide."""

    ORIGINAL = "original"
    EDITABLE = "editable"

    @property
    def label(self) -> str:
        return {
            ConversionMode.ORIGINAL: "원본 보존",
            ConversionMode.EDITABLE: "편집 가능",
        }[self]


class SlideRatio(str, Enum):
    """Target slide aspect ratio."""

    ORIGINAL = "original"
    WIDESCREEN = "16:9"
    STANDARD = "4:3"

    @property
    def label(self) -> str:
        return {
            SlideRatio.ORIGINAL: "원본 비율 유지",
            SlideRatio.WIDESCREEN: "16:9 (와이드)",
            SlideRatio.STANDARD: "4:3 (표준)",
        }[self]


class ImageQuality(str, Enum):
    """Render quality presets (DPI)."""

    STANDARD = "standard"
    HIGH = "high"

    @property
    def dpi(self) -> int:
        return {ImageQuality.STANDARD: 150, ImageQuality.HIGH: 300}[self]

    @property
    def label(self) -> str:
        return {ImageQuality.STANDARD: "표준 (150 DPI)", ImageQuality.HIGH: "고품질 (300 DPI)"}[self]


def parse_page_range(spec: str, page_count: int) -> List[int]:
    """Parse a user page range such as ``"1-3,5"`` into 0-based indexes.

    An empty/blank spec means every page. Duplicates are removed while the
    original order is kept. Raises ``ValueError`` with a Korean user-facing
    message for malformed or out-of-bounds input.
    """

    if page_count <= 0:
        raise ValueError("PDF에 변환할 페이지가 없습니다.")

    spec = (spec or "").strip()
    if not spec:
        return list(range(page_count))

    indexes: List[int] = []
    seen = set()
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            bits = part.split("-")
            if len(bits) != 2 or not bits[0].strip().isdigit() or not bits[1].strip().isdigit():
                raise ValueError(f"페이지 범위 형식이 올바르지 않습니다: '{part}' (예: 1-3,5)")
            start, end = int(bits[0]), int(bits[1])
        else:
            if not part.isdigit():
                raise ValueError(f"페이지 번호가 올바르지 않습니다: '{part}' (예: 1-3,5)")
            start = end = int(part)

        if start > end:
            raise ValueError(f"페이지 범위의 시작이 끝보다 큽니다: '{part}'")
        if start < 1 or end > page_count:
            raise ValueError(
                f"페이지 범위가 문서 범위를 벗어났습니다: '{part}' (전체 {page_count}페이지)"
            )
        for number in range(start, end + 1):
            index = number - 1
            if index not in seen:
                seen.add(index)
                indexes.append(index)

    if not indexes:
        raise ValueError("변환할 페이지를 한 개 이상 지정하세요.")
    return indexes


@dataclass
class ConversionOptions:
    """Everything needed to run one conversion."""

    output_path: Path
    mode: ConversionMode = ConversionMode.ORIGINAL
    ratio: SlideRatio = SlideRatio.ORIGINAL
    quality: ImageQuality = ImageQuality.STANDARD
    page_range: str = ""

    def __post_init__(self) -> None:
        self.output_path = Path(self.output_path)
        if self.output_path.suffix.lower() != ".pptx":
            self.output_path = self.output_path.with_suffix(".pptx")

    @property
    def dpi(self) -> int:
        return self.quality.dpi


@dataclass
class PageFailure:
    page_number: int
    message: str


@dataclass
class ConversionResult:
    output_path: Path
    total_pages: int
    converted_pages: int
    requested_pages: List[int]
    failed_pages: List[PageFailure] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
