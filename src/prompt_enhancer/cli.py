#!/usr/bin/env python3
"""
prompt-enhancer CLI — unified entry point (v1.2.0).

Usage:
    pe persona "a Rust dev who likes functional style"     # 7-section persistent system prompt
    pe enhance-task "fix the login bug"                    # inline task refinement
    pe install "a security reviewer" --agent claude         # safe install with backup
    pe benchmark --enhance "a Go backend dev"               # benchmark before/after
    pe store stats                                          # analytics
    pe doctor                                               # health check

Install:
    pip install git+https://github.com/hongphuc5497/prompt-enhancer.git
    brew install hongphuc5497/tap/prompt-enhancer
    curl -fsSL https://raw.githubusercontent.com/hongphuc5497/prompt-enhancer/main/install.sh | sh
"""

import json
import os
import sys
import time
import shutil
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

from . import __version__ as VERSION
from . import term

# ═══════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════

STORE_DIR = Path.home() / ".prompt-enhancer"
STORE_FILE = STORE_DIR / "store.jsonl"

AGENT_CONFIGS = {
    "claude":    {"path": "CLAUDE.md", "desc": "Claude Code — auto-loaded every session"},
    "codex":     {"path": ".codex/system.md", "desc": "Codex CLI — system-level instructions"},
    "opencode":  {"path": "AGENTS.md", "desc": "OpenCode"},
    "cursor":    {"path": ".cursorrules", "desc": "Cursor"},
    "auggie":    {"path": "AGENTS.md", "desc": "Auggie (Augment)"},
    "copilot":   {"path": ".github/copilot-instructions.md", "desc": "GitHub Copilot"},
    "aider":     {"path": None, "desc": "Aider (prints launch command)"},
}

PROFILES = ["senior-dev", "architect", "reviewer", "sre", "product", "mentor"]

CONTEXT_PATTERNS = ["AGENTS.md", "CLAUDE.md", ".cursorrules", ".github/copilot-instructions.md"]
STACK_SIGNALS = ["package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Makefile", "docker-compose.yml"]


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


# ═══════════════════════════════════════════════════════════════════
# Workspace Context (Auggie's #1 blocker fix)
# ═══════════════════════════════════════════════════════════════════

def collect_context(project_dir, max_content=2000):
    """Discover and read project context files. Mirrors Auggie's workspace awareness."""
    cwd = Path(project_dir).resolve()
    context_parts = []

    # Context files (AGENTS.md, CLAUDE.md, etc.)
    for pattern in CONTEXT_PATTERNS:
        for found in cwd.rglob(pattern):
            try:
                content = found.read_text()
                if len(content) > max_content:
                    content = content[:max_content] + "\n... (truncated)"
                context_parts.append(f"## {found.name}\n```\n{content}\n```")
            except (PermissionError, OSError):
                continue
            break  # only first match per pattern

    # Stack signals (package.json, Cargo.toml, etc.)
    for signal in STACK_SIGNALS:
        path = cwd / signal
        if path.exists():
            try:
                content = path.read_text()
                if len(content) > max_content:
                    content = content[:max_content] + "\n... (truncated)"
                context_parts.append(f"## {signal} (tech stack)\n```\n{content}\n```")
            except (PermissionError, OSError):
                continue

    return "\n\n".join(context_parts)


# ═══════════════════════════════════════════════════════════════════
# LLM
# ═══════════════════════════════════════════════════════════════════

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
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode())
            if "choices" not in result:
                raise ValueError(f"Unexpected API response: {json.dumps(result)[:200]}")
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        die(f"API error ({e.code}): {body}")
    except urllib.error.URLError as e:
        die(f"Connection error: {e.reason}")
    except json.JSONDecodeError:
        die("API returned invalid JSON. Check your LLM_BASE_URL.")
    except Exception as e:
        die(f"LLM call failed: {e}")


# ═══════════════════════════════════════════════════════════════════
# Store
# ═══════════════════════════════════════════════════════════════════

STORE_INITIALIZED = False

