"""Conversion option widgets (mode, ratio, quality, range, destination)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from app.models.conversion_options import ImageQuality, SlideRatio, ConversionMode


class ModeCard(QFrame):
    """Selectable card containing a radio button and a description."""

    clicked = Signal(object)

    def __init__(self, mode: ConversionMode, title: str, description: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setObjectName("modeCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 10, 10)
        layout.setSpacing(9)

        self.radio = QRadioButton()
        self.radio.setObjectName(f"modeRadio_{mode.value}")
        layout.addWidget(self.radio, 0, Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 700; font-size: 13px; background: transparent;")
        description_label = QLabel(description)
        description_label.setObjectName("muted")
        description_label.setWordWrap(True)
        description_label.setStyleSheet("background: transparent;")
        text_layout.addWidget(title_label)
        text_layout.addWidget(description_label)
        layout.addLayout(text_layout, 1)

        self.radio.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self.setProperty("selected", checked)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.radio.setChecked(True)
            self.clicked.emit(self.mode)
        super().mousePressEvent(event)


class SettingsPanel(QFrame):
    """All conversion options in one card."""

    browse_output_requested = Signal()
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsCard")
        self._page_count = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(11)

        title = QLabel("변환 설정")
        title.setObjectName("sectionTitle")
        root.addWidget(title)

        # --- Conversion mode -------------------------------------------------
        mode_label = QLabel("변환 모드")
        mode_label.setObjectName("fieldLabel")
        root.addWidget(mode_label)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        self.original_card = ModeCard(
            ConversionMode.ORIGINAL,
            "원본 보존 (권장)",
            "PDF 페이지를 고해상도 이미지로 넣어 디자인과 글꼴을 그대로 유지합니다.",
        )
        self.editable_card = ModeCard(
            ConversionMode.EDITABLE,
            "편집 가능",
            "텍스트·이미지·단순 도형을 개별 객체로 재구성합니다. 복잡한 요소는 이미지로 대체됩니다.",
        )
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self.original_card.radio)
        self._mode_group.addButton(self.editable_card.radio)
        self.original_card.radio.setChecked(True)
        mode_row.addWidget(self.original_card, 1)
        mode_row.addWidget(self.editable_card, 1)
        root.addLayout(mode_row)

        # --- Slide / quality / range ----------------------------------------
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)

        ratio_label = QLabel("슬라이드 비율")
        ratio_label.setObjectName("fieldLabel")
        quality_label = QLabel("이미지 해상도")
        quality_label.setObjectName("fieldLabel")
        grid.addWidget(ratio_label, 0, 0)
        grid.addWidget(quality_label, 0, 1)

        self.ratio_combo = QComboBox()
        for ratio in SlideRatio:
            self.ratio_combo.addItem(ratio.label, ratio.value)
        self.quality_combo = QComboBox()
        for quality in ImageQuality:
            self.quality_combo.addItem(quality.label, quality.value)
        grid.addWidget(self.ratio_combo, 1, 0)
        grid.addWidget(self.quality_combo, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        root.addLayout(grid)

        range_label = QLabel("페이지 범위")
        range_label.setObjectName("fieldLabel")
        root.addWidget(range_label)

        range_row = QHBoxLayout()
        range_row.setSpacing(10)
        self.all_pages_radio = QRadioButton("전체 페이지")
        self.all_pages_radio.setChecked(True)
        self.custom_pages_radio = QRadioButton("지정")
        self.page_range_edit = QLineEdit()
        self.page_range_edit.setPlaceholderText("예: 1-3, 5, 8")
        self.page_range_edit.setEnabled(False)
        self.page_range_edit.setClearButtonEnabled(True)
        self.page_range_edit.setMaximumWidth(220)
        range_row.addWidget(self.all_pages_radio)
        range_row.addWidget(self.custom_pages_radio)
        range_row.addWidget(self.page_range_edit, 1)
        range_row.addStretch(1)
        root.addLayout(range_row)

        hint = QLabel(
            "원본 비율 유지를 권장합니다. 비율을 바꾸면 페이지 주변에 여백이 생길 수 있으며, "
            "내용이 잘리지는 않습니다."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        self.hint_label = hint
        root.addWidget(hint)

        # --- Output ----------------------------------------------------------
        output_label = QLabel("저장 위치")
        output_label.setObjectName("fieldLabel")
        root.addWidget(output_label)
        output_row = QHBoxLayout()
        output_row.setSpacing(8)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("저장할 PPTX 파일 경로")
        self.browse_button = QPushButton("찾아보기")
        self.browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.browse_button)
        root.addLayout(output_row)

        # --- Signals ---------------------------------------------------------
        self.original_card.radio.toggled.connect(self._on_mode_changed)
        self.editable_card.radio.toggled.connect(self._on_mode_changed)
        self.original_card.clicked.connect(self._select_mode)
        self.editable_card.clicked.connect(self._select_mode)
        self.ratio_combo.currentIndexChanged.connect(self._on_ratio_changed)
        self.quality_combo.currentIndexChanged.connect(lambda *_: self.settings_changed.emit())
        self.all_pages_radio.toggled.connect(self._on_range_mode_changed)
        self.browse_button.clicked.connect(self.browse_output_requested.emit)
        self.output_edit.textChanged.connect(lambda *_: self.settings_changed.emit())
        self._on_mode_changed()
        self._on_ratio_changed()

    # -- public API ------------------------------------------------------------
    def selected_mode(self) -> ConversionMode:
        return ConversionMode.EDITABLE if self.editable_card.radio.isChecked() else ConversionMode.ORIGINAL

    def selected_ratio(self) -> SlideRatio:
        data = self.ratio_combo.currentData()
        return data if isinstance(data, SlideRatio) else SlideRatio(data)

    def selected_quality(self) -> ImageQuality:
        data = self.quality_combo.currentData()
        return data if isinstance(data, ImageQuality) else ImageQuality(data)

    def page_range_text(self) -> str:
        if self.all_pages_radio.isChecked():
            return ""
        return self.page_range_edit.text().strip()

    def output_path(self) -> Path:
        return Path(self.output_edit.text().strip())

    def output_text(self) -> str:
        return self.output_edit.text().strip()

    def set_output_path(self, path: Path | str) -> None:
        self.output_edit.setText(str(path))

    def set_page_count(self, page_count: int) -> None:
        self._page_count = max(0, page_count)
        self.all_pages_radio.setText(
            f"전체 페이지 ({self._page_count}페이지)" if self._page_count else "전체 페이지"
        )
        self.all_pages_radio.setChecked(True)

    def set_controls_enabled(self, enabled: bool) -> None:
        self.original_card.setEnabled(enabled)
        self.editable_card.setEnabled(enabled)
        self.ratio_combo.setEnabled(enabled)
        self.quality_combo.setEnabled(enabled)
        self.all_pages_radio.setEnabled(enabled)
        self.custom_pages_radio.setEnabled(enabled)
        self.page_range_edit.setEnabled(enabled and self.custom_pages_radio.isChecked())
        self.output_edit.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)

    def focus_page_range(self) -> None:
        self.custom_pages_radio.setChecked(True)
        self.page_range_edit.setFocus()
        self.page_range_edit.selectAll()

    # -- slots ----------------------------------------------------------------
    def _select_mode(self, mode) -> None:
        if mode is ConversionMode.EDITABLE:
            self.editable_card.radio.setChecked(True)
        else:
            self.original_card.radio.setChecked(True)

    def _on_mode_changed(self, *args) -> None:
        self._refresh_hint()
        self.settings_changed.emit()

    def _refresh_hint(self) -> None:
        if self.selected_mode() is ConversionMode.EDITABLE:
            self.hint_label.setText(
                "편집 가능 모드는 텍스트·이미지·단순 도형을 개별 객체로 만듭니다. "
                "서체, 복잡한 도형, 투명도는 원본과 다를 수 있습니다."
            )
        elif self.selected_ratio() is not SlideRatio.ORIGINAL:
            self.hint_label.setText(
                "선택한 비율에 맞춰 페이지 전체가 들어가며, 남는 공간은 여백으로 표시됩니다. "
                "내용이 잘리지는 않습니다."
            )
        else:
            self.hint_label.setText(
                "원본 비율 유지를 권장합니다. 비율을 바꾸면 페이지 주변에 여백이 생길 수 있으며, "
                "내용이 잘리지는 않습니다."
            )

    def _on_ratio_changed(self, *args) -> None:
        self._refresh_hint()
        self.settings_changed.emit()

    def _on_range_mode_changed(self, *args) -> None:
        custom = self.custom_pages_radio.isChecked()
        self.page_range_edit.setEnabled(custom)
        if custom:
            self.page_range_edit.setFocus()
        self.settings_changed.emit()
