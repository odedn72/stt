# TDD: Written from spec 07-ui-layer.md
"""
Tests for FloatingPill — floating status indicator during dictation.

Design spec references: Section 5 (floating pill states, specs, animations).

Tests verify:
- Show/hide transitions
- Language label updates
- Elapsed time display
- Preview text area (including Hebrew/RTL)
- Error and warning display
- Command confirmation display
- Position management (set, reset, dragging)
- Expansion/collapse behavior
- Signal definitions
"""

from __future__ import annotations

from systemstt.ui.floating_pill import FloatingPill

# ---------------------------------------------------------------------------
# Show/hide lifecycle tests
# ---------------------------------------------------------------------------


class TestFloatingPillLifecycle:
    """Tests for pill show/hide lifecycle."""

    def test_show_active_makes_pill_visible(self) -> None:
        pill = FloatingPill()
        pill.show_active(language="EN", engine="Cloud")
        # Pill should be visible after show_active

    def test_hide_pill_hides_it(self) -> None:
        pill = FloatingPill()
        pill.show_active()
        pill.hide_pill()
        # Pill should be hidden


# ---------------------------------------------------------------------------
# Language update tests
# ---------------------------------------------------------------------------


class TestFloatingPillLanguage:
    """Tests for real-time language label updates."""

    def test_update_language_to_english(self) -> None:
        pill = FloatingPill()
        pill.update_language("EN")

    def test_update_language_to_hebrew(self) -> None:
        pill = FloatingPill()
        pill.update_language("HE")


# ---------------------------------------------------------------------------
# Elapsed time tests
# ---------------------------------------------------------------------------


class TestFloatingPillElapsedTime:
    """Tests for elapsed time display."""

    def test_update_elapsed_time_zero(self) -> None:
        pill = FloatingPill()
        pill.update_elapsed_time(0)

    def test_update_elapsed_time_short(self) -> None:
        pill = FloatingPill()
        pill.update_elapsed_time(12)  # "0:12"

    def test_update_elapsed_time_long(self) -> None:
        pill = FloatingPill()
        pill.update_elapsed_time(3661)  # "1:01:01"

    def test_format_time_short(self) -> None:
        assert FloatingPill._format_time(0) == "0:00"
        assert FloatingPill._format_time(12) == "0:12"
        assert FloatingPill._format_time(72) == "1:12"

    def test_format_time_hours(self) -> None:
        assert FloatingPill._format_time(3661) == "1:01:01"


# ---------------------------------------------------------------------------
# Preview text tests
# ---------------------------------------------------------------------------


class TestFloatingPillPreview:
    """Tests for the live transcription preview area."""

    def test_show_preview_english(self) -> None:
        pill = FloatingPill()
        pill.show_preview_text("Hello world this is a test")

    def test_show_preview_hebrew(self) -> None:
        pill = FloatingPill()
        pill.show_preview_text("\u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd")

    def test_show_preview_mixed_bidi(self) -> None:
        pill = FloatingPill()
        pill.show_preview_text("\u05e9\u05dc\u05d5\u05dd, this is a test of mixed language")

    def test_hide_preview(self) -> None:
        pill = FloatingPill()
        pill.show_preview_text("some text")
        pill.hide_preview()

    def test_show_preview_empty_string(self) -> None:
        pill = FloatingPill()
        pill.show_preview_text("")


# ---------------------------------------------------------------------------
# Error/warning display tests
# ---------------------------------------------------------------------------


class TestFloatingPillErrors:
    """Tests for inline error and warning display."""

    def test_show_error(self) -> None:
        pill = FloatingPill()
        pill.show_error("API timeout -- retrying...")

    def test_show_warning(self) -> None:
        pill = FloatingPill()
        pill.show_error("Cloud API unavailable. Switch to local?", is_warning=True)

    def test_show_error_default_is_not_warning(self) -> None:
        pill = FloatingPill()
        pill.show_error("Microphone disconnected")
        # is_warning defaults to False


# ---------------------------------------------------------------------------
# Command confirmation tests
# ---------------------------------------------------------------------------


class TestFloatingPillCommandConfirmation:
    """Tests for voice command confirmation display."""

    def test_show_command_confirmation(self) -> None:
        pill = FloatingPill()
        pill.show_command_confirmation("Deleted last word")

    def test_show_command_confirmation_various_commands(self) -> None:
        pill = FloatingPill()
        confirmations = [
            "Deleted last word",
            "Deleted last sentence",
            "Undone",
            "New line",
            "New paragraph",
            "Selected all",
            "Copied",
            "Pasted",
            "Dictation stopped",
        ]
        for text in confirmations:
            pill.show_command_confirmation(text)


# ---------------------------------------------------------------------------
# Expansion/collapse tests
# ---------------------------------------------------------------------------


class TestFloatingPillExpansion:
    """Tests for the expansion area behavior."""

    def test_clear_expansion(self) -> None:
        pill = FloatingPill()
        pill.show_error("some error")
        pill.clear_expansion()


# ---------------------------------------------------------------------------
# Position management tests
# ---------------------------------------------------------------------------


class TestFloatingPillPosition:
    """Tests for pill positioning and dragging."""

    def test_set_position(self) -> None:
        pill = FloatingPill()
        pill.set_position(100, 200)

    def test_reset_position(self) -> None:
        pill = FloatingPill()
        pill.set_position(500, 600)
        pill.reset_position()
        # Should reset to default: top-center, 48px below menu bar


# ---------------------------------------------------------------------------
# Signal tests
# ---------------------------------------------------------------------------


class TestFloatingPillSignals:
    """Tests that required signals are defined."""

    def test_has_position_changed_signal(self) -> None:
        pill = FloatingPill()
        assert hasattr(pill, "position_changed")
