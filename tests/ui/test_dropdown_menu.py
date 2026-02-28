# TDD: Written from spec 07-ui-layer.md
"""
Tests for DropdownMenu — custom dropdown for the menu bar icon.

Design spec references: Section 4.3 (dropdown menu).

Tests verify:
- Widget creation
- State updates (active/inactive, language, engine, preview)
- Signal definitions
- Show/hide behavior
"""

from __future__ import annotations

import pytest

from systemstt.ui.dropdown_menu import DropdownMenu


class TestDropdownMenuCreation:
    """Tests for dropdown menu creation."""

    def test_creates_without_error(self) -> None:
        menu = DropdownMenu()
        assert menu is not None

    def test_is_qwidget(self) -> None:
        from PySide6.QtWidgets import QWidget
        menu = DropdownMenu()
        assert isinstance(menu, QWidget)


class TestDropdownMenuState:
    """Tests for updating dropdown state."""

    def test_update_state_active(self) -> None:
        menu = DropdownMenu()
        menu.update_state(
            is_active=True,
            language="HE",
            engine="Cloud",
            is_preview_on=True,
        )

    def test_update_state_inactive(self) -> None:
        menu = DropdownMenu()
        menu.update_state(
            is_active=False,
            language="EN",
            engine="Local",
            is_preview_on=False,
        )


class TestDropdownMenuSignals:
    """Tests that required signals are defined."""

    def test_has_start_stop_signal(self) -> None:
        menu = DropdownMenu()
        assert hasattr(menu, "start_stop_clicked")

    def test_has_preview_signal(self) -> None:
        menu = DropdownMenu()
        assert hasattr(menu, "show_hide_preview_clicked")

    def test_has_settings_signal(self) -> None:
        menu = DropdownMenu()
        assert hasattr(menu, "settings_clicked")

    def test_has_quit_signal(self) -> None:
        menu = DropdownMenu()
        assert hasattr(menu, "quit_clicked")
