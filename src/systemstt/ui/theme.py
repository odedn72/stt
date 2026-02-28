"""
Design tokens and QSS generation for SystemSTT.

Single source of truth for all colors, typography, and spacing.
The DesignTokens dataclass mirrors the design spec (section 2)
and the UI spec (section 2.1).

Usage:
    from systemstt.ui.theme import TOKENS, generate_qss

    app.setStyleSheet(generate_qss())
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DesignTokens:
    """All design tokens from the design spec, section 2.

    These are the single source of truth for colors, sizes, and typography.
    """

    # Colors
    bg_solid: str = "#1A1A2E"
    bg_translucent: str = "rgba(26, 26, 46, 178)"  # 70% opacity
    bg_elevated: str = "#252540"
    bg_hover: str = "#2E2E4A"
    bg_active: str = "#3A3A5C"
    text_primary: str = "#F0F0F5"
    text_secondary: str = "#9999B0"
    text_disabled: str = "#55556A"
    accent: str = "#8B5CF6"
    accent_hover: str = "#7C4FE0"
    accent_glow: str = "rgba(139, 92, 246, 102)"  # 40% opacity
    error: str = "#EF4444"
    error_bg: str = "rgba(239, 68, 68, 38)"  # 15% opacity
    warning: str = "#F59E0B"
    success: str = "#10B981"
    border: str = "#2E2E4A"

    # Typography sizes (px)
    text_xs: int = 10
    text_sm: int = 12
    text_base: int = 13
    text_md: int = 14
    text_lg: int = 16
    text_xl: int = 20

    # Font families
    font_family: str = "-apple-system, 'Helvetica Neue', sans-serif"
    font_family_mono: str = "'SF Mono', Menlo, monospace"

    # Backdrop blur
    blur_radius: int = 20

    # Shared dimensions
    border_radius_sm: int = 6
    border_radius_md: int = 10
    border_radius_lg: int = 12
    border_radius_pill: int = 18

    # Widget dimensions
    toggle_width: int = 40
    toggle_height: int = 22
    button_height: int = 28
    dropdown_height: int = 28
    setting_row_height: int = 36
    tab_height: int = 36
    dropdown_menu_width: int = 240
    settings_width: int = 480
    settings_height: int = 420
    pill_min_width: int = 200
    pill_max_width: int = 360
    pill_collapsed_height: int = 36

    # Animation durations (ms)
    animation_fast: int = 150
    animation_normal: int = 200
    animation_pulse: int = 1500


TOKENS = DesignTokens()


def generate_qss(tokens: DesignTokens | None = None) -> str:
    """Generate the complete Qt Style Sheet from design tokens.

    Returns a QSS string that should be applied to the QApplication.
    All design token values are embedded into the stylesheet so that
    widgets automatically pick up the correct colors, fonts, and sizes.

    Args:
        tokens: Optional DesignTokens instance. Uses TOKENS if not provided.

    Returns:
        A QSS stylesheet string.
    """
    t = tokens if tokens is not None else TOKENS

    return f"""
/* ============================================================
   SystemSTT Global Stylesheet — generated from DesignTokens
   ============================================================ */

/* --- Base widget defaults --- */
QWidget {{
    background-color: {t.bg_solid};
    color: {t.text_primary};
    font-family: {t.font_family};
    font-size: {t.text_base}px;
}}

QLabel {{
    background-color: transparent;
    color: {t.text_primary};
}}

QLabel[class="secondary"] {{
    color: {t.text_secondary};
    font-size: {t.text_sm}px;
}}

QLabel[class="disabled"] {{
    color: {t.text_disabled};
}}

