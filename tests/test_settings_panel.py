"""UI option-widget tests (headless Qt)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.conversion_options import (
    ConversionMode,
    ConversionOptions,
    ImageQuality,
    SlideRatio,
)
from app.ui.main_window import MainWindow
from app.ui.settings_panel import SettingsPanel


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_settings_returns_real_enums(qapp):
    panel = SettingsPanel()
    panel.ratio_combo.setCurrentIndex(1)
    panel.quality_combo.setCurrentIndex(1)

    assert panel.selected_ratio() is SlideRatio.WIDESCREEN
    assert panel.selected_quality() is ImageQuality.HIGH

    panel.editable_card.radio.setChecked(True)
    assert panel.selected_mode() is ConversionMode.EDITABLE

    options = ConversionOptions(
        output_path=Path("example"),
        mode=panel.selected_mode(),
        ratio=panel.selected_ratio(),
        quality=panel.selected_quality(),
    )
    assert options.output_path.suffix == ".pptx"
    assert options.dpi == 300
    panel.deleteLater()


def test_settings_page_range_and_page_count(qapp):
    panel = SettingsPanel()
    panel.set_page_count(12)
    assert "12페이지" in panel.all_pages_radio.text()
    assert panel.page_range_text() == ""

    panel.custom_pages_radio.setChecked(True)
    assert panel.page_range_edit.isEnabled()
    panel.page_range_edit.setText("1-3, 5")
    assert panel.page_range_text() == "1-3, 5"
    panel.deleteLater()


def test_settings_controls_can_be_disabled(qapp):
    panel = SettingsPanel()
    panel.set_controls_enabled(False)
    assert not panel.original_card.isEnabled()
    assert not panel.editable_card.isEnabled()
    assert not panel.ratio_combo.isEnabled()
    assert not panel.output_edit.isEnabled()
    panel.set_controls_enabled(True)
    assert panel.ratio_combo.isEnabled()
    panel.deleteLater()


def test_main_window_loads_pdf_and_sets_defaults(qapp, sample_pdf: Path):
    window = MainWindow()
    try:
        window._load_pdf(str(sample_pdf))
        assert window._info is not None
        assert window._info.page_count == 3
        assert window.start_button.isEnabled()
        assert window.settings_panel.output_path().suffix == ".pptx"
        assert window.settings_panel.output_path().stem == "sample"

        window._new_conversion()
        assert window._pdf_path is None
        assert not window.start_button.isEnabled()
    finally:
        window.close()
        window.deleteLater()
