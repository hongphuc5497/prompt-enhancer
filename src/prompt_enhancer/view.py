"""
Rich prompt viewer — ANSI-styled terminal rendering for enhanced prompts.

Renders the 7-section markdown output with color-coded headers,
box-drawing panels, and an interactive footer. All ANSI/Unicode and
display-width primitives come from term.py so styling stays consistent
across the CLI.
"""

import sys
import time
import signal
import threading

from . import term

# Thin aliases so call sites read naturally.
c = term.colorize
BOX = term.BOX

SECTION_COLORS = {
    "ROLE": "cyan",
    "CONTEXT": "violet",
    "BEHAVIORAL RULES": "yellow",
    "BEHAVIORAL": "yellow",
    "TECHNICAL GUIDELINES": "green",
    "TECHNICAL": "green",
    "OUTPUT FORMAT": "cyan",
    "OUTPUT": "cyan",
    "PITFALLS": "red",
    "GUARDRAILS": "red",
    "EXAMPLES": "violet",
    "PRO TIP": "green",
}


# ═══════════════════════════════════════════════════════════════════
# Rich prompt renderer
# ═══════════════════════════════════════════════════════════════════

def render_prompt(markdown_text, agent=None, duration_ms=None):
    """Render enhanced markdown prompt with ANSI-styled panels.

    Auto-detects TTY. If stdout is not a TTY, falls back to raw text.
    When stdin is also a TTY, an interactive key loop follows the render.
    """
    if not sys.stdout.isatty():
        # Not a TTY — just print raw text (for pipes, CI, etc.)
        print(markdown_text)
        return

    lines = markdown_text.split("\n")
    width = term.terminal_width(100)

    # Header bar (pad by display width so ANSI codes don't skew alignment)
    header = f"  {c('⚡', 'cyan')} {c('Prompt Enhancer', 'white', bold=True)}"
    if agent:
        header += f"  {c(f'via {agent}', 'dim')}"
    if duration_ms:
        header += f"  {c(f'{duration_ms/1000:.1f}s', 'dim')}"
    header += " " * max(0, width - term.display_width(header) - 1)
    print()
    print(c(BOX["h"] * width, "dim"))
    print(header)
    print(c(BOX["h"] * width, "dim"))
    print()

    # Parse sections
    current_section = None
    section_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Detect section headers: ## ROLE, ## CONTEXT, etc.
        if stripped.startswith("## "):
            # Flush previous section
            if current_section and section_lines:
                _flush_section(current_section, section_lines, width)
                section_lines = []

            section_name = stripped[3:].strip().upper()
            current_section = section_name

            # Print section header
            color = SECTION_COLORS.get(section_name.split("/")[0].strip(), "white")
            print(f"  {c('▸ ' + section_name, color, bold=True)}")
            print(f"  {c(BOX['h'] * (width - 4), 'dim')}")
            continue

        # Collect section content
        if current_section:
            section_lines.append(line)

    # Flush last section
    if current_section and section_lines:
        _flush_section(current_section, section_lines, width)

    # Footer — only advertise keys the viewer actually handles.
    print()
    print(c(BOX["h"] * width, "dim"))
    print(f"  {c('[c] copy', 'dim')}  {c('[r] show raw', 'dim')}  {c('[q] done', 'dim')}")
    print()

    # Interactive key loop (requires an interactive stdin too).
    if sys.stdin.isatty():
        _interactive_loop(markdown_text)


def _flush_section(section_name, lines, width):
    """Print a section's content with proper formatting."""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            print()
            continue

        # Bullet points
        if stripped.startswith("- ") or stripped.startswith("* "):
            bullet = stripped[2:]
            # Wrap long lines
            wrapped = _wrap_text(f"  • {bullet}", width - 4)
            for w in wrapped:
                print(f"  {c(w, 'white')}")
        # Code blocks
        elif stripped.startswith("```"):
            continue  # skip fence markers, code is handled by indentation
        # Continuation lines (indented)
        elif line.startswith("  ") or line.startswith("\t"):
            print(f"  {c(line, 'dim')}")
        # Regular text
        else:
            wrapped = _wrap_text(stripped, width - 6)
            for w in wrapped:
                print(f"    {c(w, 'white')}")


