"""
pe dashboard — stdlib-only ANSI terminal dashboard for prompt enhancement analytics.

Zero dependencies. Unicode sparklines, box-drawing panels, ANSI color.
Designed per Auggie's review: actionable metrics > pretty boxes.
"""

import json
import os
import sys
import signal
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import term

# ═══════════════════════════════════════════════════════════════════
# Shared primitives — all live in term.py now
# ═══════════════════════════════════════════════════════════════════

ANSI = term.ANSI
BOX = term.BOX
colorize = term.colorize
sparkline = term.sparkline      # re-exported for tests and callers
bar_chart = term.bar_chart      # re-exported for tests and callers
panel = term.panel
panel_pair = term.panel_pair


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
        record_delta = None
        bm = r.get("benchmark")
        if bm:
            b = bm.get("before", {}).get("total")
            a = bm.get("after", {}).get("total")
            if isinstance(b, int) and isinstance(a, int):
                before_scores.append(b)
                after_scores.append(a)
                record_delta = a - b
                deltas.append(record_delta)

        status = r.get("status", "ok")
        if status in ("error", "failed", "timeout"):
            failures += 1

        agent = r.get("agent") or "—"
        if agent not in by_agent:
            by_agent[agent] = {"count": 0, "deltas": [], "fails": 0}
        by_agent[agent]["count"] += 1
        if status in ("error", "failed", "timeout"):
            by_agent[agent]["fails"] += 1
        # Attribute the delta only to the agent of THIS record (not the global last).
        if record_delta is not None:
            by_agent[agent]["deltas"].append(record_delta)

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

def render_dashboard(stats, use_ascii=False, show_prompts=False,
                     scroll=0, visible=8, recent_all=None,
                     live=False, return_lines=False, refresh=0):
    """Render the full dashboard.

    The Recent table is a scroll window: `recent_all[scroll:scroll+visible]`.
    `recent_all` defaults to stats' last-10 snapshot; the live view passes the
    full history so it can page through everything. With return_lines=True the
    composed rows are returned (for repositioned redraw) instead of printed.
    """
    if not stats or stats.get("total", 0) == 0:
        msg = "No enhancement data yet. Run 'pe persona' or 'pe enhance-task' to get started."
        if return_lines:
            return [msg]
        print(msg)
        return

    total_width = term.terminal_width(120)
    narrow = total_width < 80
    h = "-" if use_ascii else BOX["h"]
    out = []

    # Header — shared term.header keeps the ⚡ brand + divider consistent.
    out.extend(term.header("pe dashboard", f"v{term.VERSION}", total_width, use_ascii))

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
        tb = stats["score_trend_before"]
        ta = stats["score_trend_after"]
        n = len(ta)
        avg_b = sum(tb) / len(tb) if tb else 0
        avg_a = sum(ta) / len(ta) if ta else 0
        trend_lines = [
            f"  Last {n}:",
            f"  Before: {before_spark} → avg {avg_b:.0f}",
            f"  After:  {after_spark} → avg {avg_a:.0f}",
        ]
    else:
        trend_lines = ["  No benchmark data", "  Run 'pe benchmark --enhance ...' to see trends"]
    trend = "\n".join(trend_lines)

    out.append(panel_pair("Summary", summary, "Score Trend", trend, total_width, use_ascii))

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

    out.append(panel_pair("Agent Effectiveness (avg Δ)", agent_content, "Velocity (by day)", vel_content, total_width, use_ascii))

    # ── Row 3: Recent runs ──
    recents = recent_all if recent_all is not None else stats.get("recent", [])
    total_recent = len(recents)
    if recents:
        recent_width = total_width - 4
        header_line = f" {'When':<17} {'Agent':<10} {'Before→After':>13} {'Δ':>6} {'Status':<8} {'Seed' if show_prompts else 'ID'}"
        sep_line = h * (recent_width - 2)
        lines = [header_line, sep_line]
        window = recents[scroll:scroll + visible] if visible else []
        for r in window:
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
    out.append(panel(recent_title, recent_content, total_width - 2, "green", use_ascii))

    # Footer — honest about what the keys actually do in each mode.
    out.append(term.rule(total_width, use_ascii))
    if live:
        lo = scroll + 1 if total_recent else 0
        hi = min(scroll + visible, total_recent)
        footer_parts = [
            "[j/↓ k/↑] scroll",
            "[g/G] top/bottom",
            "[q] quit",
            f"rows {lo}–{hi} of {total_recent}",
        ]
        if refresh > 0:
            footer_parts.append(f"↻ {refresh}s")
    else:
        footer_parts = []
        if sys.stdout.isatty():
            footer_parts.append("[--ascii] no-unicode")
    if footer_parts:
        out.append(term.footer(footer_parts, use_ascii))

    if return_lines:
        return out
    print()
    print("\n".join(out))
    print()


