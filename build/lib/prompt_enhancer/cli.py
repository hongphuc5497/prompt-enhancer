#!/usr/bin/env python3
"""
prompt-enhancer CLI — unified entry point.

Usage:
    prompt-enhancer enhance "a Rust dev who likes functional style"
    prompt-enhancer install "a security reviewer" --agent claude
    prompt-enhancer benchmark --before raw.txt --after enhanced.md
    prompt-enhancer store list
    prompt-enhancer store stats
    prompt-enhancer store search "keyword"

Install:
    pip install git+https://github.com/hongphuc5497/prompt-enhancer.git
    brew install hongphuc5497/tap/prompt-enhancer
    curl -fsSL https://raw.githubusercontent.com/hongphuc5497/prompt-enhancer/main/install.sh | sh
"""

import json
import os
import sys
import time
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════

STORE_DIR = Path.home() / ".prompt-enhancer"
STORE_FILE = STORE_DIR / "store.jsonl"
PYTHON = os.environ.get("PYTHON3", sys.executable)

AGENT_CONFIGS = {
    "claude":    {"path": "CLAUDE.md", "desc": "Claude Code — auto-loaded every session"},
    "codex":     {"path": ".github/copilot-instructions.md", "desc": "Codex (OpenAI)"},
    "opencode":  {"path": "AGENTS.md", "desc": "OpenCode"},
    "cursor":    {"path": ".cursorrules", "desc": "Cursor"},
    "auggie":    {"path": "AGENTS.md", "desc": "Auggie (Augment)"},
    "copilot":   {"path": ".github/copilot-instructions.md", "desc": "GitHub Copilot"},
    "aider":     {"path": None, "desc": "Aider (prints launch command)"},
}

ENHANCEMENT_PROFILES = ["senior-dev", "architect", "reviewer", "sre", "product", "mentor"]


def load_config():
    env_file = Path.home() / ".prompt-enhancer.env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    return {
        "api_key": os.environ.get("LLM_API_KEY", ""),
        "base_url": os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"),
        "model": os.environ.get("LLM_MODEL", "deepseek-chat"),
    }


