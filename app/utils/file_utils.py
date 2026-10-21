"""Small filesystem helpers."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Tuple


def human_file_size(num_bytes: int) -> str:
    """Format a byte count for the UI."""

    size = float(max(0, num_bytes))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def unique_output_path(directory: Path, stem: str) -> Path:
    """Return ``stem.pptx`` or ``stem (2).pptx`` ... without overwriting."""

    directory = Path(directory)
    candidate = directory / f"{stem}.pptx"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem} ({counter}).pptx"
        counter += 1
    return candidate


def can_write_directory(directory: Path) -> Tuple[bool, str]:
    """Check that *directory* exists and accepts a new file."""

    directory = Path(directory)
    if not directory.exists():
        return False, "저장 폴더가 존재하지 않습니다."
    if not directory.is_dir():
        return False, "저장 위치가 폴더가 아닙니다."
    try:
        fd, probe = tempfile.mkstemp(prefix=".deckforge_", suffix=".tmp", dir=str(directory))
        os.close(fd)
        os.unlink(probe)
    except OSError as exc:
        return False, f"저장 폴더에 쓸 수 없습니다: {exc.strerror or exc}"
    return True, ""


def is_probably_pdf(path: Path) -> bool:
    """Check the ``%PDF-`` header without fully parsing the document."""

    try:
        with open(path, "rb") as handle:
            return handle.read(5) == b"%PDF-"
    except OSError:
        return False
