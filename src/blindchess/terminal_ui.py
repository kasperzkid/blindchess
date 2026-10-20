"""Production-grade, responsive terminal user interface and design system for BlindChess."""

from dataclasses import dataclass
import os
import shutil
import sys
from typing import Any, Dict, List, Optional, Tuple

from blindchess.board_state import BoardState


@dataclass
class TerminalPalette:
    """Color and styling token definitions with zero external dependencies."""

    enabled: bool = True

    # ANSI escape codes
    RESET: str = "\033[0m"
    BOLD: str = "\033[1m"
    DIM: str = "\033[2m"
    ITALIC: str = "\033[3m"
    UNDERLINE: str = "\033[4m"

    # Semantic foregrounds
    FG_ACCENT: str = "\033[36m"         # Cyan
    FG_ACCENT_BOLD: str = "\033[1;36m"   # Bold Cyan
    FG_SUCCESS: str = "\033[32m"        # Green
    FG_SUCCESS_BOLD: str = "\033[1;32m"  # Bold Green
    FG_WARNING: str = "\033[33m"        # Amber / Yellow
    FG_WARNING_BOLD: str = "\033[1;33m"  # Bold Yellow
    FG_ERROR: str = "\033[31m"          # Red
    FG_ERROR_BOLD: str = "\033[1;31m"    # Bold Red
    FG_MUTED: str = "\033[38;5;244m"    # Mid Gray (fallback to \033[90m if 8-color)
    FG_MUTED_FALLBACK: str = "\033[90m" # Bright Black / Gray
    FG_HIGHLIGHT: str = "\033[1;37m"    # Bright Bold White
    FG_LABEL: str = "\033[38;5;250m"    # Light Gray

    # Background pills
    BG_DARK: str = "\033[48;5;236m"
    BG_ACCENT: str = "\033[48;5;24m"

    def _wrap(self, code: str, text: str) -> str:
        if not self.enabled or not text:
            return text
        return f"{code}{text}{self.RESET}"

    def accent(self, text: str) -> str:
        return self._wrap(self.FG_ACCENT, text)

    def accent_bold(self, text: str) -> str:
        return self._wrap(self.FG_ACCENT_BOLD, text)

    def success(self, text: str) -> str:
        return self._wrap(self.FG_SUCCESS, text)

    def success_bold(self, text: str) -> str:
        return self._wrap(self.FG_SUCCESS_BOLD, text)

    def warning(self, text: str) -> str:
        return self._wrap(self.FG_WARNING, text)

    def warning_bold(self, text: str) -> str:
        return self._wrap(self.FG_WARNING_BOLD, text)

    def error(self, text: str) -> str:
        return self._wrap(self.FG_ERROR, text)

    def error_bold(self, text: str) -> str:
        return self._wrap(self.FG_ERROR_BOLD, text)

    def muted(self, text: str) -> str:
        return self._wrap(self.FG_MUTED_FALLBACK, text)

    def highlight(self, text: str) -> str:
        return self._wrap(self.FG_HIGHLIGHT, text)

    def dim(self, text: str) -> str:
        return self._wrap(self.DIM, text)

    def bold(self, text: str) -> str:
        return self._wrap(self.BOLD, text)


class BoxChars:
    """Box drawing character sets for Unicode and ASCII modes."""

    def __init__(self, ascii_only: bool = False):
        self.ascii_only = ascii_only
        if ascii_only:
            self.top_left = "+"
            self.top_right = "+"
            self.bottom_left = "+"
            self.bottom_right = "+"
            self.horizontal = "-"
            self.vertical = "|"
            self.tee_left = "+"
            self.tee_right = "+"
            self.cross = "+"
            self.bullet = "*"
            self.arrow = "->"
            self.check = "[v]"
            self.cross_mark = "[x]"
            self.warn_mark = "[!]"
            self.info_mark = "[i]"
        else:
            self.top_left = "╭"
            self.top_right = "╮"
            self.bottom_left = "╰"
            self.bottom_right = "╯"
            self.horizontal = "─"
            self.vertical = "│"
            self.tee_left = "├"
            self.tee_right = "┤"
            self.cross = "┼"
            self.bullet = "•"
            self.arrow = "→"
            self.check = "✓"
            self.cross_mark = "✗"
            self.warn_mark = "▲"
            self.info_mark = "ℹ"


def visible_len(text: str) -> int:
    """Calculate visible string width ignoring ANSI escape codes."""
    import re
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return len(ansi_escape.sub("", text))


