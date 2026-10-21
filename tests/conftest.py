"""Shared PDF fixtures generated at test time (no binary test assets needed)."""

from __future__ import annotations

import os
from pathlib import Path

import fitz
import pytest
from PIL import Image, ImageDraw

# Qt is only needed by the settings-panel tests; keep them headless.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _make_image(path: Path) -> Path:
    image = Image.new("RGB", (240, 120), (222, 235, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((6, 6, 233, 113), outline=(37, 99, 235), width=4)
    draw.text((24, 50), "SlideBridge", fill=(15, 23, 42))
    image.save(path)
    return path


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory) -> Path:
    """Three A4 pages: text, image, rectangle, line and polyline."""

    base = tmp_path_factory.mktemp("pdfs")
    image_path = _make_image(base / "image.png")
    path = base / "sample.pdf"

    doc = fitz.open()
    for number in (1, 2, 3):
        page = doc.new_page(width=595, height=842)
        page.insert_text(
            (60, 90),
            f"SlideBridge Test Page {number}",
            fontsize=26,
            color=(0.1, 0.2, 0.5),
        )
        page.insert_text((60, 130), "Editable text extraction test.", fontsize=14)
        page.insert_text((60, 165), "한글 텍스트 테스트", fontname="korea", fontsize=16)
        page.draw_rect(
            fitz.Rect(60, 190, 300, 250),
            color=(0.1, 0.4, 0.9),
            fill=(0.9, 0.95, 1.0),
            width=2,
        )
        page.insert_image(fitz.Rect(330, 190, 530, 290), filename=str(image_path))
        if number == 2:
            page.draw_line(
                fitz.Point(60, 320), fitz.Point(420, 360), color=(0.8, 0.2, 0.2), width=3
            )
            page.draw_polyline(
                [
                    fitz.Point(80, 400),
                    fitz.Point(160, 360),
                    fitz.Point(240, 430),
                    fitz.Point(320, 380),
                ],
                color=(0.1, 0.5, 0.3),
                fill=(0.85, 0.96, 0.9),
                width=2,
            )
    doc.set_metadata({"title": "SlideBridge Sample", "author": "Tests"})
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def scanned_pdf(tmp_path_factory) -> Path:
    """A page containing only a full-page image (simulating a scan)."""

    base = tmp_path_factory.mktemp("scanned")
    image_path = _make_image(base / "scan.png")
    path = base / "scanned.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, filename=str(image_path))
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def mixed_size_pdf(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("mixed")
    path = base / "mixed.pdf"
    doc = fitz.open()
    portrait = doc.new_page(width=595, height=842)
    portrait.insert_text((60, 90), "Portrait page", fontsize=24)
    landscape = doc.new_page(width=842, height=595)
    landscape.insert_text((60, 90), "Landscape page", fontsize=24)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def rotated_pdf(tmp_path_factory) -> Path:
    """A portrait page displayed with /Rotate 90 (landscape output)."""

    base = tmp_path_factory.mktemp("rotated")
    path = base / "rotated.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 100), "Rotated page text", fontsize=24)
    page.draw_rect(
        fitz.Rect(60, 200, 260, 260),
        color=(0.1, 0.4, 0.9),
        fill=(0.9, 0.95, 1.0),
        width=2,
    )
    page.set_rotation(90)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="session")
def encrypted_pdf(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("encrypted")
    path = base / "secret.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 90), "Protected document", fontsize=22)
    doc.save(
        str(path),
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="user-secret",
        permissions=fitz.PDF_PERM_ACCESSIBILITY | fitz.PDF_PERM_PRINT,
    )
    doc.close()
    return path


@pytest.fixture(scope="session")
def corrupt_pdf(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("corrupt") / "broken.pdf"
    path.write_bytes(b"%PDF-1.7\nthis is not a real pdf\n%%EOF\n")
    return path


@pytest.fixture(scope="session")
def empty_pdf(tmp_path_factory) -> Path:
    """A structurally valid PDF whose page tree has zero pages."""

    path = tmp_path_factory.mktemp("empty") / "empty.pdf"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [] /Count 0 >>",
    ]
    header = b"%PDF-1.4\n"
    body = b""
    offsets = [0]
    for index, payload in enumerate(objects, start=1):
        offsets.append(len(header) + len(body))
        body += f"{index} 0 obj\n".encode("ascii") + payload + b"\nendobj\n"
    xref_position = len(header) + len(body)
    xref = b"xref\n0 3\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        xref += f"{offset:010d} 00000 n \n".encode("ascii")
    trailer = (
        b"trailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n"
        + str(xref_position).encode("ascii")
        + b"\n%%EOF\n"
    )
    path.write_bytes(header + body + xref + trailer)
    return path
