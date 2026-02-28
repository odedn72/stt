# TDD: Written from spec 07-ui-layer.md
"""
Tests for theme.py — design tokens and QSS generation.

Verifies:
- DesignTokens has all expected fields with correct defaults
- generate_qss() produces valid QSS containing all design token values
- TOKENS singleton is accessible
"""

from __future__ import annotations

import pytest

from systemstt.ui.theme import DesignTokens, TOKENS, generate_qss


class TestDesignTokens:
    """Tests for the DesignTokens dataclass."""

    def test_tokens_is_frozen(self) -> None:
        with pytest.raises(AttributeError):
            TOKENS.accent = "#000000"  # type: ignore[misc]

    def test_bg_solid_default(self) -> None:
        assert TOKENS.bg_solid == "#1A1A2E"

    def test_accent_default(self) -> None:
        assert TOKENS.accent == "#8B5CF6"

    def test_accent_hover_default(self) -> None:
        assert TOKENS.accent_hover == "#7C4FE0"

    def test_error_default(self) -> None:
        assert TOKENS.error == "#EF4444"

    def test_warning_default(self) -> None:
        assert TOKENS.warning == "#F59E0B"

    def test_success_default(self) -> None:
        assert TOKENS.success == "#10B981"

    def test_text_primary_default(self) -> None:
        assert TOKENS.text_primary == "#F0F0F5"

    def test_text_secondary_default(self) -> None:
        assert TOKENS.text_secondary == "#9999B0"

    def test_text_sizes(self) -> None:
        assert TOKENS.text_xs == 10
        assert TOKENS.text_sm == 12
        assert TOKENS.text_base == 13
        assert TOKENS.text_md == 14
        assert TOKENS.text_lg == 16
        assert TOKENS.text_xl == 20

    def test_border_radius_values(self) -> None:
        assert TOKENS.border_radius_sm == 6
        assert TOKENS.border_radius_md == 10
        assert TOKENS.border_radius_lg == 12
        assert TOKENS.border_radius_pill == 18

    def test_widget_dimensions(self) -> None:
        assert TOKENS.settings_width == 480
        assert TOKENS.settings_height == 420
        assert TOKENS.dropdown_menu_width == 240
        assert TOKENS.pill_min_width == 200
        assert TOKENS.pill_max_width == 360
        assert TOKENS.pill_collapsed_height == 36

    def test_custom_tokens(self) -> None:
        custom = DesignTokens(accent="#FF0000", text_xs=8)
        assert custom.accent == "#FF0000"
        assert custom.text_xs == 8
        # Other values should still be defaults
        assert custom.bg_solid == "#1A1A2E"


class TestGenerateQSS:
    """Tests for QSS generation."""

    def test_generates_non_empty_string(self) -> None:
        qss = generate_qss()
        assert isinstance(qss, str)
        assert len(qss) > 100

    def test_contains_bg_solid_color(self) -> None:
        qss = generate_qss()
        assert TOKENS.bg_solid in qss

    def test_contains_accent_color(self) -> None:
        qss = generate_qss()
        assert TOKENS.accent in qss

    def test_contains_text_primary_color(self) -> None:
        qss = generate_qss()
        assert TOKENS.text_primary in qss

    def test_contains_error_color(self) -> None:
        qss = generate_qss()
        assert TOKENS.error in qss

    def test_contains_border_radius(self) -> None:
        qss = generate_qss()
        assert str(TOKENS.border_radius_sm) in qss

    def test_custom_tokens_used(self) -> None:
        custom = DesignTokens(accent="#AABBCC")
        qss = generate_qss(custom)
        assert "#AABBCC" in qss
        # Default accent should NOT be in the generated QSS
        assert "#8B5CF6" not in qss

    def test_contains_widget_selectors(self) -> None:
        qss = generate_qss()
        assert "QWidget" in qss
        assert "QPushButton" in qss
        assert "QComboBox" in qss
        assert "QLabel" in qss
        assert "QRadioButton" in qss