def store_init():
    """Show first-run privacy notice."""
    global STORE_INITIALIZED
    if STORE_INITIALIZED:
        return
    STORE_INITIALIZED = True
    marker = STORE_DIR / ".initialized"
    if not marker.exists():
        print("📊 Prompt Enhancer stores enhancement history locally.", file=sys.stderr)
        print(f"   Data saved to: {STORE_FILE}", file=sys.stderr)
        print("   Use 'pe store delete <id>' or 'pe store clear' to manage.", file=sys.stderr)
        print("   Use --no-store to skip saving. See README for details.", file=sys.stderr)
        print("", file=sys.stderr)
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        marker.write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ"))


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
        "version": VERSION,
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


def store_delete(record_id):
    records = store_read()
    before = len(records)
    records = [r for r in records if r["id"] != record_id]
    after = len(records)
    if before == after:
        return False
    STORE_FILE.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")
    return True


def store_clear():
    if STORE_FILE.exists():
        STORE_FILE.write_text("")
    return True


# ═══════════════════════════════════════════════════════════════════
# Persona Engine (7-section system prompt)
# ═══════════════════════════════════════════════════════════════════

PERSONA_PROMPT = """You are a prompt engineer. Transform a rough persona idea into a production-quality system prompt with 7 sections.

SECTIONS: ROLE (identity) → CONTEXT (project specifics) → BEHAVIORAL RULES → TECHNICAL GUIDELINES → OUTPUT FORMAT → PITFALLS/GUARDRAILS → EXAMPLES

RULES:
- Be CONCRETE — reference actual tools, patterns, and conventions from the workspace context
- Be ACTIONABLE — rules must translate directly into agent behavior
- Be CONCISE — 2-4 bullets per section
- Include a short "pro tip" at the end
- Output ONLY the system prompt markdown, no preamble"""


def persona(seed, config, workspace_context="", profile=None, concise=False):
    """Generate a 7-section system prompt."""
    profile_instruction = ""
    if profile:
        profiles = {
            "senior-dev": "Focus: technical depth, testing rigor, edge-case awareness.",
            "architect": "Focus: system design, trade-off analysis, scalability.",
            "reviewer": "Focus: security, performance, code smells, best-practices.",
            "sre": "Focus: observability, reliability, incident response, IaC.",
            "product": "Focus: user experience, feature prioritization, stakeholders.",
            "mentor": "Focus: teaching, explanation, onboarding, pair-programming.",
        }
        profile_instruction = f"\n\nProfile: {profiles.get(profile, '')}"

    concise_note = "\n\nMake this brief — 1-2 bullets per section. Skip EXAMPLES if zero-shot is viable." if concise else ""
    context_block = f"\n\n## Workspace context\n{workspace_context}" if workspace_context else ""

    prompt = f"""{PERSONA_PROMPT}{concise_note}

## Seed (rough persona idea)
{seed}
{profile_instruction}
{context_block}

## Output
Output ONLY the system prompt markdown. Start with "# System Prompt: <Role Name>"."""

    return call_llm(prompt, config, temperature=0.7)


# ═══════════════════════════════════════════════════════════════════
# Task Enhancer (inline — Auggie-style)
# ═══════════════════════════════════════════════════════════════════

TASK_ENHANCE_PROMPT = """You are a prompt enhancer for AI coding agents. Transform a vague task request into a clear, actionable prompt.

RULES:
- Add relevant file references and context from the workspace
- Structure the task into clear steps
- Include relevant coding conventions and patterns
- Ask clarifying questions if the task is ambiguous
- Keep it concise — 3-5 sentences
- Output ONLY the enhanced task prompt, no preamble"""


def enhance_task(seed, config, workspace_context=""):
    """Inline task refinement — like Auggie's Ctrl+P."""
    context_block = f"\n\n## Workspace context\n{workspace_context}" if workspace_context else ""
    prompt = f"""{TASK_ENHANCE_PROMPT}{context_block}

## Raw task request
{seed}

## Output
Output ONLY the enhanced task prompt."""

    return call_llm(prompt, config, temperature=0.5)


