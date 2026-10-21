"""Generate the sample PDFs used for manual quality checks.

Run from the project root:

    python scripts/create_samples.py

The encrypted sample uses the user password ``slidebridge``.
"""

from __future__ import annotations

import io
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
PASSWORD = "slidebridge"


def _gradient_image(width: int, height: int, top: tuple, bottom: tuple) -> bytes:
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(
            int(top[index] * (1 - ratio) + bottom[index] * ratio) for index in range(3)
        )
        draw.line((0, y, width, y), fill=color)
    draw.rounded_rectangle(
        (width * 0.08, height * 0.25, width * 0.92, height * 0.75),
        radius=int(min(width, height) * 0.08),
        outline=(255, 255, 255),
        width=max(2, width // 200),
    )
    draw.text(
        (width * 0.16, height * 0.46),
        "SlideBridge sample image",
        fill=(255, 255, 255),
    )
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=88, optimize=True)
    return output.getvalue()


def _table(page: fitz.Page, x: float, y: float, rows: int, cols: int, width: float, height: float) -> None:
    row_height = height / rows
    col_width = width / cols
    page.draw_rect(fitz.Rect(x, y, x + width, y + height), color=(0.2, 0.3, 0.5), width=1.2)
    for row in range(1, rows):
        page.draw_line(
            fitz.Point(x, y + row * row_height),
            fitz.Point(x + width, y + row * row_height),
            color=(0.55, 0.62, 0.75),
            width=0.8,
        )
    for col in range(1, cols):
        page.draw_line(
            fitz.Point(x + col * col_width, y),
            fitz.Point(x + col * col_width, y + height),
            color=(0.55, 0.62, 0.75),
            width=0.8,
        )
    headers = ["항목", "설명", "값"]
    for col in range(min(cols, len(headers))):
        page.insert_text(
            (x + col * col_width + 6, y + 18),
            headers[col],
            fontname="korea",
            fontsize=10,
            color=(0.1, 0.2, 0.4),
        )
    for row in range(1, rows):
        for col in range(min(cols, 3)):
            page.insert_text(
                (x + col * col_width + 6, y + row * row_height + 16),
                f"{row}-{col + 1}",
                fontsize=9,
                color=(0.2, 0.25, 0.35),
            )


def text_only(path: Path) -> None:
    doc = fitz.open()
    for number in (1, 2):
        page = doc.new_page(width=595, height=842)
        page.insert_text(
            (60, 100), "SlideBridge text document", fontsize=26, color=(0.1, 0.2, 0.5)
        )
        page.insert_text(
            (60, 135), "PDF to PowerPoint conversion test", fontsize=14, color=(0.25, 0.3, 0.4)
        )
        page.insert_text(
            (60, 175),
            "한글 텍스트와 특수문자: 가나다라 · “인용” · 100% · ① ② ③",
            fontname="korea",
            fontsize=13,
        )
        body = (
            "This sample contains only text. The editable mode should create text boxes\n"
            "with positions and sizes close to the original PDF layout. Line breaks are\n"
            "kept as separate paragraphs so that the reading order remains intact."
        )
        page.insert_textbox(
            fitz.Rect(60, 210, 530, 360), body, fontsize=12, lineheight=1.5
        )
        page.insert_text(
            (60, 760),
            f"Page {number} of 2",
            fontsize=9,
            color=(0.45, 0.5, 0.6),
        )
    doc.save(str(path))
    doc.close()


