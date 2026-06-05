"""
pe dashboard — stdlib-only ANSI terminal dashboard for prompt enhancement analytics.

Zero dependencies. Unicode sparklines, box-drawing panels, ANSI color.
Designed per Auggie's review: actionable metrics > pretty boxes.
"""

import json
import os
import sys
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# ANSI helpers
# ═══════════════════════════════════════════════════════════════════

ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "cyan": "\033[38;5;51m",
    "violet": "\033[38;5;99m",
    "green": "\033[38;5;120m",
    "red": "\033[38;5;203m",
    "yellow": "\033[38;5;220m",
    "white": "\033[38;5;255m",
    "gray": "\033[38;5;245m",
    "bg_dark": "\033[48;5;234m",
}

UNICODE_BLOCKS = "▁▂▃▄▅▆▇█"
ASCII_BLOCKS = "._-~=+#@"

BOX = {
    "h": "─", "v": "│",
    "tl": "┌", "tr": "┐", "bl": "└", "br": "┘",
    "t": "┬", "b": "┴", "l": "├", "r": "┤", "x": "┼"
}


def colorize(text, color, bold=False):
    """Apply ANSI color. No-op if NO_COLOR or not TTY."""
    if not _use_color():
        return text
    prefix = ANSI.get("bold", "") if bold else ""
    return f"{prefix}{ANSI.get(color, '')}{text}{ANSI['reset']}"


def _use_color():
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


def _is_tty():
    return sys.stdout.isatty()


def _blocks(use_ascii=False):
    return ASCII_BLOCKS if use_ascii else UNICODE_BLOCKS


# ═══════════════════════════════════════════════════════════════════
# Sparkline
# ═══════════════════════════════════════════════════════════════════

def sparkline(values, width=20, use_ascii=False, label=""):
    """Render a Unicode sparkline from a list of numeric values."""
    if not values:
        return "(no data)"

    blocks = _blocks(use_ascii)
    vmin, vmax = min(values), max(values)
    if vmax == vmin:
        vmax = vmin + 1

    chars = []
    for v in values:
        idx = int((v - vmin) / (vmax - vmin) * (len(blocks) - 1))
        chars.append(blocks[max(0, min(idx, len(blocks) - 1))])

    result = "".join(chars)
    if label:
        result = f"{label} {result}"
    return result


# ═══════════════════════════════════════════════════════════════════
# Bar chart
# ═══════════════════════════════════════════════════════════════════