# ═══════════════════════════════════════════════════════════════════
# Benchmark Engine
# ═══════════════════════════════════════════════════════════════════

RUBRIC_PROMPT = """Score this prompt on 7 dimensions (1-5 each, max 35):
1. Role Clarity, 2. Context Sufficiency, 3. Instruction Specificity,
4. Format Structure, 5. Example Quality, 6. Constraint Tightness, 7. Output Validation

Return ONLY JSON:
{"role_clarity":{"score":N,"reasoning":"1 sentence"},"context_sufficiency":{"score":N,"reasoning":"1 sentence"},"instruction_specificity":{"score":N,"reasoning":"1 sentence"},"format_structure":{"score":N,"reasoning":"1 sentence"},"example_quality":{"score":N,"reasoning":"1 sentence"},"constraint_tightness":{"score":N,"reasoning":"1 sentence"},"output_validation":{"score":N,"reasoning":"1 sentence"},"total":N,"verdict":"production-ready|working-draft|needs-revision|rewrite","summary":"1-2 sentence assessment"}

Prompt to score:
---PROMPT_START---
__PROMPT_TEXT__
---PROMPT_END---"""


def benchmark_score(prompt_text, config, judge_via=None, judge_model=None):
    """Score a prompt with the 7-dimension rubric.

    Blind judging: pass judge_via=<agent> to route the rubric prompt through a
    different agent CLI than the one used to generate the prompt. judge_model
    overrides the API model name (ignored when judge_via is set).
    """
    judge_prompt = RUBRIC_PROMPT.replace("__PROMPT_TEXT__", prompt_text)
    if judge_via:
        from . import agents as agent_mod
        result = agent_mod.run_via_agent(judge_prompt, judge_via)
    else:
        result = call_llm(judge_prompt, config, model=judge_model, temperature=0.3)
    cleaned = result.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    # Some agent CLIs wrap output in extra prose — extract first JSON object.
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            cleaned = cleaned[start:end + 1]
    return json.loads(cleaned)


# ═══════════════════════════════════════════════════════════════════
# CLI Commands
# ═══════════════════════════════════════════════════════════════════

def cmd_persona(args):
    """pe persona — generate 7-section system prompt."""
    via = getattr(args, 'via', None)
    seed = _get_seed(args)
    if not seed:
        die("Provide a seed prompt. Usage: pe persona 'a senior Rust developer...'")

    from . import view

    if via:
        # Delegate to existing agent — no API key needed
        from . import agents
        view.log_progress(f"Delegating to {via}...")
        with view.Spinner(f"Enhancing via {via}"):
            enhanced = agents.enhance(seed, via_agent=via)
    else:
        config = load_config()
        if not config["api_key"]:
            die("LLM_API_KEY not set. Use --via <agent> or set API key.")
        profile = getattr(args, 'profile', None)
        project = getattr(args, 'project', str(Path.cwd()))
        workspace = collect_context(project) if not getattr(args, 'no_context', False) else ""
        concise = getattr(args, 'concise', False)
        view.log_progress("Calling LLM API...")
        with view.Spinner("Enhancing with LLM"):
            t0 = time.time()
            enhanced = persona(seed, config, workspace, profile, concise)
            duration_ms = int((time.time() - t0) * 1000)

    profile = getattr(args, 'profile', None)
    project = getattr(args, 'project', str(Path.cwd()))

    # Output: rich viewer or raw
    if getattr(args, 'json', False):
        print(json.dumps({"status": "ok", "seed": seed[:200], "enhanced": enhanced, "via": via, "duration_ms": 0}, ensure_ascii=False))
    elif getattr(args, 'raw', False) or not sys.stdout.isatty():
        print(enhanced)
    else:
        view.render_prompt(enhanced, agent=via)

    # Save to store
    if not getattr(args, 'no_store', False):
        store_init()
        store_save(seed, enhanced, via or None, project, profile)
        if not getattr(args, 'json', False) and not getattr(args, 'raw', False):
            view.log_progress(f"Saved to store")

    # Copy to clipboard
    if getattr(args, 'copy', False):
        if copy_to_clipboard(enhanced):
            print("[Copied to clipboard]", file=sys.stderr)
        else:
            print("[Clipboard unavailable — install xclip/wl-clipboard on Linux]", file=sys.stderr)


