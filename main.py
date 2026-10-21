"""SlideBridge application entry point."""

from __future__ import annotations

import ctypes
import logging
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox

from app.ui.main_window import MainWindow
from app.ui.theme import APP_STYLE


def create_app_icon() -> QIcon:
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(8, 8, 240, 240, 54, 54)
    painter.fillPath(path, QColor("#2563EB"))
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Segoe UI", 120)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "S")
    painter.end()
    return QIcon(pixmap)


def _log_path() -> Path:
    base = Path.home() / "AppData" / "Local" / "SlideBridge"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path.home()
    return base / "slidebridge.log"


def _install_exception_hook() -> None:
    logger = logging.getLogger("slidebridge")
    logger.setLevel(logging.ERROR)
    try:
        handler = logging.FileHandler(_log_path(), encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)s  %(message)s")
        )
        logger.addHandler(handler)
    except OSError:
        pass

    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.error("Unhandled exception\n%s", text)
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(
                None,
                "예상하지 못한 오류",
                "프로그램에서 예상하지 못한 오류가 발생했습니다.\n"
                f"{exc_value}\n\n자세한 내용은 다음 로그를 확인하세요:\n{_log_path()}",
            )

    sys.excepthook = handle_exception


def main() -> int:
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "SlideBridge.PDFToPPTX.1"
            )
        except Exception:
            pass

    _install_exception_hook()
    app = QApplication(sys.argv)
    app.setApplicationName("SlideBridge")
    app.setApplicationDisplayName("SlideBridge")
    app.setOrganizationName("SlideBridge")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    app.setWindowIcon(create_app_icon())

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