def _wrap_text(text, max_width):
    """Simple word wrap, measured by display width (CJK/emoji aware)."""
    if term.display_width(text) <= max_width:
        return [text]
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if term.display_width(current) + term.display_width(word) + 1 <= max_width:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ═══════════════════════════════════════════════════════════════════
# Interactive viewer loop
# ═══════════════════════════════════════════════════════════════════

def _interactive_loop(markdown_text):
    """Single-key actions on the rendered prompt: copy, show raw, quit.

    No alt-screen: the rendered output stays in scrollback so the prompt
    remains readable and copyable after quitting. Each action is one-shot.
    """
    while True:
        key = term.read_key()
        # NO_TTY (non-interactive), q, Enter, Esc, Ctrl-C/D all exit.
        if key in (term.NO_TTY, "q", "Q", "esc", "\r", "\n", "\x03", "\x04"):
            return
        if key in ("c", "C"):
            if term.copy_to_clipboard(markdown_text):
                print(f"  {c('✔ copied to clipboard', 'green')}")
            else:
                print(f"  {c('✖ no clipboard tool found (install xclip/wl-clipboard)', 'red')}")
        elif key in ("r", "R"):
            print()
            print(c("  ── raw markdown ──", "dim"))
            print(markdown_text)
            print(c("  ──────────────────", "dim"))


# ═══════════════════════════════════════════════════════════════════
# Progress spinner (shown to stderr during generation)
# ═══════════════════════════════════════════════════════════════════

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class Spinner:
    """Context manager for showing a progress spinner on stderr."""

    def __init__(self, message="Working", stream=sys.stderr):
        self.message = message
        self.stream = stream
        self._running = False
        self._thread = None
        self.start_time = None
        self._prev_sigint = None
        self._prev_sigterm = None

    def __enter__(self):
        self.start_time = time.time()
        self._running = True
        if self.stream.isatty():
            term.hide_cursor(self.stream)
            self._install_signal_handlers()
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *args):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        elapsed = time.time() - self.start_time
        if self.stream.isatty():
            self._restore_signal_handlers()
            self.stream.write("\r\033[K")  # clear spinner line
            self.stream.write(f"{c('✔', 'green')} {self.message}  {c(f'({elapsed:.1f}s)', 'dim')}\n")
            term.show_cursor(self.stream)
            self.stream.flush()

    def _install_signal_handlers(self):
        """Restore the cursor if the run is interrupted, then re-raise."""
        def handler(signum, _frame):
            self._running = False
            term.show_cursor(self.stream)
            self.stream.write("\n")
            self.stream.flush()
            self._restore_signal_handlers()
            if signum == signal.SIGINT:
                raise KeyboardInterrupt
            sys.exit(128 + signum)
        try:
            self._prev_sigint = signal.signal(signal.SIGINT, handler)
            self._prev_sigterm = signal.signal(signal.SIGTERM, handler)
        except ValueError:
            # Not in the main thread — signals can't be installed; skip.
            pass

    def _restore_signal_handlers(self):
        try:
            if self._prev_sigint is not None:
                signal.signal(signal.SIGINT, self._prev_sigint)
            if self._prev_sigterm is not None:
                signal.signal(signal.SIGTERM, self._prev_sigterm)
        except (ValueError, TypeError):
            pass

    def _spin(self):
        i = 0
        while self._running:
            frame = SPINNER_FRAMES[i % len(SPINNER_FRAMES)]
            elapsed = time.time() - self.start_time
            self.stream.write(f"\r  {c(frame, 'cyan')} {self.message}  {c(f'({elapsed:.0f}s)', 'dim')}")
            self.stream.flush()
            time.sleep(0.1)
            i += 1

    def update(self, message):
        self.message = message


def log_progress(message, stream=sys.stderr):
    """Print a one-line progress update to stderr."""
    if stream.isatty():
        stream.write(f"\r\033[K  {c('…', 'dim')} {message}\n")
    else:
        stream.write(f"[pe] {message}\n")
    stream.flush()