class TerminalUI:
    """Comprehensive, responsive terminal UI manager and design system."""

    def __init__(self, ascii_only: bool = False, force_color: Optional[bool] = None):
        self.unicode_supported = self._check_unicode_support() and not ascii_only
        self.ascii_only = not self.unicode_supported
        self.color_supported = self._check_color_support(force_color)

        self.palette = TerminalPalette(enabled=self.color_supported)
        self.box = BoxChars(ascii_only=self.ascii_only)

    @staticmethod
    def _check_unicode_support() -> bool:
        """Check if terminal stdout encoding supports UTF-8."""
        encoding = getattr(sys.stdout, "encoding", "") or ""
        return "utf" in encoding.lower()

    @staticmethod
    def _check_color_support(force_color: Optional[bool] = None) -> bool:
        """Determine whether ANSI color output is appropriate."""
        if force_color is not None:
            return force_color
        # Respect NO_COLOR standard (https://no-color.org)
        if "NO_COLOR" in os.environ and os.environ["NO_COLOR"]:
            return False
        # Check TERM
        term = os.environ.get("TERM", "")
        if term == "dumb":
            return False
        # Check if connected to a TTY or explicitly forced
        is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
        return is_tty or bool(os.environ.get("CLICOLOR_FORCE"))

    def get_width(self, max_w: int = 90, min_w: int = 50) -> int:
        """Get safe responsive terminal width."""
        try:
            cols = shutil.get_terminal_size(fallback=(80, 24)).columns
            return max(min_w, min(cols - 2, max_w))
        except Exception:
            return 80

    # -------------------------------------------------------------------------
    # Layout & Containers
    # -------------------------------------------------------------------------

    def print_banner(self) -> None:
        """Print clean, modern application header without oversized ASCII clutter."""
        w = self.get_width(max_w=94)
        c = self.palette
        b = self.box

        app_title = f" {c.accent_bold('BLINDCHESS')} {c.muted('v1.0.0')} "
        tagline = "Local-First Blindfold & Strategic Chess Trainer"

        inner_w = w - 2
        title_vis = visible_len(app_title)
        right_fill = max(0, inner_w - title_vis - 2)
        top = f"{c.muted(b.top_left + b.horizontal*2)}{app_title}{c.muted(b.horizontal*right_fill + b.top_right)}"

        tagline_formatted = f"  {c.muted(tagline)}"
        tag_pad = max(0, inner_w - visible_len(tagline_formatted))
        mid = f"{c.muted(b.vertical)}{tagline_formatted}{' ' * tag_pad}{c.muted(b.vertical)}"

        bottom = f"{c.muted(b.bottom_left + b.horizontal*inner_w + b.bottom_right)}"

        print(f"\n{top}\n{mid}\n{bottom}")

    def render_panel(
        self,
        title: str,
        lines: List[str],
        width: Optional[int] = None,
        border_style: str = "muted",
    ) -> str:
        """Render a styled bordered card/panel."""
        w = width or self.get_width()
        inner_w = w - 4
        c = self.palette
        b = self.box

        color_func = getattr(c, border_style, c.muted)

        if title:
            title_text = f" {title} "
            t_vis = visible_len(title_text)
            r_fill = max(0, (w - 2) - t_vis - 2)
            top = f"{color_func(b.top_left + b.horizontal * 2)}{c.highlight(title_text)}{color_func(b.horizontal * r_fill + b.top_right)}"
        else:
            top = color_func(b.top_left + b.horizontal * (w - 2) + b.top_right)

        out = [top]
        for line in lines:
            line_vis = visible_len(line)
            pad = max(0, inner_w - line_vis)
            out.append(f"{color_func(b.vertical)}  {line}{' ' * pad}{color_func(b.vertical)}")

        bottom = color_func(b.bottom_left + b.horizontal * (w - 2) + b.bottom_right)
        out.append(bottom)
        return "\n".join(out)

    def print_status_bar(
        self,
        engine_name: str,
        engine_ready: bool,
        opponent_level: str,
        visibility: str,
        training_level: int,
    ) -> None:
        """Render compact, structured status bar."""
        c = self.palette
        b = self.box
        w = self.get_width(max_w=94)

        if engine_ready:
            eng_badge = f"{c.success(b.check)} Engine: {c.highlight(engine_name)}"
        else:
            eng_badge = f"{c.warning(b.warn_mark)} Engine: {c.muted('Offline (Engine-Free Mode)')}"

        opp_badge = f"Opponent: {c.accent_bold(opponent_level.capitalize())}"
        vis_badge = f"Board: {c.highlight(visibility.capitalize())}"
        lvl_badge = f"Level: {c.accent(str(training_level))}/6"

        row = f" {eng_badge}   {opp_badge}   {vis_badge}   {lvl_badge} "
        divider = c.muted(b.horizontal * (w - 2))
        print(f"\n{row}\n{divider}\n")

    def print_shortcut_bar(self, shortcuts: List[Tuple[str, str]]) -> None:
        """Render an intuitive horizontal keyboard shortcut footer."""
        c = self.palette
        b = self.box
        parts = []
        for key, desc in shortcuts:
            parts.append(f"{c.muted('[')}{c.accent_bold(key)}{c.muted(']')} {desc}")
        sep = f"  {c.muted(b.bullet)}  "
        print(c.muted("  ") + sep.join(parts))

    # -------------------------------------------------------------------------
    # Notification & Feedback Banners
    # -------------------------------------------------------------------------

    def print_message(self, message: str, prefix: str = "") -> None:
        """Print an informational message with clean indentation."""
        c = self.palette
        if prefix:
            print(f" {c.accent_bold('[' + prefix + ']')} {message}")
        else:
            print(f" {c.muted('•')} {message}")

    def print_success(self, message: str) -> None:
        """Print a positive confirmation message."""
        c = self.palette
        b = self.box
        print(f" {c.success_bold(b.check)} {c.success(message)}")

    def print_warning(self, message: str) -> None:
        """Print a cautionary warning message."""
        c = self.palette
        b = self.box
        print(f" {c.warning_bold(b.warn_mark)} {c.warning(message)}")

    def print_error(self, message: str, hint: Optional[str] = None) -> None:
        """Print an actionable error card with clear visual hierarchy."""
        c = self.palette
        b = self.box
        print(f"\n {c.error_bold(b.cross_mark)} {c.error_bold('Error:')} {c.error(message)}")
        if hint:
            print(f"   {c.muted(b.arrow)} {c.muted('Hint:')} {c.highlight(hint)}\n")

    def print_divider(self, title: Optional[str] = None) -> None:
        """Print a crisp section divider."""
        c = self.palette
        b = self.box
        w = self.get_width(max_w=84)
        if title:
            t = f" {title} "
            rem = max(0, w - visible_len(t) - 4)
            print(f"\n{c.muted(b.horizontal * 4)}{c.highlight(t)}{c.muted(b.horizontal * rem)}")
        else:
            print(f"{c.muted(b.horizontal * w)}")

    # -------------------------------------------------------------------------
    # Prompts & Inputs
    # -------------------------------------------------------------------------

    def prompt(self, prompt_text: str = "blindchess> ") -> str:
        """Prompt user with modern command styling, handling interrupts cleanly."""
        c = self.palette
        styled_prompt = f"{c.accent('❯')} {c.bold(prompt_text)}"
        try:
            return input(styled_prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n")
            return "quit"

    def render_timer_bar(self, remaining_sec: float, total_sec: float) -> str:
        """Render a compact horizontal timer progress bar."""
        if total_sec <= 0:
            return ""
        frac = max(0.0, min(1.0, remaining_sec / total_sec))
        length = 8
        filled = int(frac * length)
        empty = length - filled
        fill_char = "=" if self.ascii_only else "█"
        empty_char = "." if self.ascii_only else "░"
        return f"[{fill_char * filled}{empty_char * empty}]"

    def timed_prompt(
        self,
        prompt_text: str = "❯ ",
        time_limit_sec: float = 30.0,
    ) -> Tuple[str, float, bool]:
        """
        Prompt user with an active countdown timer.
        
        Uses monotonic clock and non-blocking I/O.
        Returns:
            Tuple[str, float, bool]: (answer_str, elapsed_seconds, is_timeout)
        """
        import select
        import time

        c = self.palette
        start_time = time.monotonic()

        # Non-TTY mode (pipes, test fixtures, automated non-interactive runs)
        if not sys.stdin.isatty():
            sys.stdout.write(f"{c.accent('❯')} {prompt_text} ")
            sys.stdout.flush()
            line = sys.stdin.readline()
            elapsed = round(time.monotonic() - start_time, 2)
            if not line:
                return "quit", elapsed, False
            cleaned = line.strip()
            is_timeout = (elapsed > time_limit_sec)
            return cleaned, elapsed, is_timeout

        # TTY Interactive mode with non-blocking key reads and live countdown
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        chars: List[str] = []

        try:
            tty.setcbreak(fd)

            while True:
                elapsed = time.monotonic() - start_time
                remaining = max(0.0, time_limit_sec - elapsed)

                if remaining <= 0.0:
                    sys.stdout.write(f"\r\033[K {c.error_bold('⏱ [Time Expired!]')} (Limit: {time_limit_sec}s)\n")
                    sys.stdout.flush()
                    return "".join(chars).strip(), round(elapsed, 2), True

                # Determine styling by remaining percentage
                bar = self.render_timer_bar(remaining, time_limit_sec)
                rem_int = int(remaining)

                if remaining <= 5.0:
                    timer_badge = c.error_bold(f"⏱ {bar} {remaining:.1f}s ! ")
                elif remaining <= (0.25 * time_limit_sec):
                    timer_badge = c.warning_bold(f"⏱ {bar} {rem_int}s ⚠ ")
                else:
                    timer_badge = c.accent(f"⏱ {bar} {rem_int}s ")

                user_typed = "".join(chars)
                line_display = f"\r\033[K {c.bold(prompt_text)} {timer_badge}❯ {user_typed}"
                sys.stdout.write(line_display)
                sys.stdout.flush()

                # Poll for user keypress up to 0.15s
                timeout_poll = min(0.15, max(0.01, remaining))
                r, _, _ = select.select([sys.stdin], [], [], timeout_poll)
                if r:
                    ch = sys.stdin.read(1)
                    if ch in ("\n", "\r"):
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                        return "".join(chars).strip(), round(time.monotonic() - start_time, 2), False
                    elif ch == "\x03":  # Ctrl+C
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                        return "quit", round(time.monotonic() - start_time, 2), False
                    elif ch in ("\x7f", "\b"):  # Backspace
                        if chars:
                            chars.pop()
                    elif ord(ch) >= 32:  # Printable character
                        chars.append(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    # -------------------------------------------------------------------------
    # Board & Move Visualizations
    # -------------------------------------------------------------------------

    def print_board(self, board_state: BoardState, perspective_white: bool = True) -> None:
        """Render the board cleanly with coordinate headers and frame styling."""
        c = self.palette
        rendered_board = board_state.render_board(
            unicode_pieces=not self.ascii_only,
            perspective=chess_color_from_bool(perspective_white),
        )

        bal = board_state.get_material_balance()
        diff_str = f"{bal['diff']:+d}" if bal["diff"] != 0 else "Even"
        is_over, status_text, _ = board_state.get_game_status()

        status_line = f"Turn: {c.highlight(board_state.turn_name)} ({board_state.move_number}.) | Bal: {c.accent(diff_str)} | {c.muted(status_text)}"

        panel_lines = [status_line, ""] + rendered_board.split("\n")
        panel = self.render_panel(title="Chessboard View", lines=panel_lines, width=46, border_style="muted")
        print("\n" + panel + "\n")

    # -------------------------------------------------------------------------
    # Table & Metrics Formatter
    # -------------------------------------------------------------------------

    def print_table(self, headers: List[str], rows: List[List[str]], max_width: Optional[int] = None) -> None:
        """Render a clean, aligned tabular view."""
        c = self.palette
        b = self.box
        if not rows and not headers:
            return

        col_count = len(headers)
        col_widths = [visible_len(h) for h in headers]
        for row in rows:
            for idx, val in enumerate(row):
                if idx < col_count:
                    col_widths[idx] = max(col_widths[idx], visible_len(str(val)))

        header_cells = [f"{c.highlight(headers[i].ljust(col_widths[i]))}" for i in range(col_count)]
        header_line = f"  {'   '.join(header_cells)}"
        sep_cells = [b.horizontal * col_widths[i] for i in range(col_count)]
        sep_line = f"  {c.muted('   '.join(sep_cells))}"

        print("\n" + header_line)
        print(sep_line)

        for row in rows:
            cells = []
            for i in range(col_count):
                val = str(row[i]) if i < len(row) else ""
                cells.append(val.ljust(col_widths[i]))
            print(f"  {'   '.join(cells)}")
        print()


def chess_color_from_bool(is_white: bool):
    import chess
    return chess.WHITE if is_white else chess.BLACK
