"""DeckForge main window and conversion workflow."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QPoint, QSettings, QTimer, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME, __version__
from app.core.pdf_analyzer import PDFAnalysis, analyze_pdf
from app.core.pdf_loader import PDFInfo
from app.models.conversion_options import (
    ConversionOptions,
    ConversionResult,
    parse_page_range,
)
from app.services.validation_service import validate_output_path
from app.ui.conversion_worker import ConversionWorker
from app.ui.progress_dialog import PreviewDialog, ProgressPanel
from app.ui.settings_panel import SettingsPanel
from app.utils.error_handler import (
    AppError,
    PDFPasswordIncorrect,
    PDFPasswordRequired,
    format_exception,
)
from app.utils.file_utils import human_file_size, unique_output_path

DPI_MM = 25.4 / 72.0


class LogoMark(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 44)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, 44, 44, 12, 12)
        painter.fillPath(path, QColor("#2563EB"))
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Segoe UI", 20)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "D")
        painter.end()


class DropZone(QFrame):
    file_dropped = Signal(str)
    browse_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(128)
        self.setProperty("dragActive", False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel("PDF")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(44, 44)
        self.icon_label.setStyleSheet(
            "background: #EFF6FF; color: #2563EB; border-radius: 13px;"
            "font-size: 13px; font-weight: 800; letter-spacing: 1px;"
        )
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.title_label = QLabel("PDF 파일을 여기에 끌어다 놓으세요")
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("또는 아래 버튼으로 파일을 선택하세요. 원본 PDF는 변경되지 않습니다.")
        self.subtitle_label.setObjectName("muted")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        layout.addWidget(self.subtitle_label)

        self.browse_button = QPushButton("PDF 파일 선택")
        self.browse_button.setObjectName("primary")
        self.browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_button.clicked.connect(self.browse_requested.emit)
        layout.addWidget(self.browse_button, 0, Qt.AlignmentFlag.AlignHCenter)

    def set_loaded(self, loaded: bool) -> None:
        if loaded:
            self.title_label.setText("다른 PDF로 바꾸려면 여기에 놓으세요")
            self.subtitle_label.setText("현재 PDF는 아래에 표시됩니다. 설정을 확인하고 변환을 시작하세요.")
        else:
            self.title_label.setText("PDF 파일을 여기에 끌어다 놓으세요")
            self.subtitle_label.setText(
                "또는 아래 버튼으로 파일을 선택하세요. 원본 PDF는 변경되지 않습니다."
            )

    def _set_drag_active(self, active: bool) -> None:
        if self.property("dragActive") == active:
            return
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_drag_active(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self._set_drag_active(False)
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.file_dropped.emit(url.toLocalFile())
                event.acceptProposedAction()
                return
        event.ignore()


class FileCard(QFrame):
    preview_requested = Signal()
    change_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("fileCard")
        self.setVisible(False)
        self.setMinimumHeight(70)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        icon = QLabel("PDF")
        icon.setFixedSize(42, 42)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            "background: #FEE2E2; color: #B91C1C; border-radius: 9px;"
            "font-size: 11px; font-weight: 800;"
        )
        layout.addWidget(icon)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.name_label = QLabel("")
        self.name_label.setObjectName("fileName")
        self.name_label.setWordWrap(True)
        self.meta_label = QLabel("")
        self.meta_label.setObjectName("fileNameMeta")
        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.meta_label)
        layout.addLayout(text_layout, 1)

        self.preview_button = QPushButton("미리보기")
        self.preview_button.clicked.connect(self.preview_requested.emit)
        self.change_button = QPushButton("다른 파일")
        self.change_button.clicked.connect(self.change_requested.emit)
        layout.addWidget(self.preview_button)
        layout.addWidget(self.change_button)

    def set_file_info(self, info: PDFInfo) -> None:
        self.name_label.setText(info.path.name)
        self.name_label.setToolTip(str(info.path))
        size = info.page_sizes[0] if info.page_sizes else None
        size_text = ""
        if size:
            size_text = (
                f" · {size.width * DPI_MM:.0f}×{size.height * DPI_MM:.0f} mm"
            )
        self.meta_label.setText(
            f"{info.page_count}페이지 · {human_file_size(info.file_size)}{size_text}"
        )
        self.setVisible(True)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeckForge — PDF to PowerPoint")
        self.resize(1000, 900)
        self.setMinimumSize(820, 680)
        self.setAcceptDrops(True)

        self._settings = QSettings("DeckForge", "DeckForge")
        self._pdf_path: Optional[Path] = None
        self._password: Optional[str] = None
        self._info: Optional[PDFInfo] = None
        self._analysis: Optional[PDFAnalysis] = None
        self._result: Optional[ConversionResult] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[ConversionWorker] = None
        self._busy = False
        self._closing_after_cancel = False

        self._build_ui()
        self._restore_window_state()
        self._update_start_state()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(
            "background: #FFFFFF; border-bottom: 1px solid #E2E8F0;"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(26, 10, 26, 10)
        header_layout.setSpacing(12)
        header_layout.addWidget(LogoMark())

        title_layout = QVBoxLayout()
        title_layout.setSpacing(0)
        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        subtitle = QLabel("PDF를 편집 가능한 PowerPoint로")
        subtitle.setObjectName("appSubtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout)
        header_layout.addStretch(1)

        self.menu_button = QToolButton()
        self.menu_button.setText("도움말")
        self.menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        menu = QMenu(self.menu_button)
        help_action = menu.addAction("사용 방법")
        limits_action = menu.addAction("지원 범위와 한계")
        menu.addSeparator()
        about_action = menu.addAction("프로그램 정보")
        help_action.triggered.connect(self._show_help)
        limits_action.triggered.connect(self._show_limits)
        about_action.triggered.connect(self._show_about)
        self._help_menu = menu
        self.menu_button.clicked.connect(self._show_help_menu)
        header_layout.addWidget(self.menu_button)
        root_layout.addWidget(header)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_convert_page())
        self.stack.addWidget(self._build_done_page())
        root_layout.addWidget(self.stack, 1)

        footer = QLabel(f"원본 PDF는 수정·삭제되지 않습니다.   ·   {APP_NAME} v{__version__}")
        footer.setObjectName("muted")
        footer.setStyleSheet(
            "background: #FFFFFF; border-top: 1px solid #E2E8F0; padding: 7px 26px;"
        )
        root_layout.addWidget(footer)

    def _build_convert_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.convert_scroll = scroll
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(26, 16, 26, 20)
        layout.setSpacing(12)

        self.drop_zone = DropZone()
        self.drop_zone.browse_requested.connect(self._choose_file)
        self.drop_zone.file_dropped.connect(self._load_pdf)
        layout.addWidget(self.drop_zone)

        self.file_card = FileCard()
        self.file_card.preview_requested.connect(self._open_preview)
        self.file_card.change_requested.connect(self._choose_file)
        layout.addWidget(self.file_card)

        self.settings_panel = SettingsPanel()
        self.settings_panel.browse_output_requested.connect(self._choose_output)
        self.settings_panel.settings_changed.connect(self._clear_error_banner)
        layout.addWidget(self.settings_panel)

        self.warning_label = QLabel("")
        self.warning_label.setObjectName("warningText")
        self.warning_label.setWordWrap(True)
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorText")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_hint = QLabel("변환 결과는 PPTX 파일로 저장됩니다. 저장 위치는 위에서 변경할 수 있습니다.")
        action_hint.setObjectName("muted")
        action_hint.setWordWrap(True)
        self.start_button = QPushButton("변환 시작")
        self.start_button.setObjectName("primary")
        self.start_button.setMinimumWidth(168)
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.clicked.connect(self._start_conversion)
        action_row.addWidget(action_hint, 1)
        action_row.addWidget(self.start_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(action_row)

        self.progress_panel = ProgressPanel()
        self.progress_panel.cancel_requested.connect(self._cancel_conversion)
        layout.addWidget(self.progress_panel)
        layout.addStretch(1)

        scroll.setWidget(content)
        return scroll

    def _build_done_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(26, 30, 26, 30)
        outer.addStretch(1)

        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(760)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 32, 34, 30)
        card_layout.setSpacing(12)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        badge = QLabel("✓")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(64, 64)
        badge.setStyleSheet(
            "background: #ECFDF5; color: #059669; border-radius: 32px;"
            "font-size: 30px; font-weight: 700;"
        )
        card_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("변환 완료")
        title.setObjectName("doneTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)

        self.done_summary_label = QLabel("")
        self.done_summary_label.setObjectName("muted")
        self.done_summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.done_summary_label.setWordWrap(True)
        card_layout.addWidget(self.done_summary_label)

        self.done_path_label = QLineEdit()
        self.done_path_label.setReadOnly(True)
        self.done_path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.done_path_label.setStyleSheet(
            "background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px;"
            "padding: 9px 12px; color: #334155; font-size: 12px;"
        )
        card_layout.addWidget(self.done_path_label)

        self.done_warning_label = QLabel("")
        self.done_warning_label.setObjectName("warningText")
        self.done_warning_label.setWordWrap(True)
        self.done_warning_label.setVisible(False)
        card_layout.addWidget(self.done_warning_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.open_folder_button = QPushButton("저장 위치 열기")
        self.open_folder_button.setObjectName("primary")
        self.open_folder_button.clicked.connect(self._open_output_folder)
        preview_button = QPushButton("원본 미리보기")
        preview_button.clicked.connect(self._open_preview)
        new_button = QPushButton("새 파일 변환")
        new_button.clicked.connect(self._new_conversion)
        button_row.addStretch(1)
        button_row.addWidget(self.open_folder_button)
        button_row.addWidget(preview_button)
        button_row.addWidget(new_button)
        button_row.addStretch(1)
        card_layout.addLayout(button_row)

        hint = QLabel(
            "PowerPoint에서 파일을 열어 슬라이드를 확인하세요. "
            "편집 가능 모드에서도 복잡한 그래픽은 원본과 다를 수 있습니다."
        )
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        card_layout.addWidget(hint)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)
        scroll.setWidget(content)
        return scroll

    # ------------------------------------------------------------ window state
    def _restore_window_state(self) -> None:
        geometry = self._settings.value("geometry")
        if geometry is not None:
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass

    def closeEvent(self, event) -> None:
        if self._busy and self._worker is not None:
            answer = QMessageBox.question(
                self,
                "변환 취소 후 종료",
                "변환이 진행 중입니다. 작업을 취소하고 프로그램을 종료할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer is not QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._closing_after_cancel = True
            self._worker.cancel()
            self.progress_panel.mark_cancelling()
            self.settings_panel.set_controls_enabled(False)
            self.start_button.setEnabled(False)
            event.ignore()
            return
        self._settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    # ------------------------------------------------------------------ files
    def dragEnterEvent(self, event) -> None:
        if not self._busy and event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self._load_pdf(url.toLocalFile())
                event.acceptProposedAction()
                return
        event.ignore()

    def _choose_file(self) -> None:
        if self._busy:
            return
        last_dir = self._settings.value("last_dir", str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(
            self, "PDF 파일 선택", str(last_dir), "PDF 파일 (*.pdf)"
        )
        if path:
            self._load_pdf(path)

    def _load_pdf(self, path_text: str) -> None:
        if self._busy:
            return
        path = Path(path_text)
        self._settings.setValue("last_dir", str(path.parent))
        self._clear_error_banner()

        if path.suffix.lower() != ".pdf":
            self._show_error_banner("PDF 파일만 선택할 수 있습니다.")
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        wait_cursor_active = True
        password: Optional[str] = None
        info: Optional[PDFInfo] = None
        analysis: Optional[PDFAnalysis] = None
        try:
            for _attempt in range(3):
                try:
                    analysis = analyze_pdf(path, password)
                    info = analysis.info
                    break
                except PDFPasswordRequired:
                    QApplication.restoreOverrideCursor()
                    wait_cursor_active = False
                    entered, ok = QInputDialog.getText(
                        self,
                        "PDF 암호",
                        "암호가 설정된 PDF입니다.\n암호를 입력하세요:",
                        QLineEdit.EchoMode.Password,
                    )
                    if not ok:
                        return
                    password = entered
                    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                    wait_cursor_active = True
                except PDFPasswordIncorrect:
                    QApplication.restoreOverrideCursor()
                    wait_cursor_active = False
                    QMessageBox.warning(
                        self, "암호 오류", "PDF 암호가 올바르지 않습니다. 다시 입력해 주세요."
                    )
                    password = None
                    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                    wait_cursor_active = True
                except AppError as exc:
                    self._show_error_banner(format_exception(exc))
                    return
                except Exception as exc:
                    self._show_error_banner(
                        "PDF를 불러오는 중 오류가 발생했습니다.\n" + format_exception(exc)
                    )
                    return
            if info is None or analysis is None:
                self._show_error_banner("PDF 암호를 확인하지 못했습니다. 다시 시도해 주세요.")
                return
        finally:
            if wait_cursor_active:
                QApplication.restoreOverrideCursor()

        self._pdf_path = path
        self._password = password
        self._info = info
        self._analysis = analysis
        self._result = None
        self.stack.setCurrentIndex(0)
        self.file_card.set_file_info(info)
        self.drop_zone.set_loaded(True)
        self.settings_panel.set_page_count(info.page_count)
        default_output = unique_output_path(path.parent, path.stem)
        self.settings_panel.set_output_path(default_output)
        self._show_analysis_warnings(analysis)
        self.progress_panel.reset()
        self.start_button.setText("변환 시작")
        self._update_start_state()

    def _show_analysis_warnings(self, analysis: PDFAnalysis) -> None:
        messages: List[str] = list(analysis.warnings)
        if analysis.is_probably_scanned and not any("스캔" in message for message in messages):
            messages.append(
                "스캔 문서는 편집 가능 모드에서도 텍스트 편집이 어려울 수 있습니다."
            )
        if messages:
            self.warning_label.setText("참고  ·  " + "  /  ".join(messages))
            self.warning_label.setVisible(True)
        else:
            self.warning_label.setVisible(False)

    def _open_preview(self) -> None:
        if not self._pdf_path:
            self._show_error_banner("미리 볼 PDF 파일을 먼저 선택해 주세요.")
            return
        dialog = PreviewDialog(self._pdf_path, self._password, self)
        dialog.exec()

    def _choose_output(self) -> None:
        if self._busy:
            return
        suggested = self.settings_panel.output_text()
        if not suggested and self._pdf_path:
            suggested = str(unique_output_path(self._pdf_path.parent, self._pdf_path.stem))
        path, _ = QFileDialog.getSaveFileName(
            self, "PPTX 저장 위치 선택", suggested, "PowerPoint 파일 (*.pptx)"
        )
        if path:
            if not path.lower().endswith(".pptx"):
                path += ".pptx"
            self.settings_panel.set_output_path(path)

    # -------------------------------------------------------------- conversion
    def _build_options(self) -> ConversionOptions:
        if self._info is None:
            raise ValueError("PDF 파일을 먼저 선택해 주세요.")
        if self.settings_panel.custom_pages_radio.isChecked():
            range_text = self.settings_panel.page_range_text()
            if not range_text:
                self.settings_panel.focus_page_range()
                raise ValueError("변환할 페이지 범위를 입력하세요. 예: 1-3, 5")
        else:
            range_text = ""
        try:
            parse_page_range(range_text, self._info.page_count)
        except ValueError as exc:
            self.settings_panel.focus_page_range()
            raise ValueError(str(exc)) from exc

        output_text = self.settings_panel.output_text().strip()
        if not output_text:
            raise ValueError("저장 위치를 지정해 주세요.")
        output = Path(output_text).expanduser()
        if not output.is_absolute():
            output = (Path.cwd() / output).resolve()
        if output.suffix.lower() != ".pptx":
            output = output.with_suffix(".pptx")
            self.settings_panel.set_output_path(output)
        validate_output_path(output)
        return ConversionOptions(
            output_path=output,
            mode=self.settings_panel.selected_mode(),
            ratio=self.settings_panel.selected_ratio(),
            quality=self.settings_panel.selected_quality(),
            page_range=range_text,
        )

    def _start_conversion(self) -> None:
        if self._busy:
            return
        self._clear_error_banner()
        if not self._pdf_path or not self._info:
            self._show_error_banner("PDF 파일을 먼저 선택해 주세요.")
            return
        try:
            options = self._build_options()
        except AppError as exc:
            self._show_error_banner(format_exception(exc))
            return
        except ValueError as exc:
            self._show_error_banner(str(exc))
            return

        if options.output_path.exists():
            answer = QMessageBox.question(
                self,
                "파일 덮어쓰기",
                f"같은 이름의 파일이 이미 있습니다.\n\n{options.output_path.name}\n\n덮어쓸까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer is not QMessageBox.StandardButton.Yes:
                return

        try:
            pages = parse_page_range(options.page_range, self._info.page_count)
        except ValueError as exc:
            self._show_error_banner(str(exc))
            return

        self._busy = True
        self._result = None
        self.settings_panel.set_controls_enabled(False)
        self.start_button.setEnabled(False)
        self.start_button.setText("변환 중…")
        self.file_card.setEnabled(False)
        self.progress_panel.start_conversion(len(pages))
        QTimer.singleShot(
            0, lambda: self.convert_scroll.ensureWidgetVisible(self.progress_panel, 0, 24)
        )

        thread = QThread(self)
        worker = ConversionWorker(self._pdf_path, options, self._password)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.progress_panel.update_progress)
        worker.finished.connect(self._on_conversion_finished)
        worker.failed.connect(self._on_conversion_failed)
        worker.cancelled.connect(self._on_conversion_cancelled)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        thread.start()

    def _cancel_conversion(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.progress_panel.mark_cancelling()
            self.start_button.setEnabled(False)

    def _on_conversion_finished(self, result: ConversionResult) -> None:
        self._busy = False
        self._result = result
        self.settings_panel.set_controls_enabled(True)
        self.file_card.setEnabled(True)
        self.start_button.setText("변환 시작")
        self.start_button.setEnabled(True)
        self.progress_panel.show_done()

        self.done_summary_label.setText(
            f"{result.output_path.name}  ·  {result.converted_pages}페이지  ·  "
            f"{result.elapsed_seconds:.1f}초"
        )
        self.done_path_label.setText(str(result.output_path))
        self.done_path_label.setToolTip(str(result.output_path))
        self.done_path_label.setCursorPosition(0)
        warnings = list(result.warnings)
        if result.failed_pages:
            lines = [
                f"페이지 {failure.page_number}: {failure.message}"
                for failure in result.failed_pages[:8]
            ]
            warnings.append("변환하지 못한 페이지가 있습니다.\n" + "\n".join(lines))
        if warnings:
            self.done_warning_label.setText("참고  ·  " + "\n참고  ·  ".join(warnings))
            self.done_warning_label.setVisible(True)
        else:
            self.done_warning_label.setVisible(False)
        self.stack.setCurrentIndex(1)
        self._update_start_state()

    def _on_conversion_failed(self, message: str, detail: str) -> None:
        self._busy = False
        self.settings_panel.set_controls_enabled(True)
        self.file_card.setEnabled(True)
        self.start_button.setEnabled(True)
        self.start_button.setText("다시 시도")
        text = message
        if detail:
            text += f"\n\n기술 정보: {detail}"
        self.progress_panel.show_error(text)
        self._update_start_state()

    def _on_conversion_cancelled(self) -> None:
        self._busy = False
        self.settings_panel.set_controls_enabled(True)
        self.file_card.setEnabled(True)
        self.start_button.setEnabled(True)
        self.start_button.setText("변환 시작")
        self.progress_panel.show_cancelled()
        self._update_start_state()

    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        if self._closing_after_cancel:
            self._closing_after_cancel = False
            self._settings.setValue("geometry", self.saveGeometry())
            self.close()

    # ------------------------------------------------------------------ result
    def _open_output_folder(self) -> None:
        if not self._result:
            return
        folder = self._result.output_path.parent
        if not folder.exists():
            self._show_error_banner("저장 폴더를 찾을 수 없습니다.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _new_conversion(self) -> None:
        if self._busy:
            return
        self._pdf_path = None
        self._password = None
        self._info = None
        self._analysis = None
        self._result = None
        self.file_card.setVisible(False)
        self.drop_zone.set_loaded(False)
        self.settings_panel.set_page_count(0)
        self.settings_panel.set_output_path("")
        self.warning_label.setVisible(False)
        self.error_label.setVisible(False)
        self.progress_panel.reset()
        self.start_button.setText("변환 시작")
        self.stack.setCurrentIndex(0)
        self._update_start_state()

    def _update_start_state(self) -> None:
        if self._busy:
            return
        self.start_button.setEnabled(self._pdf_path is not None)

    def _show_error_banner(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        QTimer.singleShot(
            0, lambda: self.convert_scroll.ensureWidgetVisible(self.error_label, 0, 40)
        )

    def _clear_error_banner(self) -> None:
        if self.error_label.isVisible():
            self.error_label.setVisible(False)
            self.error_label.setText("")

    # ------------------------------------------------------------------- help
    def _show_help_menu(self) -> None:
        self._help_menu.exec(
            self.menu_button.mapToGlobal(QPoint(0, self.menu_button.height() + 4))
        )

    def _show_help(self) -> None:
        QMessageBox.information(
            self,
            "사용 방법",
            "1. PDF 파일을 끌어다 놓거나 'PDF 파일 선택'을 누릅니다.\n"
            "2. 변환 모드, 슬라이드 비율, 해상도, 페이지 범위를 선택합니다.\n"
            "3. 저장 위치를 확인한 뒤 '변환 시작'을 누릅니다.\n"
            "4. 완료되면 '저장 위치 열기'로 결과를 확인합니다.\n\n"
            "원본 보존 모드는 PDF 모양을 그대로 유지하고, "
            "편집 가능 모드는 텍스트와 이미지를 개별 객체로 만듭니다.",
        )

    def _show_limits(self) -> None:
        QMessageBox.information(
            self,
            "지원 범위와 한계",
            "• 원본 보존 모드: 화면은 원본과 거의 같지만 텍스트를 직접 편집할 수 없습니다.\n"
            "• 편집 가능 모드: 텍스트, 이미지, 단순 사각형·선을 변환합니다. "
            "복잡한 도형, 그라데이션, 투명도, 클리핑은 원본과 다르거나 누락될 수 있습니다.\n"
            "• 글꼴이 대상 PC에 없으면 PowerPoint가 다른 글꼴로 대체합니다.\n"
            "• 스캔 문서는 이미지로 처리되며 텍스트 편집이 어렵습니다.\n"
            "• 페이지마다 크기가 다른 PDF는 첫 페이지 비율을 기준으로 배치됩니다.\n"
            "• 암호가 설정된 PDF도 암호를 입력하면 변환할 수 있습니다.\n\n"
            "원본 PDF는 절대 수정하거나 삭제하지 않습니다.",
        )

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "프로그램 정보",
            f"<b>{APP_NAME}</b> v{__version__}<br><br>"
            "PDF 문서를 PowerPoint 프레젠테이션으로 변환하는 데스크톱 도구입니다.<br><br>"
            "PySide6 · PyMuPDF · python-pptx · Pillow<br><br>"
            "PDF의 모든 요소를 완벽하게 편집 가능하게 변환하는 것은 기술적으로 "
            "불가능하므로, 원본 보존 모드를 기본으로 제공합니다.",
        )