def cmd_enhance_task(args):
    """pe enhance-task — inline task refinement."""
    via = getattr(args, 'via', None)
    seed = _get_seed(args)
    if not seed:
        die("Provide a task. Usage: pe enhance-task 'fix the login bug'")

    from . import view

    if via:
        from . import agents
        view.log_progress(f"Delegating to {via}...")
        with view.Spinner(f"Enhancing via {via}"):
            enhanced = agents.enhance(seed, via_agent=via)
    else:
        config = load_config()
        if not config["api_key"]:
            die("LLM_API_KEY not set. Use --via <agent> or set API key.")
        project = getattr(args, 'project', str(Path.cwd()))
        workspace = collect_context(project) if not getattr(args, 'no_context', False) else ""
        view.log_progress("Calling LLM API...")
        with view.Spinner("Enhancing task with LLM"):
            t0 = time.time()
            enhanced = enhance_task(seed, config, workspace)
            duration_ms = int((time.time() - t0) * 1000)

    # Output
    if getattr(args, 'json', False):
        print(json.dumps({"status": "ok", "seed": seed[:200], "enhanced": enhanced, "via": via}, ensure_ascii=False))
    elif getattr(args, 'raw', False) or not sys.stdout.isatty():
        print(enhanced)
    else:
        view.render_prompt(enhanced, agent=via)

    # Save
    if not getattr(args, 'no_store', False):
        store_init()
        store_save(seed, enhanced, duration_ms=0, project=getattr(args, 'project', str(Path.cwd())))

    # Clipboard
    if getattr(args, 'copy', False):
        if copy_to_clipboard(enhanced):
            print("[Copied to clipboard]", file=sys.stderr)


def cmd_install(args):
    """pe install — safe install with backup and diff."""
    config = load_config()
    if not config["api_key"]:
        die("LLM_API_KEY not set")

    seed = _get_seed(args)
    if not seed:
        die("Provide a seed. Usage: pe install 'a security reviewer' --agent claude")

    profile = getattr(args, 'profile', None)
    project = getattr(args, 'project', str(Path.cwd()))
    workspace = collect_context(project) if not getattr(args, 'no_context', False) else ""

    t0 = time.time()
    enhanced = persona(seed, config, workspace, profile)
    duration_ms = int((time.time() - t0) * 1000)

    if getattr(args, 'json', False):
        print(json.dumps({"status": "ok", "seed": seed[:200], "enhanced": enhanced, "agent": args.agent, "duration_ms": duration_ms}, ensure_ascii=False))
        if not getattr(args, 'no_store', False) and not getattr(args, 'dry_run', False):
            store_init()
            store_save(seed, enhanced, args.agent, project, profile, duration_ms=duration_ms)
        return

    agents = list(AGENT_CONFIGS.keys()) if args.agent == "all" else [args.agent]
    for agent in agents:
        if agent == "aider":
            persona_file = Path(project) / ".aider-persona.md"
            if not getattr(args, 'dry_run', False):
                persona_file.write_text(enhanced)
            print(f"aider --system-prompt \"$(cat {persona_file})\"")
            continue

        cfg = AGENT_CONFIGS.get(agent, {})
        target = Path(project) / cfg["path"]

        # Dry run: show everything
        if getattr(args, 'dry_run', False):
            print(f"Target: {target}")
            print(f"  Exists: {'yes' if target.exists() else 'no (will create)'}")
            print(f"  Parent dir: {'exists' if target.parent.exists() else 'would create'}")
            print(f"  Content ({len(enhanced)} chars):\n---\n{enhanced[:500]}...\n---")
            continue

        # Force overwrite (no backup)
        if getattr(args, 'force', False):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(enhanced + "\n")
            print(f"✅ {target} ({len(enhanced)} chars) — {cfg['desc']}")
            continue

        # Safe write: backup + overwrite
        if target.exists():
            backup = target.with_suffix(target.suffix + ".bak")
            shutil.copy2(target, backup)
            print(f"📦 Backed up to {backup}", file=sys.stderr)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(enhanced + "\n")
        print(f"✅ {target} ({len(enhanced)} chars) — {cfg['desc']}")

    if not getattr(args, 'no_store', False) and not getattr(args, 'dry_run', False):
        store_init()
        store_save(seed, enhanced, args.agent, project, profile, duration_ms=duration_ms)