def mixed_content(path: Path, image_bytes: bytes) -> None:
    doc = fitz.open()
    for number in (1, 2, 3):
        page = doc.new_page(width=595, height=842)
        page.insert_text(
            (50, 80),
            f"Mixed content sample — page {number}",
            fontsize=22,
            color=(0.08, 0.15, 0.35),
        )
        page.insert_text(
            (50, 108),
            "텍스트, 이미지, 표, 도형이 함께 있는 페이지입니다.",
            fontname="korea",
            fontsize=11,
            color=(0.3, 0.35, 0.45),
        )
        page.draw_rect(
            fitz.Rect(50, 125, 545, 135), color=None, fill=(0.15, 0.35, 0.75)
        )
        page.insert_image(fitz.Rect(50, 155, 280, 300), stream=image_bytes)
        page.insert_textbox(
            fitz.Rect(300, 155, 545, 300),
            "An embedded image is placed next to a text block. "
            "The converter extracts the image and keeps its rectangle. "
            "Text is rebuilt as editable text boxes.",
            fontsize=11,
            lineheight=1.45,
        )
        _table(page, 50, 325, rows=5, cols=3, width=495, height=150)
        page.draw_polyline(
            [
                fitz.Point(60, 520),
                fitz.Point(150, 480),
                fitz.Point(240, 550),
                fitz.Point(330, 500),
                fitz.Point(420, 560),
            ],
            color=(0.1, 0.55, 0.35),
            fill=(0.88, 0.97, 0.92),
            width=2,
        )
        page.draw_bezier(
            fitz.Point(60, 620),
            fitz.Point(160, 570),
            fitz.Point(300, 690),
            fitz.Point(500, 610),
            color=(0.85, 0.3, 0.2),
            width=3,
        )
        page.draw_circle(
            fitz.Point(80, 690),
            24,
            color=(0.2, 0.35, 0.7),
            fill=(0.9, 0.94, 1.0),
            width=2,
        )
        page.insert_text(
            (120, 697),
            "Vector circle and curves",
            fontsize=11,
            color=(0.2, 0.25, 0.35),
        )
    doc.save(str(path))
    doc.close()


def tables_and_shapes(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 70), "Tables and shapes", fontsize=24, color=(0.1, 0.2, 0.5))
    _table(page, 50, 95, rows=8, cols=3, width=495, height=240)
    colors = [
        (0.95, 0.9, 0.85),
        (0.9, 0.95, 0.88),
        (0.88, 0.92, 0.98),
        (0.96, 0.88, 0.92),
    ]
    for index in range(4):
        x = 50 + (index % 2) * 260
        y = 380 + (index // 2) * 150
        page.draw_rect(
            fitz.Rect(x, y, x + 220, y + 120),
            color=(0.2, 0.3, 0.5),
            fill=colors[index],
            width=1.5,
        )
        page.draw_line(
            fitz.Point(x + 15, y + 20),
            fitz.Point(x + 205, y + 100),
            color=(0.2, 0.3, 0.5),
            width=1,
        )
        page.insert_text(
            (x + 18, y + 55), f"Shape {index + 1}", fontsize=13, color=(0.15, 0.2, 0.3)
        )
    page.insert_text(
        (50, 760),
        "This page stresses table borders and simple vector shapes.",
        fontsize=9,
        color=(0.4, 0.45, 0.55),
    )
    doc.save(str(path))
    doc.close()


def landscape(path: Path, image_bytes: bytes) -> None:
    doc = fitz.open()
    for number in (1, 2):
        page = doc.new_page(width=960, height=540)
        page.insert_text(
            (50, 80),
            f"Landscape slide {number}",
            fontsize=30,
            color=(0.08, 0.15, 0.35),
        )
        page.insert_text(
            (50, 112),
            "가로형 PDF 페이지입니다. 원본 비율 유지 모드에서 16:9 슬라이드와 유사합니다.",
            fontname="korea",
            fontsize=13,
            color=(0.3, 0.35, 0.45),
        )
        page.insert_image(fitz.Rect(560, 150, 910, 350), stream=image_bytes)
        page.draw_rect(
            fitz.Rect(50, 150, 520, 350),
            color=(0.2, 0.4, 0.8),
            fill=(0.92, 0.96, 1.0),
            width=2,
        )
        page.insert_textbox(
            fitz.Rect(75, 180, 495, 320),
            "Landscape pages keep their own aspect ratio. When a fixed 16:9 or 4:3 "
            "ratio is selected, the page is fitted with letterboxing instead of being "
            "cropped.",
            fontsize=14,
            lineheight=1.5,
            color=(0.15, 0.2, 0.3),
        )
    doc.save(str(path))
    doc.close()


def many_pages(path: Path) -> None:
    doc = fitz.open()
    for number in range(1, 21):
        page = doc.new_page(width=595, height=842)
        page.insert_text(
            (60, 90), f"Large document — page {number}", fontsize=22, color=(0.1, 0.2, 0.5)
        )
        page.insert_text(
            (60, 125),
            f"총 20페이지 중 {number}번째 페이지입니다.",
            fontname="korea",
            fontsize=12,
        )
        page.insert_textbox(
            fitz.Rect(60, 170, 530, 420),
            "This sample is used to check progress reporting, cancellation, and "
            "page-range selection. Only the selected pages should appear in the "
            "output presentation.",
            fontsize=12,
            lineheight=1.5,
        )
        page.draw_rect(
            fitz.Rect(60, 450, 530, 470),
            color=None,
            fill=(0.2, 0.45, 0.85),
        )
        page.insert_text((60, 510), f"{number:02d}", fontsize=36, color=(0.2, 0.3, 0.5))
    doc.save(str(path))
    doc.close()


def encrypted(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 100), "Encrypted sample", fontsize=26, color=(0.1, 0.2, 0.5))
    page.insert_text(
        (60, 140),
        "암호가 설정된 PDF입니다. 암호: slidebridge",
        fontname="korea",
        fontsize=14,
    )
    page.insert_textbox(
        fitz.Rect(60, 190, 530, 330),
        "SlideBridge asks for the password before conversion. The original file is "
        "never modified. This sample has a user password and restricted permissions.",
        fontsize=12,
        lineheight=1.5,
    )
    doc.save(
        str(path),
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-slidebridge",
        user_pw=PASSWORD,
        permissions=fitz.PDF_PERM_ACCESSIBILITY | fitz.PDF_PERM_PRINT,
    )
    doc.close()