def bar_chart(items, max_width=30, use_ascii=False, value_fmt="{value}", sort=True):
    """Render a horizontal bar chart. items = [(label, value), ...]."""
    if not items:
        return "(no data)"

    if sort:
        items = sorted(items, key=lambda x: -x[1])

    max_val = max(v for _, v in items) if items else 1
    max_label = max(len(str(l)) for l, _ in items) if items else 10
    fill_char = "#" if use_ascii else "█"

    lines = []
    for label, val in items:
        bar_len = int((val / max(max_val, 1)) * max_width)
        bar = fill_char * max(bar_len, 1)
        v_str = value_fmt.format(value=val)
        lines.append(f"  {str(label):<{max_label}}  {bar} {v_str}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Panel rendering
# ═══════════════════════════════════════════════════════════════════

def panel(title, content, width=60, accent="cyan"):
    """Render a bordered panel."""
    title_display = f" {title} "[:width - 4]
    top = f"{BOX['tl']}{colorize(title_display.ljust(width - 4, BOX['h']), accent, bold=True)}{BOX['tr']}"
    middle_lines = content.split("\n")
    middle = "\n".join(
        f"{BOX['v']} {line.ljust(width - 4)} {BOX['v']}"
        for line in middle_lines
    )
    bottom = f"{BOX['bl']}{BOX['h'] * (width - 2)}{BOX['br']}"
    return f"{top}\n{middle}\n{bottom}"


def panel_pair(left_title, left_content, right_title, right_content, total_width=120, use_ascii=False):
    """Render two panels side-by-side."""
    hw = total_width // 2 - 2
    left = panel(left_title, left_content, hw, "cyan").split("\n")
    right = panel(right_title, right_content, hw, "violet").split("\n")
    max_lines = max(len(left), len(right))
    left += [" " * (hw + 2)] * (max_lines - len(left))
    right += [" " * (hw + 2)] * (max_lines - len(right))
    return "\n".join(f"{l}  {r}" for l, r in zip(left, right))


# ═══════════════════════════════════════════════════════════════════
# Data loading
# ═══════════════════════════════════════════════════════════════════

DEFAULT_STORE = Path.home() / ".prompt-enhancer" / "store.jsonl"


def load_records(store_path=None):
    path = Path(store_path) if store_path else DEFAULT_STORE
    if not path.exists():
        return []
    records = []
    for line in path.read_text().strip().splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def parse_since(since_str):
    """Parse --since argument: '24h', '7d', '2026-06-01'."""
    now = datetime.now(timezone.utc)
    if since_str.endswith("h"):
        return now - timedelta(hours=int(since_str[:-1]))
    if since_str.endswith("d"):
        return now - timedelta(days=int(since_str[:-1]))
    if since_str == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        return datetime.fromisoformat(since_str).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ═══════════════════════════════════════════════════════════════════
# Compute stats
# ═══════════════════════════════════════════════════════════════════

def compute_stats(records):
    """Compute all dashboard stats from records."""
    total = len(records)
    if total == 0:
        return {"total": 0}

    before_scores = []
    after_scores = []
    deltas = []
    by_agent = {}
    failures = 0

    for r in records:
        bm = r.get("benchmark")
        if bm:
            b = bm.get("before", {}).get("total")
            a = bm.get("after", {}).get("total")
            if isinstance(b, int) and isinstance(a, int):
                before_scores.append(b)
                after_scores.append(a)
                deltas.append(a - b)

        status = r.get("status", "ok")
        if status in ("error", "failed", "timeout"):
            failures += 1

        agent = r.get("agent") or "—"
        if agent not in by_agent:
            by_agent[agent] = {"count": 0, "deltas": [], "fails": 0}
        by_agent[agent]["count"] += 1
        if status in ("error", "failed", "timeout"):
            by_agent[agent]["fails"] += 1
        if deltas:
            by_agent[agent]["deltas"].append(deltas[-1])

    # Agent effectiveness
    agent_eff = []
    for agent, data in by_agent.items():
        avg_d = sum(data["deltas"]) / len(data["deltas"]) if data["deltas"] else 0
        agent_eff.append((agent, avg_d, data["count"], data["fails"]))

    # Velocity by day
    velocity = {}
    for r in records:
        ts = r.get("timestamp", "")
        day = ts[:10] if ts else "unknown"
        velocity[day] = velocity.get(day, 0) + 1

    # Score trend (last 15)
    score_trend_before = before_scores[-15:] if before_scores else []
    score_trend_after = after_scores[-15:] if after_scores else []

    return {
        "total": total,
        "with_benchmark": len(deltas),
        "avg_before": sum(before_scores) / len(before_scores) if before_scores else 0,
        "avg_after": sum(after_scores) / len(after_scores) if after_scores else 0,
        "avg_delta": sum(deltas) / len(deltas) if deltas else 0,
        "best_delta": max(deltas) if deltas else 0,
        "pass_rate": ((total - failures) / total * 100) if total > 0 else 100,
        "failures": failures,
        "agent_effectiveness": agent_eff,
        "velocity": sorted(velocity.items())[-7:],  # last 7 days
        "score_trend_before": score_trend_before,
        "score_trend_after": score_trend_after,
        "recent": records[-10:][::-1],  # last 10, newest first
    }


# ═══════════════════════════════════════════════════════════════════
# Rendering
# ═══════════════════════════════════════════════════════════════════

def render_dashboard(stats, use_ascii=False, show_prompts=False):
    """Render the full dashboard."""
    if not stats or stats.get("total", 0) == 0:
        print("No enhancement data yet. Run 'pe persona' or 'pe enhance-task' to get started.")
        return

    total_width = min(shutil.get_terminal_size().columns, 120)
    narrow = total_width < 80

    # Header
    print(colorize(f"\n  ⚡ pe dashboard{' ' * (total_width - 25)}v1.3.0", "cyan", bold=True))
    print(colorize(f"{BOX['h'] * total_width}", "dim"))

    # ── Row 1: Summary + Score Trend ──
    summary_lines = [
        f"  Runs: {stats['total']}",
        f"  With benchmarks: {stats.get('with_benchmark', 0)}",
        f"  Avg score: {stats['avg_before']:.0f} → {stats['avg_after']:.0f} (+{stats['avg_delta']:.0f})" if stats.get("avg_before") else "  Avg score: no benchmarks yet",
        f"  Pass rate: {stats['pass_rate']:.0f}%",
        f"  Failures: {stats.get('failures', 0)}",
    ]
    summary = "\n".join(summary_lines)

    if stats.get("score_trend_after"):
        before_spark = sparkline(stats["score_trend_before"], 20, use_ascii)
        after_spark = sparkline(stats["score_trend_after"], 20, use_ascii)
        n = len(stats["score_trend_after"])
        trend_lines = [
            f"  Last {n}:",
            f"  Before: {before_spark} → avg {stats['score_trend_before'][-1] if stats['score_trend_before'] else '?'}",
            f"  After:  {after_spark} → avg {stats['score_trend_after'][-1] if stats['score_trend_after'] else '?'}",
        ]
    else:
        trend_lines = ["  No benchmark data", "  Run 'pe benchmark --enhance ...' to see trends"]
    trend = "\n".join(trend_lines)

    print(panel_pair("Summary", summary, "Score Trend", trend, total_width, use_ascii))

    # ── Row 2: Agent Effectiveness + Velocity ──
    if stats.get("agent_effectiveness"):
        agent_items = [(a, d) for a, d, c, f in stats["agent_effectiveness"] if c > 0]
        agent_content = bar_chart(agent_items, 25, use_ascii, value_fmt="+{value:.0f}")
    else:
        agent_content = "  No agent data"

    if stats.get("velocity"):
        vel_items = stats["velocity"]
        vel_content = bar_chart(vel_items, 25, use_ascii, value_fmt="{value} runs")
    else:
        vel_content = "  No velocity data"

    print(panel_pair("Agent Effectiveness (avg Δ)", agent_content, "Velocity (by day)", vel_content, total_width, use_ascii))

    # ── Row 3: Recent runs ──
    recents = stats.get("recent", [])
    if recents:
        recent_width = total_width - 4
        header_line = f" {'When':<17} {'Agent':<10} {'Before→After':>13} {'Δ':>6} {'Status':<8} {'Seed' if show_prompts else 'ID'}"
        sep_line = "─" * (recent_width - 2)
        lines = [header_line, sep_line]
        for r in recents[:8]:
            ts = r.get("timestamp", "")[:16].replace("T", " ")
            agent = (r.get("agent") or "—")[:10]
            bm = r.get("benchmark") or {}
            b = bm.get("before", {}).get("total", "?")
            a = bm.get("after", {}).get("total", "?")
            scores = f"{b}→{a}/35" if isinstance(b, int) else "—"
            delta = a - b if isinstance(b, int) and isinstance(a, int) else "—"
            d_str = f"+{delta}" if isinstance(delta, int) and delta > 0 else str(delta)
            status = r.get("status", "ok")[:8]
            if show_prompts:
                seed = r.get("seed", "")[:60].replace("\n", " ")
            else:
                seed = r.get("id", "—")[:14]
            lines.append(f" {ts:<17} {agent:<10} {scores:>13} {d_str:>6} {status:<8} {seed}")
        recent_content = "\n".join(lines)
    else:
        recent_content = " No recent runs"

    recent_title = f"Recent ({'unredacted' if show_prompts else 'redacted'})"
    recent_panel = panel(recent_title, recent_content, total_width - 2, "green")
    print(recent_panel)

    # Footer
    print(colorize(f"{BOX['h'] * total_width}", "dim"))
    footer_parts = ["[j↓] scroll  [k↑] scroll  [q] quit"]
    if _is_tty():
        footer_parts.append("[--ascii] no-unicode")
    print(colorize("  " + "  │  ".join(footer_parts), "dim"))
    print()


# ═══════════════════════════════════════════════════════════════════
# Entry point (called from cli.py)
# ═══════════════════════════════════════════════════════════════════

def cmd_dashboard(store_path=None, agent=None, since=None, json_out=False,
                  ascii_mode=False, show_prompts=False):
    """Main entry point for pe dashboard."""
    records = load_records(store_path)

    # Filter
    if agent:
        records = [r for r in records if r.get("agent") == agent]
    if since:
        since_dt = parse_since(since)
        if since_dt:
            records = [r for r in records
                       if datetime.fromisoformat(r.get("timestamp", "1970-01-01T00:00:00Z").replace("Z", "+00:00")) >= since_dt]
        else:
            print(f"Invalid --since: {since}", file=sys.stderr)
            sys.exit(1)

    stats = compute_stats(records)

    if json_out:
        print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))
        return

    # Detect ASCII mode
    use_ascii = ascii_mode or not _is_tty() or os.environ.get("TERM") == "dumb"

    render_dashboard(stats, use_ascii=use_ascii, show_prompts=show_prompts)
