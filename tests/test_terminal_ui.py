"""Automated tests for redesigned TerminalUI and design system."""

import os
from blindchess.board_state import BoardState
from blindchess.terminal_ui import TerminalPalette, TerminalUI, visible_len


def test_visible_len():
    plain = "Hello World"
    assert visible_len(plain) == 11

    colored = "\033[1;36mHello World\033[0m"
    assert visible_len(colored) == 11


def test_palette_color_toggle():
    palette_enabled = TerminalPalette(enabled=True)
    assert "\033[" in palette_enabled.accent("Test")

    palette_disabled = TerminalPalette(enabled=False)
    assert palette_disabled.accent("Test") == "Test"
    assert palette_disabled.success("OK") == "OK"
    assert palette_disabled.error("Fail") == "Fail"


def test_panel_rendering_unicode():
    ui = TerminalUI(ascii_only=False, force_color=False)
    panel = ui.render_panel("Title", ["Line 1", "Line 2"], width=40)
    assert "Title" in panel
    assert "Line 1" in panel
    assert "Line 2" in panel
    assert "╭" in panel
    assert "╰" in panel


def test_panel_rendering_ascii():
    ui = TerminalUI(ascii_only=True, force_color=False)
    panel = ui.render_panel("Title", ["Line 1", "Line 2"], width=40)
    assert "Title" in panel
    assert "Line 1" in panel
    assert "+" in panel
    assert "-" in panel


def test_no_color_environment(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    ui = TerminalUI()
    assert ui.palette.enabled is False
    assert ui.palette.accent("Text") == "Text"


def test_table_rendering(capsys):
    ui = TerminalUI(ascii_only=True, force_color=False)
    ui.print_table(["Col A", "Col B"], [["Val 1", "Val 2"], ["Val 3", "Val 4"]])
    captured = capsys.readouterr().out
    assert "Col A" in captured
    assert "Col B" in captured
    assert "Val 1" in captured
    assert "Val 4" in captured


def test_board_rendering_card(capsys):
    ui = TerminalUI(ascii_only=True, force_color=False)
    state = BoardState()
    ui.print_board(state)
    captured = capsys.readouterr().out
    assert "Chessboard View" in captured
    assert "Turn: White" in captured
