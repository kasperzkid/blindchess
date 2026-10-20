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


def test_main_menu_grid_alignment(capsys):
    """Test that main menu grid renders with uniform column alignment."""
    import os
    import shutil
    from unittest.mock import patch
    from blindchess.config import AppConfig
    from blindchess.cli import interactive_main_menu

    config = AppConfig()

    # Test 3-column layout on wide terminal (cols=100)
    with patch("shutil.get_terminal_size", return_value=os.terminal_size((100, 30))):
        with patch("blindchess.terminal_ui.TerminalUI.prompt", side_effect=["q"]):
            interactive_main_menu(config, None, None)

    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if "[1]" in line or "[4]" in line or "[7]" in line or "[10]" in line]
    assert len(lines) == 4
    # Check that [2], [5], [8], [11] all start at the exact same character index in their respective lines
    idx2 = lines[0].index("[2]")
    idx5 = lines[1].index("[5]")
    idx8 = lines[2].index("[8]")
    idx11 = lines[3].index("[11]")
    assert idx2 == idx5 == idx8 == idx11

    # Check that [3], [6], [9], [12] all start at the exact same character index
    idx3 = lines[0].index("[3]")
    idx6 = lines[1].index("[6]")
    idx9 = lines[2].index("[9]")
    idx12 = lines[3].index("[12]")
    assert idx3 == idx6 == idx9 == idx12