def large_image(path: Path) -> None:
    image = Image.new("RGB", (3600, 2400))
    draw = ImageDraw.Draw(image)
    for y in range(0, 2400, 8):
        ratio = y / 2400
        draw.rectangle(
            (0, y, 3600, y + 8),
            fill=(
                int(40 + 120 * ratio),
                int(80 + 80 * ratio),
                int(180 - 60 * ratio),
            ),
        )
    for index in range(24):
        x = (index * 137) % 3400
        y = (index * 211) % 2200
        draw.ellipse((x, y, x + 180, y + 180), outline=(255, 255, 255), width=6)
    draw.text((120, 1100), "Large embedded image (3600 x 2400)", fill=(255, 255, 255))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=88)
    image_bytes = output.getvalue()

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 70), "Large image sample", fontsize=22, color=(0.1, 0.2, 0.5))
    page.insert_image(fitz.Rect(40, 100, 555, 760), stream=image_bytes)
    doc.save(str(path))
    doc.close()


def main() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    image_bytes = _gradient_image(960, 540, (37, 99, 235), (12, 40, 90))

    text_only(SAMPLES / "01_text_only.pdf")
    mixed_content(SAMPLES / "02_mixed_content.pdf", image_bytes)
    tables_and_shapes(SAMPLES / "03_tables_shapes.pdf")
    landscape(SAMPLES / "04_landscape.pdf", image_bytes)
    many_pages(SAMPLES / "05_many_pages.pdf")
    encrypted(SAMPLES / "06_encrypted.pdf")
    large_image(SAMPLES / "07_large_image.pdf")

    print(f"Samples written to: {SAMPLES}")
    for path in sorted(SAMPLES.glob("*.pdf")):
        print(f"  {path.name:26s} {path.stat().st_size / 1024:8.1f} KB")
    print(f"Encrypted sample password: {PASSWORD}")


if __name__ == "__main__":
    main()
