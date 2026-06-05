"""
Rich prompt viewer — ANSI-styled terminal rendering for enhanced prompts.

Renders the 7-section markdown output with color-coded headers,
box-drawing panels, and a navigation footer. Reuses the same
ANSI/Unicode primitives as dashboard.py for visual consistency.
"""

import os
import sys
import time
import shutil
import threading


# ═══════════════════════════════════════════════════════════════════
# ANSI primitives (inlined to avoid circular imports from dashboard.py)
# ═══════════════════════════════════════════════════════════════════

ANSI = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "cyan": "\033[38;5;51m", "violet": "\033[38;5;99m",
    "green": "\033[38;5;120m", "red": "\033[38;5;203m",
    "yellow": "\033[38;5;220m", "white": "\033[38;5;255m",
    "gray": "\033[38;5;245m",
}

BOX = {
    "h": "─", "v": "│", "tl": "┌", "tr": "┐", "bl": "└", "br": "┘"
}

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


def _use_color():
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


def _is_tty():
    return sys.stdout.isatty()


def c(text, color):
    if not _use_color():
        return text
    return f"{ANSI.get(color, '')}{text}{ANSI['reset']}"


# ═══════════════════════════════════════════════════════════════════
# Rich prompt renderer
# ═══════════════════════════════════════════════════════════════════

def render_prompt(markdown_text, agent=None, duration_ms=None):
    """Render enhanced markdown prompt with ANSI-styled panels.
    
    Auto-detects TTY. If not a TTY, falls back to raw text.
    """
    if not _is_tty():
        # Not a TTY — just print raw text (for pipes, CI, etc.)
        print(markdown_text)
        return

    lines = markdown_text.split("\n")
    width = min(shutil.get_terminal_size().columns, 100)

    # Header bar
    header = f"  {c('⚡', 'cyan')} {c('Prompt Enhancer', 'white', bold=True)}"
    if agent:
        header += f"  {c(f'via {agent}', 'dim')}"
    if duration_ms:
        header += f"  {c(f'{duration_ms/1000:.1f}s', 'dim')}"
    header += " " * (width - len(header) - 1)
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

    # Footer
    print()
    print(c(BOX["h"] * width, "dim"))
    print(f"  {c('[c] copy', 'dim')}  {c('[r] raw', 'dim')}  {c('[s] store', 'dim')}  {c('[q] quit', 'dim')}")
    print()


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
    """Simple word wrap."""
    if len(text) <= max_width:
        return [text]
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_width:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


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

    def __enter__(self):
        self.start_time = time.time()
        self._running = True
        if self.stream.isatty():
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *args):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        elapsed = time.time() - self.start_time
        if self.stream.isatty():
            self.stream.write(f"\r\033[K")  # clear spinner line
            self.stream.write(f"{c('✔', 'green')} {self.message}  {c(f'({elapsed:.1f}s)', 'dim')}\n")
            self.stream.flush()

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
