"""User-facing error types and helpers.

Internal exceptions carry a technical message; :class:`AppError` carries a
message that is safe and useful to show in the UI.
"""

from __future__ import annotations

from typing import Optional


class AppError(Exception):
    """Base class for errors that can be shown to the user."""

    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        return self.message


class PDFOpenError(AppError):
    """The PDF could not be opened."""


class PDFPasswordRequired(PDFOpenError):
    """The PDF is encrypted and needs a password."""

    def __init__(self, message: str = "암호가 설정된 PDF입니다. 암호를 입력해 주세요."):
        super().__init__(message)


class PDFPasswordIncorrect(PDFOpenError):
    """The supplied password was rejected."""

    def __init__(self, message: str = "PDF 암호가 올바르지 않습니다."):
        super().__init__(message)


class InvalidPDFError(AppError):
    """The file is not a valid, usable PDF."""


class OutputPathError(AppError):
    """The requested output location cannot be written."""


class ConversionCancelled(Exception):
    """Raised internally when the user cancels a conversion."""


def format_exception(exc: BaseException) -> str:
    """Return a concise Korean message plus a technical detail when useful."""

    if isinstance(exc, AppError):
        if exc.detail:
            return f"{exc.message}\n\n기술 정보: {exc.detail}"
        return exc.message
    text = str(exc).strip()
    return text or exc.__class__.__name__
