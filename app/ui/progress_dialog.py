"""Progress UI and a PDF preview dialog."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import fitz
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.core.pdf_loader import open_pdf
from app.core.pdf_renderer import render_thumbnail
from app.services.conversion_service import ProgressInfo


class ProgressPanel(QFrame):
    """Inline progress card shown under the start button."""

    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("progressPanel")
        self.setProperty("state", "running")
        self.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.title_label = QLabel("변환 준비 중…")
        self.title_label.setStyleSheet("font-weight: 700; background: transparent;")
        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("muted")
        self.percent_label.setStyleSheet("font-weight: 700; background: transparent;")
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.percent_label)
        layout.addLayout(header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        detail_row = QHBoxLayout()
        self.detail_label = QLabel("")
        self.detail_label.setObjectName("muted")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("background: transparent;")
        self.cancel_button = QPushButton("취소")
        self.cancel_button.setObjectName("danger")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        detail_row.addWidget(self.detail_label, 1)
        detail_row.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(detail_row)

    def _set_state(self, state: str) -> None:
        self.setProperty("state", state)
        self.progress_bar.setProperty("state", state)
        for widget in (self, self.progress_bar):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def start_conversion(self, total_pages: int) -> None:
        self._set_state("running")
        self.setVisible(True)
        self.title_label.setObjectName("")
        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)
        self.title_label.setText("변환 중")
        self.percent_label.setText("0%")
        self.progress_bar.setValue(0)
        self.detail_label.setText(f"총 {total_pages}페이지를 변환합니다.")
        self.cancel_button.setVisible(True)
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText("취소")

    def update_progress(self, info: ProgressInfo) -> None:
        self.setVisible(True)
        self._set_state("running")
        self.progress_bar.setValue(info.percent)
        self.percent_label.setText(f"{info.percent}%")
        if info.phase == "done":
            self.title_label.setText("변환 완료")
        elif info.phase == "saving":
            self.title_label.setText("파일 저장 중")
        elif info.phase == "validating":
            self.title_label.setText("파일 검증 중")
        else:
            self.title_label.setText("변환 중")
        if info.page_number and info.total:
            self.detail_label.setText(f"{info.message}")
        else:
            self.detail_label.setText(info.message)

    def mark_cancelling(self) -> None:
        self.title_label.setText("취소 중…")
        self.detail_label.setText("현재 페이지 처리가 끝나면 안전하게 취소됩니다.")
        self.cancel_button.setEnabled(False)

    def show_cancelled(self) -> None:
        self._set_state("idle")
        self.title_label.setText("변환이 취소되었습니다")
        self.percent_label.setText("")
        self.progress_bar.setValue(0)
        self.detail_label.setText("출력 파일은 생성되지 않았습니다. 설정을 확인한 뒤 다시 시작하세요.")
        self.cancel_button.setVisible(False)

    def show_error(self, message: str) -> None:
        self.setVisible(True)
        self._set_state("error")
        self.title_label.setText("변환 실패")
        self.title_label.setObjectName("errorTitle")
        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)
        self.percent_label.setText("")
        self.detail_label.setText(message)
        self.cancel_button.setVisible(False)

    def show_done(self) -> None:
        self._set_state("done")
        self.title_label.setText("변환 완료")
        self.progress_bar.setValue(100)
        self.percent_label.setText("100%")
        self.cancel_button.setVisible(False)

    def reset(self) -> None:
        self._set_state("running")
        self.title_label.setObjectName("")
        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)
        self.setVisible(False)
        self.progress_bar.setValue(0)
        self.percent_label.setText("0%")
        self.detail_label.setText("")
        self.cancel_button.setVisible(True)


class PreviewDialog(QDialog):
    """Renders original PDF pages for a quick sanity check."""

    def __init__(self, pdf_path: Path, password: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("원본 PDF 미리보기 — DeckForge")
        self.resize(900, 720)
        self._pdf_path = Path(pdf_path)
        self._password = password
        self._doc: Optional["fitz.Document"] = None
        self._pixmap: Optional[QPixmap] = None
        self._page_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        header = QLabel(self._pdf_path.name)
        header.setStyleSheet("font-size: 15px; font-weight: 700;")
        layout.addWidget(header)
        note = QLabel("원본 PDF의 페이지를 표시합니다. 변환된 PPTX의 모양과는 다를 수 있습니다.")
        note.setObjectName("muted")
        layout.addWidget(note)

        self.image_label = QLabel("페이지를 불러오는 중…")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(420)
        self.image_label.setStyleSheet(
            "background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 8px;"
        )
        layout.addWidget(self.image_label, 1)

        nav = QHBoxLayout()
        self.prev_button = QPushButton("← 이전")
        self.next_button = QPushButton("다음 →")
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setFixedWidth(110)
        self.page_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label = QLabel("/ 1")
        self.page_label.setObjectName("muted")
        nav.addStretch(1)
        nav.addWidget(self.prev_button)
        nav.addWidget(self.page_spin)
        nav.addWidget(self.page_label)
        nav.addWidget(self.next_button)
        nav.addStretch(1)
        layout.addLayout(nav)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setText("닫기")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.prev_button.clicked.connect(lambda: self._step(-1))
        self.next_button.clicked.connect(lambda: self._step(1))
        self.page_spin.valueChanged.connect(self._render_page)
        self.finished.connect(lambda _result: self._close_document())

        try:
            self._doc = open_pdf(self._pdf_path, self._password)
            self._page_count = self._doc.page_count
        except Exception as exc:
            self.image_label.setText(f"PDF를 불러오지 못했습니다.\n{exc}")
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            self.page_spin.setEnabled(False)
            return

        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(max(1, self._page_count))
        self.page_spin.blockSignals(False)
        self.page_label.setText(f"/ {self._page_count}")
        self._render_page(1)

    def _step(self, delta: int) -> None:
        value = self.page_spin.value() + delta
        value = max(1, min(self._page_count or 1, value))
        self.page_spin.setValue(value)
        self._update_nav()

    def _update_nav(self) -> None:
        self.prev_button.setEnabled(self.page_spin.value() > 1)
        self.next_button.setEnabled(self.page_spin.value() < self._page_count)

    def _render_page(self, page_number: int) -> None:
        if not self._doc:
            return
        try:
            page = self._doc.load_page(max(0, page_number - 1))
            data = render_thumbnail(page, max_width=1100)
            if not data:
                raise RuntimeError("페이지를 렌더링하지 못했습니다.")
            pixmap = QPixmap()
            if not pixmap.loadFromData(data, "PNG"):
                raise RuntimeError("이미지를 표시하지 못했습니다.")
            self._pixmap = pixmap
            self._update_pixmap()
        except Exception as exc:
            self._pixmap = None
            self.image_label.setText(f"페이지를 표시하지 못했습니다.\n{exc}")
        self._update_nav()

    def _update_pixmap(self) -> None:
        if not self._pixmap:
            return
        margins = self.image_label.contentsMargins()
        width = max(200, self.image_label.width() - margins.left() - margins.right() - 16)
        height = max(200, self.image_label.height() - margins.top() - margins.bottom() - 16)
        scaled = self._pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_pixmap()

    def closeEvent(self, event) -> None:
        self._close_document()
        super().closeEvent(event)

    def _close_document(self) -> None:
        if self._doc is not None:
            self._doc.close()
            self._doc = None