# ═══════════════════════════════════════════════════════════════════
# Live scrollable view
# ═══════════════════════════════════════════════════════════════════

def _live_dashboard_loop(stats, recent_all, use_ascii=False, show_prompts=False,
                         refresh=0, reload_data=None):
    """Alt-screen dashboard that scrolls the Recent table through the full
    history. j/↓ and k/↑ move one row, g/G jump to top/bottom, space pages
    down, q/Esc quit. The alt screen and cursor are always restored — even
    on SIGINT/SIGTERM.

    When refresh > 0 the keypress wait times out every `refresh` seconds and
    `reload_data()` (returning (stats, recent_all)) is called to pull in new
    records, keeping the current scroll position.
    """
    out = sys.stdout
    scroll = 0

    def _restore():
        out.write(term.ALT_SCREEN_EXIT)
        out.flush()
        term.show_cursor(out)

    def _on_signal(signum, _frame):
        _restore()
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    prev_sigint = signal.signal(signal.SIGINT, _on_signal)
    prev_sigterm = signal.signal(signal.SIGTERM, _on_signal)
    out.write(term.ALT_SCREEN_ENTER)
    term.hide_cursor(out)
    try:
        while True:
            # Size the Recent window to the live terminal: render once with no
            # rows to measure fixed overhead (each row is exactly one line).
            total = len(recent_all)
            overhead = len(render_dashboard(
                stats, use_ascii, show_prompts, scroll=scroll, visible=0,
                recent_all=recent_all, live=True, return_lines=True, refresh=refresh))
            visible = max(1, term.terminal_height() - overhead - 1)
            max_scroll = max(0, total - visible)
            scroll = min(scroll, max_scroll)

            lines = render_dashboard(
                stats, use_ascii, show_prompts, scroll=scroll, visible=visible,
                recent_all=recent_all, live=True, return_lines=True, refresh=refresh)
            out.write(term.CLEAR)
            out.write("\n".join(lines))
            out.flush()

            key = term.read_key(timeout=refresh if refresh > 0 else None)
            if key is None:
                # Refresh tick: pull fresh data, keep scroll position.
                if reload_data is not None:
                    stats, recent_all = reload_data()
                continue
            if key in (term.NO_TTY, "q", "Q", "esc", "\x03", "\x04"):
                break
            elif key in ("j", "down"):
                scroll = min(scroll + 1, max_scroll)
            elif key in ("k", "up"):
                scroll = max(scroll - 1, 0)
            elif key == "g":
                scroll = 0
            elif key in ("G",):
                scroll = max_scroll
            elif key == " ":
                scroll = min(scroll + visible, max_scroll)
    finally:
        _restore()
        signal.signal(signal.SIGINT, prev_sigint)
        signal.signal(signal.SIGTERM, prev_sigterm)


# ═══════════════════════════════════════════════════════════════════
# Entry point (called from cli.py)
# ═══════════════════════════════════════════════════════════════════

def cmd_dashboard(store_path=None, agent=None, since=None, json_out=False,
                  ascii_mode=False, show_prompts=False, refresh=0):
    """Main entry point for pe dashboard."""
    # Validate --since once, up front, so the live reload path can reuse it.
    since_dt = None
    if since:
        since_dt = parse_since(since)
        if not since_dt:
            print(f"Invalid --since: {since}", file=sys.stderr)
            sys.exit(1)

    def _load():
        recs = load_records(store_path)
        if agent:
            recs = [r for r in recs if r.get("agent") == agent]
        if since_dt:
            recs = [r for r in recs
                    if datetime.fromisoformat(r.get("timestamp", "1970-01-01T00:00:00Z").replace("Z", "+00:00")) >= since_dt]
        return recs

    records = _load()
    stats = compute_stats(records)

    if json_out:
        print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))
        return

    # Detect ASCII mode
    use_ascii = ascii_mode or not sys.stdout.isatty() or os.environ.get("TERM") == "dumb"

    # Live scrollable view by default on an interactive TTY; one-shot otherwise
    # (pipes, redirects, TERM=dumb). The live view pages through full history.
    interactive = (sys.stdout.isatty() and sys.stdin.isatty()
                   and os.environ.get("TERM") != "dumb")
    if interactive and stats.get("total", 0) > 0:
        def _reload():
            recs = _load()
            return compute_stats(recs), recs[::-1]

        _live_dashboard_loop(stats, records[::-1], use_ascii, show_prompts,
                             refresh=refresh, reload_data=_reload)
    else:
        render_dashboard(stats, use_ascii=use_ascii, show_prompts=show_prompts)
