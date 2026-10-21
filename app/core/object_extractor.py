"""Extract text, images and simple vector graphics from PDF pages."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import fitz
from PIL import Image

BBox = Tuple[float, float, float, float]
SUBSET_FONT_RE = re.compile(r"^[A-Z]{6}\+")
MAX_DRAWINGS_PER_PAGE = 800
MAX_FREEFORM_POINTS = 2000
MAX_TOTAL_DRAWING_POINTS = 60_000
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_SIDE = 8000

# Fonts PowerPoint understands well; map common PDF base fonts.
FONT_ALIASES = {
    "helvetica": "Arial",
    "helvetica-bold": "Arial",
    "helvetica-oblique": "Arial",
    "times": "Times New Roman",
    "times-roman": "Times New Roman",
    "times-bold": "Times New Roman",
    "courier": "Courier New",
    "courier-bold": "Courier New",
    "symbol": "Symbol",
    "zapfdingbats": "Wingdings",
}


@dataclass
class ExtractedSpan:
    text: str
    bbox: BBox
    font_name: str
    font_size: float
    color: int
    bold: bool = False
    italic: bool = False


@dataclass
class ExtractedLine:
    bbox: BBox
    spans: List[ExtractedSpan] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans)


@dataclass
class ExtractedTextBlock:
    bbox: BBox
    lines: List[ExtractedLine] = field(default_factory=list)


@dataclass
class ExtractedImage:
    bbox: BBox
    width: int
    height: int
    data: bytes
    extension: str


@dataclass
class ExtractedDrawing:
    bbox: BBox
    points: List[Tuple[float, float]]
    is_rect: bool = False
    fill: Optional[Tuple[int, int, int]] = None
    stroke: Optional[Tuple[int, int, int]] = None
    stroke_width: float = 0.0
    closed: bool = False


@dataclass
class ExtractedPage:
    width: float
    height: float
    text_blocks: List[ExtractedTextBlock] = field(default_factory=list)
    images: List[ExtractedImage] = field(default_factory=list)
    drawings: List[ExtractedDrawing] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _clean_font_name(name: str) -> str:
    cleaned = SUBSET_FONT_RE.sub("", name or "").strip()
    cleaned = cleaned.split(",")[0].strip()
    if not cleaned:
        return "Arial"
    alias = FONT_ALIASES.get(cleaned.lower())
    return alias or cleaned


def _color_to_rgb(color: int) -> Tuple[int, int, int]:
    return ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)


def _pdf_color_to_rgb(color: Sequence[float]) -> Optional[Tuple[int, int, int]]:
    try:
        values = [max(0.0, min(1.0, float(v))) for v in color]
    except (TypeError, ValueError):
        return None
    if len(values) == 1:
        gray = int(round(values[0] * 255))
        return (gray, gray, gray)
    if len(values) == 3:
        return tuple(int(round(v * 255)) for v in values)  # type: ignore[return-value]
    if len(values) == 4:
        # CMYK -> RGB (simple, no color profile)
        c, m, y, k = values
        return (
            int(round(255 * (1 - c) * (1 - k))),
            int(round(255 * (1 - m) * (1 - k))),
            int(round(255 * (1 - y) * (1 - k))),
        )
    return None


def _clamp_bbox(bbox: Sequence[float], width: float, height: float) -> Optional[BBox]:
    if len(bbox) < 4:
        return None
    x0, y0, x1, y1 = (float(v) for v in bbox[:4])
    x0, x1 = sorted((max(0.0, min(width, x0)), max(0.0, min(width, x1))))
    y0, y1 = sorted((max(0.0, min(height, y0)), max(0.0, min(height, y1))))
    if x1 - x0 < 0.2 or y1 - y0 < 0.2:
        return None
    return (x0, y0, x1, y1)


def _rotate_bbox(bbox: BBox, matrix: "fitz.Matrix") -> BBox:
    """Rotate an axis-aligned bbox; page rotation is always a multiple of 90°."""

    first = fitz.Point(bbox[0], bbox[1]) * matrix
    second = fitz.Point(bbox[2], bbox[3]) * matrix
    rect = fitz.Rect(first, second)
    rect.normalize()
    return (rect.x0, rect.y0, rect.x1, rect.y1)


def _rotate_point(point: Tuple[float, float], matrix: "fitz.Matrix") -> Tuple[float, float]:
    rotated = fitz.Point(point[0], point[1]) * matrix
    return (rotated.x, rotated.y)


def _extract_text(
    page: "fitz.Page",
    page_width: float,
    page_height: float,
) -> List[ExtractedTextBlock]:
    blocks: List[ExtractedTextBlock] = []
    try:
        text_dict = page.get_text("dict", sort=False)
    except Exception:
        return blocks

    for raw_block in text_dict.get("blocks", []):
        if raw_block.get("type") != 0:
            continue
        block_bbox = _clamp_bbox(raw_block.get("bbox", ()), page_width, page_height)
        if not block_bbox:
            continue
        lines: List[ExtractedLine] = []
        for raw_line in raw_block.get("lines", []):
            span_list: List[ExtractedSpan] = []
            for raw_span in raw_line.get("spans", []):
                text = raw_span.get("text", "")
                if not text:
                    continue
                span_bbox = _clamp_bbox(raw_span.get("bbox", ()), page_width, page_height)
                if not span_bbox:
                    continue
                flags = int(raw_span.get("flags", 0))
                font_name = _clean_font_name(raw_span.get("font", ""))
                span_list.append(
                    ExtractedSpan(
                        text=text,
                        bbox=span_bbox,
                        font_name=font_name,
                        font_size=float(raw_span.get("size", 11.0) or 11.0),
                        color=int(raw_span.get("color", 0) or 0),
                        bold=bool(flags & 16) or "bold" in font_name.lower(),
                        italic=bool(flags & 2) or "italic" in font_name.lower()
                        or "oblique" in font_name.lower(),
                    )
                )
            if span_list:
                line_bbox = _clamp_bbox(raw_line.get("bbox", ()), page_width, page_height) or (
                    min(s.bbox[0] for s in span_list),
                    min(s.bbox[1] for s in span_list),
                    max(s.bbox[2] for s in span_list),
                    max(s.bbox[3] for s in span_list),
                )
                lines.append(ExtractedLine(bbox=line_bbox, spans=span_list))
        if lines:
            blocks.append(ExtractedTextBlock(bbox=block_bbox, lines=lines))
    return blocks


def _limit_image_size(data: bytes, extension: str) -> Tuple[bytes, str, bool]:
    """Downscale pathological images so one page cannot exhaust memory."""

    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            if width * height <= MAX_IMAGE_PIXELS and max(width, height) <= MAX_IMAGE_SIDE:
                return data, extension, False
            scale = min(
                MAX_IMAGE_SIDE / max(1, width),
                MAX_IMAGE_SIDE / max(1, height),
                (MAX_IMAGE_PIXELS / max(1, width * height)) ** 0.5,
            )
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            resized = image.resize(new_size, Image.LANCZOS)
            out = io.BytesIO()
            if resized.mode in {"RGBA", "LA", "P"}:
                resized.convert("RGBA").save(out, format="PNG", optimize=True)
                return out.getvalue(), "png", True
            resized.convert("RGB").save(out, format="JPEG", quality=90, optimize=True)
            return out.getvalue(), "jpeg", True
    except Exception:
        return data, extension, False


def _image_bytes(
    doc: "fitz.Document", image_info: dict
) -> Optional[Tuple[bytes, str, bool]]:
    """Extract image bytes, converting uncommon formats and applying SMask.

    Returns ``(bytes, extension, resized)`` or ``None``.
    """

    xref = int(image_info.get("xref", 0))
    if xref <= 0:
        return None
    try:
        extracted = doc.extract_image(xref)
    except Exception:
        extracted = None

    if not extracted or not extracted.get("image"):
        try:
            pixmap = fitz.Pixmap(doc, xref)
            if pixmap.colorspace is not None and pixmap.colorspace.n > 3:
                pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
            data, extension, resized = _limit_image_size(pixmap.tobytes("png"), "png")
            return data, extension, resized
        except Exception:
            return None

    data = extracted["image"]
    extension = (extracted.get("ext") or "png").lower()
    smask = int(image_info.get("smask", 0) or 0)

    if smask:
        try:
            mask_info = doc.extract_image(smask)
            if mask_info and mask_info.get("image"):
                base = Image.open(io.BytesIO(data)).convert("RGB")
                mask = Image.open(io.BytesIO(mask_info["image"])).convert("L")
                if mask.size != base.size:
                    mask = mask.resize(base.size, Image.LANCZOS)
                rgba = base.convert("RGBA")
                rgba.putalpha(mask)
                out = io.BytesIO()
                rgba.save(out, format="PNG")
                return _limit_image_size(out.getvalue(), "png")
        except Exception:
            pass

    if extension in {"png", "jpg", "jpeg", "gif", "bmp", "tif", "tiff"}:
        normalized = "jpeg" if extension in {"jpg", "jpeg"} else extension
        return _limit_image_size(data, normalized)

    # JPEG2000, JBIG2 etc. are not supported by PowerPoint; convert with Pillow
    # or PyMuPDF.
    try:
        image = Image.open(io.BytesIO(data))
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA")
        out = io.BytesIO()
        image.save(out, format="PNG")
        return _limit_image_size(out.getvalue(), "png")
    except Exception:
        pass

    try:
        pixmap = fitz.Pixmap(doc, xref)
        if pixmap.colorspace is not None and pixmap.colorspace.n > 3:
            pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
        return _limit_image_size(pixmap.tobytes("png"), "png")
    except Exception:
        return None


def _extract_images(
    doc: "fitz.Document",
    page: "fitz.Page",
    page_width: float,
    page_height: float,
) -> Tuple[List[ExtractedImage], List[str]]:
    images: List[ExtractedImage] = []
    warnings: List[str] = []
    try:
        image_infos = page.get_images(full=True)
    except Exception:
        return images, warnings

    seen = set()
    for info in image_infos:
        xref = int(info[0])
        width = int(info[2] or 0)
        height = int(info[3] or 0)
        if width < 2 or height < 2:
            continue  # spacer / mask-only images
        key = (xref, width, height)
        try:
            rects = page.get_image_rects(xref, transform=False)
        except Exception:
            rects = []
        for rect in rects:
            bbox = _clamp_bbox((rect.x0, rect.y0, rect.x1, rect.y1), page_width, page_height)
            if not bbox:
                continue
            placement_key = key + tuple(round(v, 2) for v in bbox)
            if placement_key in seen:
                continue
            seen.add(placement_key)
            payload = _image_bytes(doc, {"xref": xref, "smask": info[1] if len(info) > 1 else 0})
            if not payload:
                warnings.append(f"이미지(xref {xref})를 추출하지 못해 건너뛰었습니다.")
                continue
            data, extension, resized = payload
            if resized:
                warnings.append(
                    f"매우 큰 이미지(xref {xref})를 메모리 보호를 위해 축소했습니다."
                )
            images.append(
                ExtractedImage(
                    bbox=bbox,
                    width=width,
                    height=height,
                    data=data,
                    extension=extension,
                )
            )
    return images, warnings


def _sample_cubic(p0, p1, p2, p3, steps: int = 8) -> List[Tuple[float, float]]:
    points = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


def _extract_drawings(
    page: "fitz.Page",
    page_width: float,
    page_height: float,
) -> Tuple[List[ExtractedDrawing], List[str]]:
    drawings: List[ExtractedDrawing] = []
    warnings: List[str] = []
    try:
        raw_drawings = page.get_drawings()
    except Exception:
        return drawings, ["벡터 그래픽 정보를 읽지 못했습니다."]

    total_count = len(raw_drawings or [])
    if total_count > MAX_DRAWINGS_PER_PAGE:
        warnings.append(
            f"벡터 요소가 너무 많아({total_count}개) 일부만 변환했습니다. "
            "복잡한 도형은 누락될 수 있습니다."
        )

    total_points = 0
    for raw in (raw_drawings or [])[:MAX_DRAWINGS_PER_PAGE]:
        items = raw.get("items") or []
        if not items:
            continue
        bbox = _clamp_bbox(raw.get("rect", ()), page_width, page_height)
        if not bbox:
            continue

        fill = _pdf_color_to_rgb(raw.get("fill") or ()) if raw.get("fill") else None
        stroke = _pdf_color_to_rgb(raw.get("color") or ()) if raw.get("color") else None
        if fill is None and stroke is None:
            continue
        stroke_width = float(raw.get("width") or 0.0)
        if stroke and stroke_width <= 0:
            stroke_width = 0.75

        points: List[Tuple[float, float]] = []
        is_rect = len(items) == 1 and items[0][0] == "re"
        unsupported = False
        for item in items:
            kind = item[0]
            if kind == "re":
                rect = item[1]
                points.extend(
                    [
                        (float(rect.x0), float(rect.y0)),
                        (float(rect.x1), float(rect.y0)),
                        (float(rect.x1), float(rect.y1)),
                        (float(rect.x0), float(rect.y1)),
                    ]
                )
            elif kind == "l":
                points.append((float(item[1].x), float(item[1].y)))
                points.append((float(item[2].x), float(item[2].y)))
            elif kind == "qu":
                quad = item[1]
                points.extend([(float(p.x), float(p.y)) for p in (quad.ul, quad.ur, quad.lr, quad.ll)])
            elif kind == "c":
                points.extend(
                    _sample_cubic(
                        (float(item[1].x), float(item[1].y)),
                        (float(item[2].x), float(item[2].y)),
                        (float(item[3].x), float(item[3].y)),
                        (float(item[4].x), float(item[4].y)),
                    )
                )
            elif kind == "v":
                p0 = (float(item[1].x), float(item[1].y))
                points.append(p0)
                points.extend(
                    _sample_cubic(
                        p0,
                        (float(item[2].x), float(item[2].y)),
                        (float(item[3].x), float(item[3].y)),
                        (float(item[3].x), float(item[3].y)),
                        steps=4,
                    )
                )
            else:
                unsupported = True
                continue

        if unsupported or len(points) < 2:
            continue
        # Limit pathological paths so a single shape cannot explode the file.
        if len(points) > MAX_FREEFORM_POINTS:
            step = max(1, len(points) // MAX_FREEFORM_POINTS)
            points = points[::step]

        if is_rect:
            # Use the actual rectangle bounds; item orientation is irrelevant.
            points = [
                (bbox[0], bbox[1]),
                (bbox[2], bbox[1]),
                (bbox[2], bbox[3]),
                (bbox[0], bbox[3]),
            ]
            # Tiny decorations (rules, borders) are cheaper as thin lines.
            fill = fill if (bbox[2] - bbox[0]) > 0.5 and (bbox[3] - bbox[1]) > 0.5 else None
            if fill is None and not stroke:
                continue

        if total_points + len(points) > MAX_TOTAL_DRAWING_POINTS:
            warnings.append(
                "벡터 요소가 지나치게 복잡하여 일부 도형을 변환하지 못했습니다."
            )
            break
        total_points += len(points)

        drawings.append(
            ExtractedDrawing(
                bbox=bbox,
                points=points,
                is_rect=is_rect,
                fill=fill,
                stroke=stroke,
                stroke_width=max(0.0, min(stroke_width, 50.0)),
                closed=bool(raw.get("closePath")) or is_rect,
            )
        )
    return drawings, warnings


def extract_page(
    doc: "fitz.Document", page_index: int, max_images: int = 400
) -> ExtractedPage:
    """Extract all objects needed to rebuild one page as editable shapes.

    PyMuPDF reports text, image and drawing coordinates in the *unrotated*
    page system.  This function applies the page's /Rotate value so every
    bbox/point is in the same coordinate space as ``page.rect`` (which the
    slide builder uses).
    """

    page = doc.load_page(page_index)
    rect = page.rect
    page_width = max(abs(rect.width), 1.0)
    page_height = max(abs(rect.height), 1.0)
    result = ExtractedPage(width=page_width, height=page_height)

    rotation = int(page.rotation or 0) % 360
    # PyMuPDF reports objects in the unrotated page space.  For 90°/270° the
    # displayed (page.rect) width and height are swapped.
    if rotation in (90, 270):
        source_width, source_height = page_height, page_width
    else:
        source_width, source_height = page_width, page_height

    result.text_blocks = _extract_text(page, source_width, source_height)
    images, image_warnings = _extract_images(
        doc, page, source_width, source_height
    )
    result.images = images[:max_images]
    if len(images) > max_images:
        result.warnings.append(f"이미지가 너무 많아 {max_images}개만 변환했습니다.")
    result.warnings.extend(image_warnings[:10])

    drawings, drawing_warnings = _extract_drawings(
        page, source_width, source_height
    )
    result.drawings = drawings
    result.warnings.extend(drawing_warnings)

    if rotation:
        matrix = page.rotation_matrix
        for block in result.text_blocks:
            block.bbox = _rotate_bbox(block.bbox, matrix)
            for line in block.lines:
                line.bbox = _rotate_bbox(line.bbox, matrix)
                for span in line.spans:
                    span.bbox = _rotate_bbox(span.bbox, matrix)
        for image in result.images:
            image.bbox = _rotate_bbox(image.bbox, matrix)
        for drawing in result.drawings:
            drawing.bbox = _rotate_bbox(drawing.bbox, matrix)
            drawing.points = [
                _rotate_point(point, matrix) for point in drawing.points
            ]

    if not result.text_blocks and not result.images and not result.drawings:
        result.warnings.append("편집 가능한 객체를 찾지 못했습니다. 페이지가 비어 있거나 스캔 이미지일 수 있습니다.")
    return result
