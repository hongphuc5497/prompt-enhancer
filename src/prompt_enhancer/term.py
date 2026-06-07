"""
term.py — shared, zero-dependency terminal primitives (Unix-only).

One canonical home for ANSI color, box-drawing, display-width-aware
padding/truncation, sparkline/bar charts, raw single-key input, and
clipboard access. view.py, dashboard.py, and lint.py all draw from here
so colors, borders, and width math stay consistent.
"""

import os
import re
import sys
import shutil
import subprocess
import unicodedata

from . import __version__ as VERSION

try:
    import termios
    import tty
    import select as _select
    _HAS_TERMIOS = True
except ImportError:  # non-Unix; this milestone targets Unix only
    _HAS_TERMIOS = False


# ── Color ──────────────────────────────────────────────────────────

ANSI = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "cyan": "\033[38;5;51m", "violet": "\033[38;5;99m",
    "green": "\033[38;5;120m", "red": "\033[38;5;203m",
    "yellow": "\033[38;5;220m", "white": "\033[38;5;255m",
    "gray": "\033[38;5;245m", "bg_dark": "\033[48;5;234m",
}

BOX = {
    "h": "─", "v": "│",
    "tl": "┌", "tr": "┐", "bl": "└", "br": "┘",
    "t": "┬", "b": "┴", "l": "├", "r": "┤", "x": "┼",
}

UNICODE_BLOCKS = "▁▂▃▄▅▆▇█"
ASCII_BLOCKS = "._-~=+#@"

_ANSI_RE = re.compile(r"\033\[[0-9;?]*[a-zA-Z]")


def should_color(stream=None):
    """Color policy: honor NO_COLOR / TERM=dumb, else require a TTY.

    Defaults to sys.stdout. Key input checks stdin.isatty() separately —
    the two streams can differ under pipes.
    """
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    return (stream or sys.stdout).isatty()


def colorize(text, color, bold=False, stream=None):
    """Apply an ANSI color. No-op when color is disabled."""
    if not should_color(stream):
        return text
    prefix = ANSI["bold"] if bold else ""
    return f"{prefix}{ANSI.get(color, '')}{text}{ANSI['reset']}"


# ── Display width ──────────────────────────────────────────────────

def strip_ansi(text):
    """Remove ANSI escape sequences so width math sees only glyphs."""
    return _ANSI_RE.sub("", text)


def display_width(text):
    """Visible column width, counting CJK/emoji (W/F) as 2 columns and
    zero-width combining marks as 0. ANSI escape codes are ignored.
    """
    width = 0
    for ch in strip_ansi(text):
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def truncate(text, max_width, ellipsis="…"):
    """Truncate to max_width display columns, appending an ellipsis."""
    if display_width(text) <= max_width:
        return text
    ell = display_width(ellipsis)
    out, w = "", 0
    for ch in text:
        cw = display_width(ch)
        if w + cw > max_width - ell:
            break
        out += ch
        w += cw
    return out + ellipsis


def pad(text, width, align="left", fill=" "):
    """Pad to a display width. Width-aware, so colored/CJK text aligns."""
    gap = width - display_width(text)
    if gap <= 0:
        return text
    if align == "right":
        return fill * gap + text
    if align == "center":
        left = gap // 2
        return fill * left + text + fill * (gap - left)
    return text + fill * gap


# ── Box & panels ───────────────────────────────────────────────────

def panel(title, content, width=60, accent="cyan", use_ascii=False):
    """Bordered panel that is exactly `width` columns on every row.

    Fixes the historical ragged-border bug: top, body, and bottom rows
    are all `width` display columns, so colored titles and CJK/emoji
    content stay aligned.
    """
    inner = width - 2            # columns between the two vertical borders
    body_w = inner - 2           # content area (one space padding each side)
    h = "-" if use_ascii else BOX["h"]
    v = "|" if use_ascii else BOX["v"]
    tl = "+" if use_ascii else BOX["tl"]
    tr = "+" if use_ascii else BOX["tr"]
    bl = "+" if use_ascii else BOX["bl"]
    br = "+" if use_ascii else BOX["br"]

    title_bar = pad(f" {title} ", inner, fill=h)
    top = f"{tl}{colorize(title_bar, accent, bold=True)}{tr}"
    rows = [f"{v} {pad(truncate(line, body_w), body_w)} {v}"
            for line in content.split("\n")]
    bottom = f"{bl}{h * inner}{br}"
    return "\n".join([top, *rows, bottom])


def panel_pair(left_title, left_content, right_title, right_content,
               total_width=120, use_ascii=False):
    """Two panels side by side, columns aligned via display width."""
    hw = total_width // 2 - 2
    left = panel(left_title, left_content, hw, "cyan", use_ascii).split("\n")
    right = panel(right_title, right_content, hw, "violet", use_ascii).split("\n")
    n = max(len(left), len(right))
    left += [" " * hw] * (n - len(left))
    right += [" " * hw] * (n - len(right))
    return "\n".join(f"{lft}  {rgt}" for lft, rgt in zip(left, right))


