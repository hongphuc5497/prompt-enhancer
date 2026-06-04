#!/usr/bin/env python3
"""
Prompt Store — JSON Lines database for all prompt enhancements.

Every enhancement is logged as a JSON record for analytics:
  - Before/after benchmark scores
  - Token counts, duration, model used
  - Agent target, project path, profile

Storage: ~/.prompt-enhancer/store.jsonl (append-only, one record per line)

Usage:
  python3 prompt-store.py save --seed "..." --enhanced "..." [--agent claude] [--benchmark {...}]
  python3 prompt-store.py list [--limit 20] [--agent claude]
  python3 prompt-store.py show <id>
  python3 prompt-store.py stats
  python3 prompt-store.py search "security reviewer"
  python3 prompt-store.py export [--agent claude] [--since 2026-06-01] [--format json|csv]
"""

import json
import os
import sys
import uuid
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ── Config ──────────────────────────────────────────────────────────
STORE_DIR = Path.home() / ".prompt-enhancer"
STORE_FILE = STORE_DIR / "store.jsonl"


def ensure_store():
    """Ensure the store directory and file exist."""
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    if not STORE_FILE.exists():
        STORE_FILE.write_text("")


# ── Read / Write ────────────────────────────────────────────────────
def read_all() -> list[dict]:
    """Read all records from the store."""
    ensure_store()
    records = []
    for line in STORE_FILE.read_text().strip().splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def append_record(record: dict):
    """Append a single record to the store."""
    ensure_store()
    with open(STORE_FILE, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── Commands ────────────────────────────────────────────────────────
def cmd_save(args):
    """Save an enhancement to the store."""
    seed = args.seed
    enhanced = args.enhanced

    if seed == "-":
        seed = sys.stdin.read().strip()
    if enhanced == "-":
        enhanced = sys.stdin.read().strip()
    if args.seed_file:
        seed = Path(args.seed_file).expanduser().read_text().strip()
    if args.enhanced_file:
        enhanced = Path(args.enhanced_file).expanduser().read_text().strip()

    benchmark = None
    if args.benchmark:
        try:
            benchmark = json.loads(args.benchmark)
        except json.JSONDecodeError:
            benchmark_file = Path(args.benchmark).expanduser()
            if benchmark_file.exists():
                benchmark = json.loads(benchmark_file.read_text())

    record = {
        "id": str(uuid.uuid4())[:12],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seed": seed[:500],  # truncate for storage
        "seed_length": len(seed),
        "enhanced": enhanced[:5000],  # truncate for storage
        "enhanced_length": len(enhanced),
        "agent": args.agent,
        "project": args.project or str(Path.cwd()),
        "profile": args.profile,
        "benchmark": benchmark,
        "model": os.environ.get("LLM_MODEL", "unknown"),
        "duration_ms": args.duration_ms,
    }

    append_record(record)
    print(json.dumps({"saved": record["id"], "store": str(STORE_FILE)}))
    if not args.quiet:
        print(f"✅ Saved {record['id']} ({record['enhanced_length']} chars)", file=sys.stderr)


def cmd_list(args):
    """List recent enhancements."""
    records = read_all()

    # Filter
    if args.agent:
        records = [r for r in records if r.get("agent") == args.agent]
    if args.profile:
        records = [r for r in records if r.get("profile") == args.profile]
    if args.since:
        since_dt = datetime.fromisoformat(args.since)
        records = [r for r in records if datetime.fromisoformat(r["timestamp"]) >= since_dt]

    # Sort by timestamp descending
    records.sort(key=lambda r: r["timestamp"], reverse=True)

    # Limit
    limit = args.limit or len(records)
    records = records[:limit]

    if args.format == "json":
        print(json.dumps(records, indent=2, ensure_ascii=False))
        return

    # Table output
    print(f"{'ID':<14} {'When':<22} {'Agent':<10} {'Before':>6} {'After':>6} {'Delta':>5} {'Seed'}")
    print("-" * 90)
    for r in records:
        rid = r["id"]
        when = r["timestamp"][:19].replace("T", " ")
        agent = r.get("agent", "—") or "—"
        b_score = r.get("benchmark", {}).get("before", {}).get("total", "—") if r.get("benchmark") else "—"
        a_score = r.get("benchmark", {}).get("after", {}).get("total", "—") if r.get("benchmark") else "—"
        if isinstance(b_score, int) and isinstance(a_score, int):
            delta = f"+{a_score - b_score}"
        else:
            delta = "—"
        seed = r["seed"][:50].replace("\n", " ")
        print(f"{rid:<14} {when:<22} {agent:<10} {str(b_score):>6} {str(a_score):>6} {delta:>5} {seed}")


def cmd_show(args):
    """Show a specific enhancement."""
    records = read_all()
    for r in records:
        if r["id"] == args.id:
            print(json.dumps(r, indent=2, ensure_ascii=False))
            return
    print(f"Record not found: {args.id}", file=sys.stderr)
    sys.exit(1)


def cmd_stats(args):
    """Show analytics."""
    records = read_all()

    if not records:
        print("No records in store.")
        return

    total = len(records)
    with_benchmark = sum(1 for r in records if r.get("benchmark"))
    agents = {}
    profiles = {}
    models = {}

    before_scores = []
    after_scores = []
    deltas = []

    for r in records:
        agent = r.get("agent", "unknown")
        agents[agent] = agents.get(agent, 0) + 1

        profile = r.get("profile", "none")
        profiles[profile] = profiles.get(profile, 0) + 1

        model = r.get("model", "unknown")
        models[model] = models.get(model, 0) + 1

        bm = r.get("benchmark")
        if bm:
            b = bm.get("before", {}).get("total")
            a = bm.get("after", {}).get("total")
            if isinstance(b, int) and isinstance(a, int):
                before_scores.append(b)
                after_scores.append(a)
                deltas.append(a - b)

    avg_before = sum(before_scores) / len(before_scores) if before_scores else 0
    avg_after = sum(after_scores) / len(after_scores) if after_scores else 0
    avg_delta = sum(deltas) / len(deltas) if deltas else 0
    total_chars = sum(r.get("enhanced_length", 0) for r in records)

    print(f"Total enhancements:    {total}")
    print(f"With benchmarks:       {with_benchmark}/{total}")
    print(f"Total enhanced chars:  {total_chars:,}")
    print()
    print(f"Avg before score:      {avg_before:.1f}/35")
    print(f"Avg after score:       {avg_after:.1f}/35")
    print(f"Avg improvement:       +{avg_delta:.1f} ({avg_delta/max(avg_before,0.1)*100:.0f}%)")
    print()
    print("By agent:")
    for agent, count in sorted(agents.items(), key=lambda x: -x[1]):
        print(f"  {agent:<12} {count:>4}")
    print()
    if profiles and any(k and k != "none" for k in profiles):
        print("By profile:")
        for profile, count in sorted(profiles.items(), key=lambda x: -x[1]):
            if profile:
                print(f"  {profile:<12} {count:>4}")
    print()
    print("By model:")
    for model, count in sorted(models.items(), key=lambda x: -x[1]):
        print(f"  {model:<12} {count:>4}")


def cmd_search(args):
    """Search for enhancements by keyword."""
    records = read_all()
    query = args.query.lower()
    matches = []

    for r in records:
        seed = r.get("seed", "").lower()
        enhanced = r.get("enhanced", "").lower()
        if query in seed or query in enhanced:
            matches.append(r)

    if args.format == "json":
        print(json.dumps(matches, indent=2, ensure_ascii=False))
        return

    for r in matches[:args.limit or 10]:
        print(f"\n{'='*60}")
        print(f"ID: {r['id']} | {r['timestamp'][:19]} | Agent: {r.get('agent', '—')}")
        print(f"Seed: {r['seed'][:120]}")
        if r.get("benchmark"):
            bm = r["benchmark"]
            b = bm.get("before", {}).get("total", "—")
            a = bm.get("after", {}).get("total", "—")
            print(f"Score: {b}/35 → {a}/35")


def cmd_export(args):
    """Export records to a file."""
    records = read_all()

    if args.agent:
        records = [r for r in records if r.get("agent") == args.agent]
    if args.since:
        since_dt = datetime.fromisoformat(args.since)
        records = [r for r in records if datetime.fromisoformat(r["timestamp"]) >= since_dt]

    records.sort(key=lambda r: r["timestamp"], reverse=True)

    if args.format == "csv":
        import csv, io
        output = io.StringIO()
        if records:
            writer = csv.DictWriter(output, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)
        content = output.getvalue()
    else:
        content = json.dumps(records, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(content)
        print(f"Exported {len(records)} records to {args.output}")
    else:
        print(content)


# ── CLI ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Prompt Store — JSON database for prompt enhancement analytics"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # save
    p_save = sub.add_parser("save", help="Save an enhancement")
    p_save.add_argument("--seed", help="Raw prompt text (or '-' for stdin)")
    p_save.add_argument("--enhanced", help="Enhanced prompt text (or '-' for stdin)")
    p_save.add_argument("--seed-file", help="Read seed from file")
    p_save.add_argument("--enhanced-file", help="Read enhanced from file")
    p_save.add_argument("--agent", help="Target agent (claude, codex, etc.)")
    p_save.add_argument("--project", help="Project directory")
    p_save.add_argument("--profile", help="Enhancement profile used")
    p_save.add_argument("--benchmark", help="Benchmark JSON (string or file path)")
    p_save.add_argument("--duration-ms", type=int, help="Enhancement duration in ms")
    p_save.add_argument("--quiet", action="store_true", help="Suppress stderr output")

    # list
    p_list = sub.add_parser("list", help="List enhancements")
    p_list.add_argument("--limit", type=int, default=20, help="Max records")
    p_list.add_argument("--agent", help="Filter by agent")
    p_list.add_argument("--profile", help="Filter by profile")
    p_list.add_argument("--since", help="Filter since date (ISO format)")
    p_list.add_argument("--format", choices=["table", "json"], default="table")

    # show
    p_show = sub.add_parser("show", help="Show a specific enhancement")
    p_show.add_argument("id", help="Record ID")

    # stats
    sub.add_parser("stats", help="Show analytics")

    # search
    p_search = sub.add_parser("search", help="Search by keyword")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument("--format", choices=["table", "json"], default="table")

    # export
    p_export = sub.add_parser("export", help="Export records")
    p_export.add_argument("--agent", help="Filter by agent")
    p_export.add_argument("--since", help="Filter since date")
    p_export.add_argument("--format", choices=["json", "csv"], default="json")
    p_export.add_argument("--output", "-o", help="Output file")

    args = parser.parse_args()

    if args.command == "save":
        cmd_save(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "export":
        cmd_export(args)


if __name__ == "__main__":
    main()