def cmd_benchmark(args):
    config = load_config()
    judge_via = getattr(args, 'judge_via', None)
    judge_model = getattr(args, 'judge_model', None)
    # API key only required when we still need it: --enhance always uses the API
    # for generation; scoring uses the API only if no judge_via override.
    needs_api = bool(args.enhance) or not judge_via
    if needs_api and not config["api_key"]:
        die("LLM_API_KEY not set (or pass --judge-via to score without an API key)")

    def _score(text):
        return benchmark_score(text, config, judge_via=judge_via, judge_model=judge_model)

    if args.enhance:
        seed = args.enhance
        project = getattr(args, 'project', str(Path.cwd()))
        workspace = collect_context(project) if not getattr(args, 'no_context', False) else ""
        t0 = time.time()
        enhanced = persona(seed, config, workspace)
        duration_ms = int((time.time() - t0) * 1000)
        before_scores = _score(seed)
        after_scores = _score(enhanced)
        store_init()
        store_save(
            seed, enhanced,
            benchmark={
                "before": before_scores,
                "after": after_scores,
                "judge": {"via": judge_via, "model": judge_model} if (judge_via or judge_model) else None,
            },
            duration_ms=duration_ms,
            project=project,
        )
    else:
        before_text = args.before or ""
        after_text = args.after or ""
        if before_text and Path(before_text).expanduser().exists():
            before_text = Path(before_text).expanduser().read_text()
        if after_text and Path(after_text).expanduser().exists():
            after_text = Path(after_text).expanduser().read_text()
        if not before_text and not after_text:
            die("Provide --before/--after or use --enhance")
        before_scores = _score(before_text) if before_text else None
        after_scores = _score(after_text) if after_text else None

    if getattr(args, 'json', False):
        out = {}
        if before_scores: out["before"] = before_scores
        if after_scores: out["after"] = after_scores
        if judge_via or judge_model:
            out["judge"] = {"via": judge_via, "model": judge_model}
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    width = term.terminal_width()
    dims = [
        ("role_clarity", "Role Clarity"), ("context_sufficiency", "Context Sufficiency"),
        ("instruction_specificity", "Instruction Specificity"), ("format_structure", "Format Structure"),
        ("example_quality", "Example Quality"), ("constraint_tightness", "Constraint Tightness"),
        ("output_validation", "Output Validation"),
    ]
    print()
    for line in term.header("pe benchmark — 7-dimension rubric", f"v{VERSION}", width):
        print(line)
    if judge_via or judge_model:
        judge_label = judge_via or (judge_model and f"model={judge_model}") or "default"
        gen_label = "API" if args.enhance else "input"
        print(f"  judge: {judge_label}   generator: {gen_label}")
    if before_scores:
        print(f"\n  BEFORE:  {before_scores.get('total','?')}/35  ({before_scores.get('verdict','?')})")
    if after_scores:
        print(f"  AFTER:   {after_scores.get('total','?')}/35  ({after_scores.get('verdict','?')})")
    if before_scores and after_scores:
        delta = after_scores.get("total", 0) - before_scores.get("total", 0)
        pct = (delta / max(before_scores.get("total", 1), 1)) * 100
        s = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        print(f"  DELTA:   {s}{abs(delta)} points ({pct:+.0f}%)\n")
    print(f"  {'Dimension':<28} {'BEFORE':>7} {'AFTER':>7} {'Δ':>5}\n  {'-'*28} {'-'*7} {'-'*7} {'-'*5}")
    for key, label in dims:
        b_s = before_scores.get(key, {}).get("score", "—") if before_scores else "—"
        a_s = after_scores.get(key, {}).get("score", "—") if after_scores else "—"
        if isinstance(b_s, int) and isinstance(a_s, int):
            d = a_s - b_s
            print(f"  {label:<28} {str(b_s):>7} {str(a_s):>7} {'+' + str(d) if d > 0 else str(d):>5}")
        else:
            print(f"  {label:<28} {str(b_s):>7} {str(a_s):>7} {'—':>5}")
    print()
    print(term.rule(width))


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
        for r in records:
            if r["id"] == args.id:
                print(json.dumps(r, indent=2, ensure_ascii=False))
                return
        die(f"Record not found: {args.id}")
    elif action == "delete":
        if store_delete(args.id):
            print(f"✅ Deleted {args.id}")
        else:
            die(f"Record not found: {args.id}")
    elif action == "clear":
        if store_clear():
            print("✅ Store cleared")
    else:
        die(f"Unknown store action: {action}")


