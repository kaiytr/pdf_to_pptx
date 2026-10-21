"""QThread worker that runs ConversionService off the UI thread."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot

from app.models.conversion_options import ConversionOptions
from app.services.conversion_service import ConversionService
from app.utils.error_handler import AppError, ConversionCancelled, format_exception


class ConversionWorker(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str, str)
    cancelled = Signal()

    def __init__(
        self,
        source_path: Path,
        options: ConversionOptions,
        password: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._source_path = Path(source_path)
        self._options = options
        self._password = password
        self.cancel_event = threading.Event()
        self._service = ConversionService()

    def cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.convert(
                self._source_path,
                self._options,
                password=self._password,
                progress=self.progress.emit,
                cancel_event=self.cancel_event,
            )
            self.finished.emit(result)
        except ConversionCancelled:
            self.cancelled.emit()
        except AppError as exc:
            self.failed.emit(exc.message, exc.detail or "")
        except Exception as exc:  # defensive: never let the worker die silently
            self.failed.emit(
                "변환 중 예상하지 못한 오류가 발생했습니다.",
                format_exception(exc),
            )