def call_llm(prompt, config, model=None, max_tokens=4096, temperature=0.7):
    url = f"{config['base_url'].rstrip('/')}/v1/chat/completions"
    body = json.dumps({
        "model": model or config["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {config['api_key']}")
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode())["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════════════════
# Store (auto-saves every enhancement)
# ═══════════════════════════════════════════════════════════════════

def store_save(seed, enhanced, agent=None, project=None, profile=None, benchmark=None, duration_ms=None):
    import uuid
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "id": str(uuid.uuid4())[:12],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed": seed[:500],
        "seed_length": len(seed),
        "enhanced": enhanced[:5000],
        "enhanced_length": len(enhanced),
        "agent": agent,
        "project": project or str(Path.cwd()),
        "profile": profile,
        "benchmark": benchmark,
        "model": os.environ.get("LLM_MODEL", "unknown"),
        "version": "1.0.0",
        "duration_ms": duration_ms,
    }
    with open(STORE_FILE, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record["id"]


def store_read():
    if not STORE_FILE.exists():
        return []
    records = []
    for line in STORE_FILE.read_text().strip().splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


# ═══════════════════════════════════════════════════════════════════
# Enhancement Engine
# ═══════════════════════════════════════════════════════════════════

ENHANCEMENT_SYSTEM_PROMPT = """You are a prompt engineer specializing in creating system prompts for AI coding agents (Claude Code, Codex, Cursor, Hermes, Copilot). Transform a rough idea into a production-quality system prompt with 7 sections.

SECTIONS: ROLE (identity) → CONTEXT (project specifics) → BEHAVIORAL RULES → TECHNICAL GUIDELINES → OUTPUT FORMAT → PITFALLS/GUARDRAILS → EXAMPLES

RULES:
- Be CONCRETE — reference actual tools, patterns, and conventions
- Be ACTIONABLE — rules must translate directly into agent behavior
- Be CONCISE — 2-4 bullets per section
- Include a "pro tip" at the end
- Output ONLY the system prompt markdown, no preamble"""


def enhance(seed, config, profile=None):
    """Enhance a rough prompt into a 7-section system prompt."""
    profile_instruction = ""
    if profile:
        profiles = {
            "senior-dev": "Focus on: technical depth, testing rigor, edge-case awareness.",
            "architect": "Focus on: system design, trade-off analysis, scalability.",
            "reviewer": "Focus on: security, performance, code smells, best-practice violations.",
            "sre": "Focus on: observability, reliability, incident response, infrastructure as code.",
            "product": "Focus on: user experience, feature prioritization, stakeholder communication.",
            "mentor": "Focus on: teaching, explanation, onboarding, pair-programming style.",
        }
        profile_instruction = f"\n\nProfile focus: {profiles.get(profile, '')}"

    prompt = f"""{ENHANCEMENT_SYSTEM_PROMPT}

## Seed prompt (rough idea)
{seed}
{profile_instruction}

## Output
Output ONLY the system prompt markdown. Start with "# System Prompt: <Role Name>"."""

    return call_llm(prompt, config, temperature=0.7)


# ═══════════════════════════════════════════════════════════════════
# Benchmark Engine (7-dim rubric)
# ═══════════════════════════════════════════════════════════════════

RUBRIC_PROMPT = """Score this prompt on 7 dimensions (1-5 each, max 35):
1. Role Clarity, 2. Context Sufficiency, 3. Instruction Specificity,
4. Format Structure, 5. Example Quality, 6. Constraint Tightness, 7. Output Validation

Return ONLY JSON:
{"role_clarity":{"score":N,"reasoning":"..."},"context_sufficiency":{"score":N,"reasoning":"..."},"instruction_specificity":{"score":N,"reasoning":"..."},"format_structure":{"score":N,"reasoning":"..."},"example_quality":{"score":N,"reasoning":"..."},"constraint_tightness":{"score":N,"reasoning":"..."},"output_validation":{"score":N,"reasoning":"..."},"total":N,"verdict":"production-ready|working-draft|needs-revision|rewrite","summary":"..."}

Prompt to score:
---PROMPT_START---
__PROMPT_TEXT__
---PROMPT_END---"""


def benchmark_score(prompt_text, config):
    judge_prompt = RUBRIC_PROMPT.replace("__PROMPT_TEXT__", prompt_text)
    result = call_llm(judge_prompt, config, temperature=0.3)
    cleaned = result.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return json.loads(cleaned)


# ═══════════════════════════════════════════════════════════════════
# CLI Commands
# ═══════════════════════════════════════════════════════════════════

def cmd_enhance(args):
    config = load_config()
    if not config["api_key"]:
        die("LLM_API_KEY not set. Run: echo 'LLM_API_KEY=sk-...' > ~/.prompt-enhancer.env")

    seed = _get_seed(args)
    profile = args.profile if hasattr(args, 'profile') else None

    t0 = time.time()
    enhanced = enhance(seed, config, profile)
    duration_ms = int((time.time() - t0) * 1000)

    # Print
    if getattr(args, 'json', False):
        print(json.dumps({"status": "ok", "seed": seed[:200], "enhanced": enhanced, "duration_ms": duration_ms}, ensure_ascii=False))
    else:
        print(enhanced)

    # Auto-save to store
    if not getattr(args, 'no_store', False):
        store_save(seed, enhanced, duration_ms=duration_ms, profile=profile)
        if not getattr(args, 'json', False):
            print(f"\n[Saved to {STORE_FILE}]", file=sys.stderr)


def cmd_install(args):
    config = load_config()
    if not config["api_key"]:
        die("LLM_API_KEY not set")

    seed = _get_seed(args)
    profile = getattr(args, 'profile', None)

    t0 = time.time()
    enhanced = enhance(seed, config, profile)
    duration_ms = int((time.time() - t0) * 1000)

    # JSON mode
    if getattr(args, 'json', False):
        print(json.dumps({"status": "ok", "seed": seed[:200], "enhanced": enhanced, "agent": args.agent, "duration_ms": duration_ms}, ensure_ascii=False))
        if not getattr(args, 'no_store', False):
            store_save(seed, enhanced, args.agent, getattr(args, 'project', str(Path.cwd())), profile, duration_ms=duration_ms)
        return

    # Write to agent config
    agents = list(AGENT_CONFIGS.keys()) if args.agent == "all" else [args.agent]
    for agent in agents:
        if args.agent == "all" and agent == "aider":
            continue
        cfg = AGENT_CONFIGS.get(agent, {})
        if agent == "aider":
            persona = Path(getattr(args, 'project', Path.cwd())) / ".aider-persona.md"
            if not getattr(args, 'dry_run', False):
                persona.write_text(enhanced)
            print(f"aider --system-prompt \"$(cat {persona})\"")
        else:
            target = Path(getattr(args, 'project', Path.cwd())) / cfg["path"]
            comment = {"claude": "# CLAUDE.md\n", "codex": "<!-- prompt-enhancer -->\n", "cursor": "// prompt-enhancer\n"}.get(agent, "")
            if getattr(args, 'dry_run', False):
                print(f"Would write: {target}")
            else:
                target.write_text(comment + enhanced + "\n")
                print(f"✅ {target} ({len(enhanced)} chars) — {cfg['desc']}")

    if not getattr(args, 'no_store', False) and not getattr(args, 'dry_run', False):
        store_save(seed, enhanced, args.agent, getattr(args, 'project', str(Path.cwd())), profile, duration_ms=duration_ms)


def cmd_benchmark(args):
    config = load_config()
    if not config["api_key"]:
        die("LLM_API_KEY not set")

    before_text = args.before
    after_text = args.after

    if args.enhance:
        t0 = time.time()
        enhanced = enhance(args.enhance, config)
        duration_ms = int((time.time() - t0) * 1000)
        before_scores = benchmark_score(args.enhance, config)
        after_scores = benchmark_score(enhanced, config)
        store_save(args.enhance, enhanced, benchmark={"before": before_scores, "after": after_scores}, duration_ms=duration_ms)
    else:
        before_text = Path(before_text).expanduser().read_text() if before_text and Path(before_text).exists() else (before_text or "")
        after_text = Path(after_text).expanduser().read_text() if after_text and Path(after_text).exists() else (after_text or "")
        before_scores = benchmark_score(before_text, config) if before_text else None
        after_scores = benchmark_score(after_text, config) if after_text else None

    if getattr(args, 'json', False):
        out = {}
        if before_scores: out["before"] = before_scores
        if after_scores: out["after"] = after_scores
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    # Pretty print
    BAR = "═" * 60
    dims = [
        ("role_clarity", "Role Clarity"), ("context_sufficiency", "Context Sufficiency"),
        ("instruction_specificity", "Instruction Specificity"), ("format_structure", "Format Structure"),
        ("example_quality", "Example Quality"), ("constraint_tightness", "Constraint Tightness"),
        ("output_validation", "Output Validation"),
    ]
    print(f"\n{BAR}\n  PROMPT QUALITY BENCHMARK — SurePrompts 7-Dimension Rubric\n{BAR}")
    if before_scores:
        print(f"\n  BEFORE:  {before_scores.get('total','?')}/35  ({before_scores.get('verdict','?')})")
    if after_scores:
        print(f"  AFTER:   {after_scores.get('total','?')}/35  ({after_scores.get('verdict','?')})")
    if before_scores and after_scores:
        delta = after_scores.get("total", 0) - before_scores.get("total", 0)
        pct = (delta / max(before_scores.get("total", 1), 1)) * 100
        print(f"  DELTA:   {'↑' if delta > 0 else '↓' if delta < 0 else '→'}{abs(delta)} points ({pct:+.0f}%)\n")
    print(f"  {'Dimension':<28} {'BEFORE':>7} {'AFTER':>7} {'Δ':>5}\n  {'-'*28} {'-'*7} {'-'*7} {'-'*5}")
    for key, label in dims:
        b_s = before_scores.get(key, {}).get("score", "—") if before_scores else "—"
        a_s = after_scores.get(key, {}).get("score", "—") if after_scores else "—"
        if isinstance(b_s, int) and isinstance(a_s, int):
            d = a_s - b_s
            print(f"  {label:<28} {str(b_s):>7} {str(a_s):>7} {'+' + str(d) if d > 0 else str(d):>5}")
        else:
            print(f"  {label:<28} {str(b_s):>7} {str(a_s):>7} {'—':>5}")
    print(f"\n{BAR}")


def cmd_store(args):
    action = args.store_action
    if action == "list":
        records = store_read()
        records.sort(key=lambda r: r["timestamp"], reverse=True)
        limit = getattr(args, 'limit', 20) or 20
        records = records[:limit]
        if getattr(args, 'json', False):
            print(json.dumps(records, indent=2, ensure_ascii=False))
            return
        print(f"{'ID':<14} {'When':<22} {'Agent':<10} {'Seed'}")
        print("-" * 70)
        for r in records:
            print(f"{r['id']:<14} {r['timestamp'][:19]:<22} {(r.get('agent') or '—'):<10} {r['seed'][:60].replace(chr(10),' ')}")
    elif action == "stats":
        records = store_read()
        if not records:
            print("No records.")
            return
        total = len(records)
        agents = {}
        for r in records:
            a = r.get("agent") or "—"
            agents[a] = agents.get(a, 0) + 1
        total_chars = sum(r.get("enhanced_length", 0) for r in records)
        with_bench = sum(1 for r in records if r.get("benchmark"))
        print(f"Total enhancements:  {total}")
        print(f"With benchmarks:     {with_bench}")
        print(f"Total chars stored:  {total_chars:,}")
        print(f"\nBy agent:")
        for agent, count in sorted(agents.items(), key=lambda x: -x[1]):
            print(f"  {agent:<12} {count:>4}")
    elif action == "search":
        query = args.query.lower()
        records = store_read()
        matches = [r for r in records if query in (r.get("seed","") + r.get("enhanced","")).lower()]
        if getattr(args, 'json', False):
            print(json.dumps(matches, indent=2, ensure_ascii=False))
            return
        for r in matches[:10]:
            print(f"\n{'='*60}\nID: {r['id']} | {r['timestamp'][:19]} | Agent: {r.get('agent','—')}")
            print(f"Seed: {r['seed'][:120]}")
    elif action == "export":
        records = store_read()
        if getattr(args, 'format', 'json') == "csv":
            import csv, io
            output = io.StringIO()
            if records:
                w = csv.DictWriter(output, fieldnames=records[0].keys())
                w.writeheader()
                w.writerows(records)
            print(output.getvalue())
        else:
            print(json.dumps(records, indent=2, ensure_ascii=False))
    elif action == "show":
        records = store_read()
        rid = args.id
        for r in records:
            if r["id"] == rid:
                print(json.dumps(r, indent=2, ensure_ascii=False))
                return
        die(f"Record not found: {rid}")


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _get_seed(args):
    if getattr(args, 'file', None):
        return Path(args.file).expanduser().read_text().strip()
    if args.seed == "-":
        return sys.stdin.read().strip()
    return args.seed


def die(msg):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════
# Main CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Prompt Enhancer — reverse-engineered from Auggie Ctrl+P")
    sub = parser.add_subparsers(dest="command")

    # enhance
    p_enh = sub.add_parser("enhance", help="Enhance a rough prompt idea into a system prompt")
    p_enh.add_argument("seed", nargs="?", help="Rough prompt idea (or '-' for stdin)")
    p_enh.add_argument("--file", "-f", help="Read seed from file")
    p_enh.add_argument("--profile", "-p", choices=ENHANCEMENT_PROFILES, help="Enhancement style")
    p_enh.add_argument("--json", action="store_true", help="JSON output for agent consumption")
    p_enh.add_argument("--no-store", action="store_true", help="Skip saving to analytics store")

    # install
    p_inst = sub.add_parser("install", help="Install enhanced prompt into an agent's config")
    p_inst.add_argument("seed", nargs="?", help="Rough prompt idea (or '-' for stdin)")
    p_inst.add_argument("--file", "-f", help="Read seed from file")
    p_inst.add_argument("--agent", "-a", required=True, choices=list(AGENT_CONFIGS.keys()) + ["all"], help="Target agent")
    p_inst.add_argument("--project", default=str(Path.cwd()), help="Project directory")
    p_inst.add_argument("--profile", "-p", choices=ENHANCEMENT_PROFILES, help="Enhancement style")
    p_inst.add_argument("--dry-run", action="store_true", help="Preview without writing")
    p_inst.add_argument("--json", action="store_true", help="JSON output for agent consumption")
    p_inst.add_argument("--no-store", action="store_true", help="Skip saving to analytics store")

    # benchmark
    p_bench = sub.add_parser("benchmark", help="Score prompts on 7-dimension rubric")
    p_bench.add_argument("--before", help="Path to raw/before prompt")
    p_bench.add_argument("--after", help="Path to enhanced/after prompt")
    p_bench.add_argument("--enhance", help="Enhance a seed and benchmark both (all-in-one)")
    p_bench.add_argument("--json", action="store_true", help="JSON output")

    # store
    p_store = sub.add_parser("store", help="Analytics store commands")
    p_store_sub = p_store.add_subparsers(dest="store_action")
    p_store_list = p_store_sub.add_parser("list", help="List recent enhancements")
    p_store_list.add_argument("--limit", type=int, default=20)
    p_store_list.add_argument("--json", action="store_true")
    p_store_stats = p_store_sub.add_parser("stats", help="Show analytics")
    p_store_search = p_store_sub.add_parser("search", help="Search by keyword")
    p_store_search.add_argument("query")
    p_store_search.add_argument("--json", action="store_true")
    p_store_show = p_store_sub.add_parser("show", help="Show a specific record")
    p_store_show.add_argument("id")
    p_store_export = p_store_sub.add_parser("export", help="Export records")
    p_store_export.add_argument("--format", choices=["json", "csv"], default="json")

    # version
    sub.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "enhance":
        cmd_enhance(args)
    elif args.command == "install":
        cmd_install(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "store":
        if not args.store_action:
            parser.parse_args(["store", "--help"])
        else:
            cmd_store(args)
    elif args.command == "version":
        print("prompt-enhancer 1.0.0")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