def cmd_doctor(args):
    """pe doctor — health check."""
    config = load_config()
    checks = []

    # Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks.append(("Python >= 3.12", sys.version_info >= (3, 12), py_ver))

    # Config
    api_set = bool(config["api_key"])
    checks.append(("API key set", api_set, "LLM_API_KEY" if api_set else "not set"))

    # Store
    store_exists = STORE_FILE.exists()
    checks.append(("Store", store_exists, str(STORE_FILE) if store_exists else "no records yet"))

    # Agent configs present
    for name, cfg in AGENT_CONFIGS.items():
        if cfg["path"]:
            target = Path.cwd() / cfg["path"]
            checks.append((f"Agent: {name}", target.exists(), str(target) if target.exists() else "not found in CWD"))

    # LLM connectivity (only if key set)
    if api_set:
        try:
            import urllib.request
            url = f"{config['base_url'].rstrip('/')}/v1/models"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {config['api_key']}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                models = len(data.get("data", [])) if isinstance(data, dict) else "ok"
            checks.append(("LLM connectivity", True, f"{models} models"))
        except Exception as e:
            checks.append(("LLM connectivity", False, str(e)[:60]))

    # Agent binaries (--via support)
    from . import agents as agent_mod
    for agent, binary, status in agent_mod.get_available_agents():
        checks.append((f"Agent: {agent}", status == "ready", binary or status))

    # Print
    width = term.terminal_width()
    print()
    for line in term.header("pe doctor — health check", f"v{VERSION}", width):
        print(line)
    for name, ok, detail in checks:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name:<22} {detail}")
    print(term.rule(width))

    all_ok = all(ok for _, ok, _ in checks)
    status = (term.colorize("Healthy", "green", bold=True) if all_ok
              else term.colorize("Issues found", "red", bold=True))
    print(f"  Overall: {'✅' if all_ok else '❌'} {status}")


def cmd_lint(args):
    """pe lint — static analysis of a system prompt (no LLM)."""
    from . import lint as lint_mod
    # Read from --file, positional path, stdin ('-'), or assume positional is inline text
    target = getattr(args, 'target', None)
    if getattr(args, 'file', None):
        path = Path(args.file).expanduser()
        if not path.exists():
            die(f"File not found: {path}")
        text = path.read_text()
    elif target == "-":
        text = sys.stdin.read()
    elif target and Path(target).expanduser().exists():
        text = Path(target).expanduser().read_text()
    elif target:
        text = target
    else:
        die("Provide a file path, inline text, or '-' for stdin")

    findings = lint_mod.lint(text)
    score_value = lint_mod.score(findings)

    if getattr(args, 'json', False):
        print(json.dumps({"score": score_value, "findings": findings}, indent=2, ensure_ascii=False))
    else:
        use_color = sys.stdout.isatty() and not getattr(args, 'no_color', False)
        print(lint_mod.format_report(findings, score_value, color=use_color))

    # Exit non-zero if any error-level finding so CI can gate on it
    if any(f["severity"] == "error" for f in findings):
        sys.exit(2)


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _get_seed(args):
    if getattr(args, 'file', None):
        path = Path(args.file).expanduser()
        if not path.exists():
            die(f"File not found: {path}")
        return path.read_text().strip()
    seed = args.seed
    if seed and seed == "-":
        return sys.stdin.read().strip()
    return seed


