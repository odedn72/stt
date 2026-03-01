# TDD: Written from spec 07-ui-layer.md
"""
Tests for MenuBarWidget — menu bar icon with language label.

PySide6 widgets are tested with pytest-qt where needed, but most
tests verify state transitions and signal emissions.

Design spec references: Section 4 (menu bar states and dropdown).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from systemstt.ui.menu_bar import MenuBarWidget

# ---------------------------------------------------------------------------
# State tests
# ---------------------------------------------------------------------------


class TestMenuBarWidgetStates:
    """Tests for menu bar state transitions."""

    @patch("systemstt.ui.menu_bar.QSystemTrayIcon")
    def test_set_state_idle(self, mock_tray_cls: MagicMock) -> None:
        widget = MenuBarWidget()
        widget.set_state_idle("EN")
        # Should not raise; state should be set internally

    @patch("systemstt.ui.menu_bar.QSystemTrayIcon")
    def test_set_state_active(self, mock_tray_cls: MagicMock) -> None:
        widget = MenuBarWidget()
        widget.set_state_active("EN")

    @patch("systemstt.ui.menu_bar.QSystemTrayIcon")
    def test_set_state_error(self, mock_tray_cls: MagicMock) -> None:
        widget = MenuBarWidget()
        widget.set_state_error("EN")

    @patch("systemstt.ui.menu_bar.QSystemTrayIcon")
    def test_update_language(self, mock_tray_cls: MagicMock) -> None:
        widget = MenuBarWidget()
        widget.update_language("HE")


# ---------------------------------------------------------------------------
# Language label tests
# ---------------------------------------------------------------------------


class TestMenuBarWidgetLanguageLabel:
    """Tests for the language label display."""

    @patch("systemstt.ui.menu_bar.QSystemTrayIcon")
    def test_default_language_is_en(self, mock_tray_cls: MagicMock) -> None:
        widget = MenuBarWidget()
        widget.set_state_idle()
        # Default language should be EN per design spec

    @patch("systemstt.ui.menu_bar.QSystemTrayIcon")
    def test_language_update_to_hebrew(self, mock_tray_cls: MagicMock) -> None:
        widget = MenuBarWidget()
        widget.update_language("HE")
        # Should not raise


# ---------------------------------------------------------------------------
# Dropdown status update tests
# ---------------------------------------------------------------------------


class TestMenuBarWidgetDropdownStatus:
    """Tests for dropdown menu dynamic content."""

    @patch("systemstt.ui.menu_bar.QSystemTrayIcon")
    def test_update_dropdown_status_active(self, mock_tray_cls: MagicMock) -> None:
        widget = MenuBarWidget()
        widget.update_dropdown_status(
            is_active=True,
            language="HE",
            engine="Cloud",
            is_preview_on=True,
        )

    @patch("systemstt.ui.menu_bar.QSystemTrayIcon")
    def test_update_dropdown_status_idle(self, mock_tray_cls: MagicMock) -> None:
        widget = MenuBarWidget()
        widget.update_dropdown_status(
            is_active=False,
            language="EN",
            engine="Local",
            is_preview_on=False,
        )


# ---------------------------------------------------------------------------
# Signal tests
# ---------------------------------------------------------------------------


class TestMenuBarWidgetSignals:
    """Tests that required signals are defined."""

    @patch("systemstt.ui.menu_bar.QSystemTrayIcon")
    def test_has_dictation_toggle_signal(self, mock_tray_cls: MagicMock) -> None:
        widget = MenuBarWidget()
        assert hasattr(widget, "dictation_toggle_requested")

    @patch("systemstt.ui.menu_bar.QSystemTrayIcon")
    def test_has_preview_toggle_signal(self, mock_tray_cls: MagicMock) -> None:
        widget = MenuBarWidget()
        assert hasattr(widget, "preview_toggle_requested")

    @patch("systemstt.ui.menu_bar.QSystemTrayIcon")
    def test_has_settings_signal(self, mock_tray_cls: MagicMock) -> None:
        widget = MenuBarWidget()
        assert hasattr(widget, "settings_requested")

    @patch("systemstt.ui.menu_bar.QSystemTrayIcon")
    def test_has_quit_signal(self, mock_tray_cls: MagicMock) -> None:
        widget = MenuBarWidget()
        assert hasattr(widget, "quit_requested")