def rule(width=None, use_ascii=False, color="dim"):
    """A horizontal divider line spanning `width` columns (dim by default)."""
    width = width or terminal_width()
    h = "-" if use_ascii else BOX["h"]
    return colorize(h * width, color)


def header(title, right="", width=None, use_ascii=False):
    """Standard command header: a branded '  ⚡ <title>' line with `right`
    flush-right (e.g. a version), followed by a dim divider.

    Returns [title_line, divider] so callers print them as they like. Widths
    use display_width so the right field stays aligned despite emoji/CJK.
    """
    width = width or terminal_width()
    left = f"  ⚡ {title}"
    if right:
        gap = max(1, width - display_width(left) - display_width(right))
        line = f"{left}{' ' * gap}{right}"
    else:
        line = left
    return [colorize(line, "cyan", bold=True), rule(width, use_ascii)]


def footer(parts, use_ascii=False):
    """Dim, separator-joined hint line: '  a  │  b  │  c' (│→| in ASCII)."""
    if not parts:
        return ""
    vsep = "|" if use_ascii else BOX["v"]
    return colorize("  " + f"  {vsep}  ".join(parts), "dim")


# ── Charts ─────────────────────────────────────────────────────────

def sparkline(values, width=20, use_ascii=False, label=""):
    """Unicode (or ASCII) sparkline from a list of numeric values."""
    if not values:
        return "(no data)"
    blocks = ASCII_BLOCKS if use_ascii else UNICODE_BLOCKS
    vmin, vmax = min(values), max(values)
    if vmax == vmin:
        vmax = vmin + 1
    chars = [
        blocks[max(0, min(int((v - vmin) / (vmax - vmin) * (len(blocks) - 1)),
                          len(blocks) - 1))]
        for v in values
    ]
    out = "".join(chars)
    return f"{label} {out}" if label else out


def bar_chart(items, max_width=30, use_ascii=False, value_fmt="{value}", sort=True):
    """Horizontal bar chart. items = [(label, value), ...]."""
    if not items:
        return "(no data)"
    if sort:
        items = sorted(items, key=lambda x: -x[1])
    max_val = max(v for _, v in items) or 1
    max_label = max(display_width(str(lbl)) for lbl, _ in items)
    fill = "#" if use_ascii else "█"
    lines = []
    for label, val in items:
        bar = fill * max(int((val / max(max_val, 1)) * max_width), 1)
        lines.append(f"  {pad(str(label), max_label)}  {bar} {value_fmt.format(value=val)}")
    return "\n".join(lines)


# ── Raw key input (Unix-only) ──────────────────────────────────────

NO_TTY = "\x00no-tty"   # sentinel: stdin is not interactive


def read_key(timeout=None):
    """Read one keypress in raw mode. Returns:
      - a single char ('q', 'j', ...),
      - 'up'/'down'/'left'/'right' for arrows, 'esc' for a bare ESC,
      - None on timeout (when `timeout` is set and nothing was pressed),
      - NO_TTY if stdin is not a TTY (caller should fall back).
    Raw mode is always restored.
    """
    if not _HAS_TERMIOS or not sys.stdin.isatty():
        return NO_TTY
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        if timeout is not None:
            ready, _, _ = _select.select([sys.stdin], [], [], timeout)
            if not ready:
                return None
        ch = sys.stdin.read(1)
        if ch == "\033":
            ready, _, _ = _select.select([sys.stdin], [], [], 0.002)
            if ready and sys.stdin.read(1) == "[":
                arrow = sys.stdin.read(1)
                return {"A": "up", "B": "down",
                        "C": "right", "D": "left"}.get(arrow, "esc")
            return "esc"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ── Clipboard, cursor, screen ──────────────────────────────────────

def copy_to_clipboard(text):
    """Copy text using the first available Unix clipboard tool.
    Returns True on success, False if no tool exists or it failed.
    """
    candidates = (
        ["pbcopy"],                              # macOS
        ["wl-copy"],                             # Wayland
        ["xclip", "-selection", "clipboard"],    # X11
        ["xsel", "--clipboard", "--input"],      # X11 alt
    )
    for cmd in candidates:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text.encode("utf-8"), check=True)
                return True
            except Exception:
                continue
    return False


def terminal_width(cap=120):
    """Current terminal width, capped (defaults to 120)."""
    return min(shutil.get_terminal_size().columns, cap)


def terminal_height(cap=None):
    """Current terminal height in rows; optionally capped."""
    rows = shutil.get_terminal_size().lines
    return min(rows, cap) if cap else rows


def hide_cursor(stream=sys.stderr):
    if stream.isatty():
        stream.write("\033[?25l")
        stream.flush()


def show_cursor(stream=sys.stderr):
    if stream.isatty():
        stream.write("\033[?25h")
        stream.flush()


ALT_SCREEN_ENTER = "\033[?1049h"
ALT_SCREEN_EXIT = "\033[?1049l"
CLEAR = "\033[2J\033[H"