def die(msg):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def copy_to_clipboard(text):
    """Copy text to system clipboard. Returns True on success."""
    import platform
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        elif system == "Linux":
            if shutil.which("wl-copy"):
                subprocess.run(["wl-copy"], input=text.encode(), check=True)
            elif shutil.which("xclip"):
                subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
            else:
                return False
        else:
            return False
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════
# Main CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description=f"pe — Prompt Enhancer v{VERSION}",
        epilog="GitHub: https://github.com/hongphuc5497/prompt-enhancer"
    )
    sub = parser.add_subparsers(dest="command")

    # persona (new name for enhance — 7-section system prompts)
    p_pers = sub.add_parser("persona", help="Generate a 7-section persistent system prompt",
                           aliases=["enhance"])  # backward compat
    p_pers.add_argument("seed", nargs="?", help="Rough persona idea (or '-' for stdin)")
    p_pers.add_argument("--file", "-f", help="Read seed from file")
    p_pers.add_argument("--profile", "-p", choices=PROFILES, help="Enhancement style")
    p_pers.add_argument("--project", default=str(Path.cwd()), help="Project for context discovery")
    p_pers.add_argument("--no-context", action="store_true", help="Skip workspace context")
    p_pers.add_argument("--concise", action="store_true", help="Shorter output (1-2 bullets/section)")
    p_pers.add_argument("--json", action="store_true", help="JSON output")
    p_pers.add_argument("--no-store", action="store_true", help="Skip saving to store")
    p_pers.add_argument("--via", choices=["claude", "codex", "auggie", "opencode"], help="Delegate to existing agent (no API key needed)")
    p_pers.add_argument("--copy", "-c", action="store_true", help="Copy enhanced output to clipboard")
    p_pers.add_argument("--raw", action="store_true", help="Raw text output (skip styled terminal UI)")

    # enhance-task (new — inline task refinement, Auggie-style)
    p_task = sub.add_parser("enhance-task", help="Inline task refinement (like Auggie Ctrl+P)")
    p_task.add_argument("seed", nargs="?", help="Task description (or '-' for stdin)")
    p_task.add_argument("--file", "-f", help="Read seed from file")
    p_task.add_argument("--project", default=str(Path.cwd()), help="Project for context")
    p_task.add_argument("--no-context", action="store_true")
    p_task.add_argument("--json", action="store_true")
    p_task.add_argument("--no-store", action="store_true")
    p_task.add_argument("--via", choices=["claude", "codex", "auggie", "opencode"], help="Delegate to existing agent")
    p_task.add_argument("--copy", "-c", action="store_true", help="Copy enhanced output to clipboard")

    # install (safe — with backup, --force, creates parent dirs)
    p_inst = sub.add_parser("install", help="Install enhanced persona into agent config")
    p_inst.add_argument("seed", nargs="?", help="Rough persona idea (or '-' for stdin)")
    p_inst.add_argument("--file", "-f", help="Read seed from file")
    p_inst.add_argument("--agent", "-a", required=True, choices=list(AGENT_CONFIGS.keys()) + ["all"], help="Target agent")
    p_inst.add_argument("--project", default=str(Path.cwd()), help="Project directory")
    p_inst.add_argument("--profile", "-p", choices=PROFILES)
    p_inst.add_argument("--no-context", action="store_true")
    p_inst.add_argument("--dry-run", action="store_true", help="Preview: no writes, no store")
    p_inst.add_argument("--force", action="store_true", help="Overwrite without backup")
    p_inst.add_argument("--json", action="store_true")
    p_inst.add_argument("--no-store", action="store_true")
    p_inst.add_argument("--via", choices=["claude", "codex", "auggie", "opencode"], help="Delegate to existing agent (no API key needed)")

    # benchmark
    p_bench = sub.add_parser("benchmark", help="Score prompts on 7-dimension rubric")
    p_bench.add_argument("--before", help="Path to raw/before prompt")
    p_bench.add_argument("--after", help="Path to enhanced/after prompt")
    p_bench.add_argument("--enhance", help="Enhance a seed and benchmark both")
    p_bench.add_argument("--project", default=str(Path.cwd()))
    p_bench.add_argument("--no-context", action="store_true")
    p_bench.add_argument("--json", action="store_true")
    p_bench.add_argument("--via", choices=["claude", "codex", "auggie", "opencode"], help="Delegate to existing agent (no API key needed)")
    p_bench.add_argument("--judge-via", choices=["claude", "codex", "auggie", "opencode"], dest="judge_via",
                         help="Blind judge: score via a different agent than the generator")
    p_bench.add_argument("--judge-model", dest="judge_model",
                         help="Blind judge: override API model name for the rubric call")

    # store
    p_store = sub.add_parser("store", help="Analytics store commands")
    p_store_sub = p_store.add_subparsers(dest="store_action")
    p_store_list = p_store_sub.add_parser("list")
    p_store_list.add_argument("--limit", type=int, default=20)
    p_store_list.add_argument("--json", action="store_true")
    p_store_sub.add_parser("stats")
    p_store_search = p_store_sub.add_parser("search")
    p_store_search.add_argument("query")
    p_store_search.add_argument("--json", action="store_true")
    p_store_show = p_store_sub.add_parser("show")
    p_store_show.add_argument("id")
    p_store_delete = p_store_sub.add_parser("delete", help="Delete a specific record")
    p_store_delete.add_argument("id")
    p_store_sub.add_parser("clear", help="Clear all stored data")
    p_store_export = p_store_sub.add_parser("export")
    p_store_export.add_argument("--format", choices=["json", "csv"], default="json")

    # doctor
    sub.add_parser("doctor", help="Health check")

    # lint — static analysis of a system prompt (no LLM)
    p_lint = sub.add_parser("lint", help="Static analysis of a system prompt (no API key needed)")
    p_lint.add_argument("target", nargs="?", help="Path to prompt file, inline text, or '-' for stdin")
    p_lint.add_argument("--file", "-f", help="Read prompt from file")
    p_lint.add_argument("--json", action="store_true", help="Machine-readable output")
    p_lint.add_argument("--no-color", action="store_true", help="Disable ANSI colors")

    # dashboard
    p_dash = sub.add_parser("dashboard", help="Terminal dashboard with analytics")
    p_dash.add_argument("--agent", help="Filter by agent")
    p_dash.add_argument("--since", help="Filter: 24h, 7d, 2026-06-01, today")
    p_dash.add_argument("--json", action="store_true", help="Machine-readable output")
    p_dash.add_argument("--ascii", action="store_true", help="ASCII-only mode (no Unicode)")
    p_dash.add_argument("--show-prompts", action="store_true", help="Show seed text in recent table")
    p_dash.add_argument("--refresh", type=int, default=0, help="Auto-refresh every N seconds")
    p_dash.add_argument("--store", help="Custom store path")

    # version
    sub.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command in ("persona", "enhance"):
        cmd_persona(args)
    elif args.command == "enhance-task":
        cmd_enhance_task(args)
    elif args.command == "install":
        cmd_install(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "store":
        cmd_store(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    elif args.command == "lint":
        cmd_lint(args)
    elif args.command == "dashboard":
        from . import dashboard
        dashboard.cmd_dashboard(
            store_path=getattr(args, 'store', None),
            agent=args.agent,
            since=args.since,
            json_out=args.json,
            ascii_mode=args.ascii,
            show_prompts=getattr(args, 'show_prompts', False),
            refresh=getattr(args, 'refresh', 0),
        )
    elif args.command == "version":
        print(f"prompt-enhancer {VERSION}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