QLabel[class="section-header"] {{
    color: {t.text_secondary};
    font-size: {t.text_xs}px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

QLabel[class="error"] {{
    color: {t.error};
    background-color: {t.error_bg};
    border-radius: {t.border_radius_sm}px;
    padding: 4px 8px;
}}

QLabel[class="warning"] {{
    color: {t.warning};
}}

QLabel[class="success"] {{
    color: {t.success};
}}

/* --- Push buttons --- */
QPushButton {{
    background-color: {t.accent};
    color: #FFFFFF;
    border: none;
    border-radius: {t.border_radius_sm}px;
    height: {t.button_height}px;
    padding: 0 12px;
    font-size: {t.text_base}px;
}}

QPushButton:hover {{
    background-color: {t.accent_hover};
}}

QPushButton:pressed {{
    background-color: {t.bg_active};
}}

QPushButton:disabled {{
    background-color: {t.bg_active};
    color: {t.text_disabled};
}}

QPushButton[class="secondary"] {{
    background-color: {t.bg_elevated};
    color: {t.text_primary};
    border: 1px solid {t.border};
}}

QPushButton[class="secondary"]:hover {{
    background-color: {t.bg_hover};
}}

/* --- Combo box (dropdowns) --- */
QComboBox {{
    background-color: {t.bg_elevated};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: {t.border_radius_sm}px;
    height: {t.dropdown_height}px;
    padding: 0 8px;
    font-size: {t.text_base}px;
}}

QComboBox:hover {{
    background-color: {t.bg_hover};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {t.bg_elevated};
    color: {t.text_primary};
    border: 1px solid {t.border};
    selection-background-color: {t.bg_hover};
    selection-color: {t.text_primary};
}}

/* --- Line edits --- */
QLineEdit {{
    background-color: {t.bg_elevated};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: {t.border_radius_sm}px;
    height: {t.dropdown_height}px;
    padding: 0 8px;
    font-size: {t.text_base}px;
}}

QLineEdit:focus {{
    border-color: {t.accent};
}}

QLineEdit:disabled {{
    color: {t.text_disabled};
}}

/* --- Radio buttons --- */
QRadioButton {{
    color: {t.text_primary};
    font-size: {t.text_base}px;
    spacing: 8px;
    background-color: transparent;
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid {t.text_secondary};
    background-color: transparent;
}}

QRadioButton::indicator:checked {{
    border-color: {t.accent};
    background-color: {t.accent};
}}

/* --- Scroll bar --- */
QScrollBar:vertical {{
    background-color: {t.bg_solid};
    width: 8px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {t.bg_active};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {t.text_disabled};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* --- Tab bar (for settings window) --- */
QTabBar::tab {{
    background-color: transparent;
    color: {t.text_secondary};
    font-size: {t.text_md}px;
    font-weight: 500;
    height: {t.tab_height}px;
    padding: 0 16px;
    border: none;
    border-bottom: 2px solid transparent;
}}

QTabBar::tab:hover {{
    color: {t.text_primary};
    background-color: {t.bg_hover};
}}

QTabBar::tab:selected {{
    color: {t.accent};
    background-color: {t.bg_elevated};
    border-bottom-color: {t.accent};
}}

QTabWidget::pane {{
    background-color: {t.bg_elevated};
    border: none;
}}

/* --- Table widget (commands tab) --- */
QTableWidget {{
    background-color: {t.bg_elevated};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: {t.border_radius_sm}px;
    gridline-color: {t.border};
    font-size: {t.text_base}px;
}}

QTableWidget::item {{
    padding: 4px 8px;
}}

QTableWidget::item:selected {{
    background-color: {t.bg_hover};
    color: {t.text_primary};
}}

QHeaderView::section {{
    background-color: {t.bg_solid};
    color: {t.text_secondary};
    border: none;
    border-bottom: 1px solid {t.border};
    padding: 4px 8px;
    font-size: {t.text_sm}px;
    font-weight: 600;
}}

/* --- Progress bar (model download) --- */
QProgressBar {{
    background-color: {t.bg_elevated};
    border: 1px solid {t.border};
    border-radius: {t.border_radius_sm}px;
    height: 8px;
    text-align: center;
    font-size: {t.text_xs}px;
    color: {t.text_secondary};
}}

QProgressBar::chunk {{
    background-color: {t.accent};
    border-radius: {t.border_radius_sm}px;
}}

/* --- Tooltips --- */
QToolTip {{
    background-color: {t.bg_elevated};
    color: {t.text_primary};
    border: 1px solid {t.border};
    padding: 4px 8px;
    font-size: {t.text_sm}px;
}}
"""
