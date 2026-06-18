#!/usr/bin/env python3
"""
Prompt Enhancer — reverse-engineered from Auggie's Prompt Enhancer (Ctrl+P).

Takes a rough prompt idea and enhances it into a well-structured system prompt
for AI coding agents. Uses workspace context (AGENTS.md, tech stack, conventions)
to inject relevant structure, like Auggie's enhancer injects codebase patterns.

Usage:
    python3 prompt-enhancer.py "a senior Rust developer who prefers functional style"
    python3 prompt-enhancer.py --file rough-idea.txt
    python3 prompt-enhancer.py --context repos/myproject/AGENTS.md "a DevOps SRE who..."
    echo "a terse code reviewer" | python3 prompt-enhancer.py

Output: enhanced system prompt to stdout

Config via env vars or ~/.prompt-enhancer.env:
    LLM_API_KEY   — API key (required)
    LLM_BASE_URL  — API base URL (default: https://api.deepseek.com)
    LLM_MODEL     — model name (default: deepseek-chat)
"""

import json
import os
import sys
import argparse
import urllib.request
import urllib.error
from pathlib import Path


# ── Config ──────────────────────────────────────────────────────────
def load_config():
    """Load config from env vars and ~/.prompt-enhancer.env."""
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


# ── Context collector (Auggie pattern: workspace awareness) ─────────
def collect_context(context_paths, auto_discover=True):
    """Collect workspace context: AGENTS.md, CLAUDE.md, package.json, etc.

    This mirrors Auggie's workspace context injection — the enhancer
    knows about the codebase and can reference it in the output.
    """
    context = []
    seen = set()

    # Explicit paths
    for p in context_paths:
        path = Path(p).expanduser().resolve()
        if path.exists() and str(path) not in seen:
            seen.add(str(path))
            content = path.read_text()
            label = path.name
            if len(content) > 3000:
                content = content[:3000] + "\n... (truncated)"
            context.append(f"### {label} ({path})\n```\n{content}\n```")

    # Auto-discover from repo roots
    if auto_discover:
        cwd = Path.cwd()
        discover_patterns = [
            "AGENTS.md", "CLAUDE.md", ".cursorrules",
            ".github/copilot-instructions.md",
        ]
        for pattern in discover_patterns:
            try:
                for found in cwd.rglob(pattern):
                    if str(found) not in seen and found.is_file():
                        seen.add(str(found))
                        content = found.read_text()
                        if len(content) > 3000:
                            content = content[:3000] + "\n... (truncated)"
                        context.append(f"### {found.name} ({found})\n```\n{content}\n```")
            except (PermissionError, OSError, InterruptedError):
                pass  # skip restricted directories

        # Also grab key tech stack signals
        for signal_file in ["package.json", "Cargo.toml", "pyproject.toml", "go.mod"]:
            path = cwd / signal_file
            if path.exists() and str(path) not in seen:
                seen.add(str(path))
                content = path.read_text()
                if len(content) > 1500:
                    content = content[:1500] + "\n... (truncated)"
                context.append(f"### {signal_file} (tech stack signal)\n```\n{content}\n```")

    return "\n\n".join(context)


# ── Enhancement profiles (pre-set enhancement styles) ───────────────
ENHANCEMENT_PROFILES = {
    "senior-dev": """
Focus on: technical depth, code quality, testing rigor, edge-case awareness.
The output prompt should emphasize correctness, readability, and maintainability.
""",
    "architect": """
Focus on: system design, trade-off analysis, scalability, integration patterns.
The output prompt should emphasize architectural decisions and long-term thinking.
""",
    "reviewer": """
Focus on: security, performance, code smells, antipatterns, best-practice violations.
The output prompt should emphasize critical scrutiny and actionable improvement suggestions.
""",
    "sre": """
Focus on: observability, reliability, incident response, infrastructure as code.
The output prompt should emphasize operational excellence and failure-mode thinking.
""",
    "product": """
Focus on: user experience, feature prioritization, stakeholder communication.
The output prompt should emphasize user outcomes and business impact.
""",
    "mentor": """
Focus on: teaching, explanation, onboarding, pair-programming style.
The output prompt should emphasize educational value and patience.
""",
}


# ── The enhancement prompt (the "engine" that transforms input) ────
def build_enhancement_prompt(seed, workspace_context, profile):
    """Build the LLM prompt that does the enhancement. This is the core
    reverse-engineered from Auggie's enhancement service."""
    profile_instruction = ENHANCEMENT_PROFILES.get(profile, "")

    return f"""You are a prompt engineer specializing in creating system prompts for AI coding agents (Claude Code, Codex, Cursor, Hermes, Copilot). Your job is to transform a rough idea into a production-quality system prompt.

## Input

### Seed prompt (the rough idea)
{seed}

### Workspace context (what you know about the project/team)
{workspace_context if workspace_context else "(no workspace context provided — use your best judgment)"}

### Enhancement profile focus
{profile_instruction if profile_instruction else "(default: balanced, production-ready system prompt)"}

## Enhancement Rules

Transform the seed prompt into a system prompt that follows this structure:

1. **ROLE** — Clear identity statement. Who is this agent? What's their expertise?
   - Be specific: "You are a senior Rust systems engineer..." not "You are a helpful assistant..."
   - Include domain expertise, years-of-experience framing, and style

2. **CONTEXT** — What project/team/codebase this agent works with
   - Reference specific technologies from the workspace context
   - Mention conventions and patterns found in AGENTS.md / configs

3. **BEHAVIORAL RULES** — How the agent should act
   - Communication style (terse? detailed? teaching-oriented?)
   - Decision-making principles (ask vs act? verify first?)
   - Safety guardrails (what NOT to do)

4. **TECHNICAL GUIDELINES** — Code quality standards
   - Testing requirements (TDD? coverage thresholds?)
   - Code style preferences
   - Architecture patterns to follow
   - Tech-stack-specific conventions

5. **OUTPUT FORMAT** — How responses should be structured
   - Code block conventions
   - Explanation style
   - When to use bullet points vs paragraphs

6. **PITFALLS / GUARDRAILS** — Common mistakes to avoid
   - Anti-patterns specific to the tech stack
   - Over-engineering warnings
   - Security considerations

7. **EXAMPLES** — 1-2 example interactions showing desired behavior

## Quality Requirements

- Be CONCRETE. Mention actual files, patterns, and tools from the workspace context.
- Be ACTIONABLE. Rules should translate directly into agent behavior.
- Be CONCISE. Each section: 2-4 bullets or 2-3 sentences.
- Include a "pro tip" at the end — the one thing that makes this prompt most effective.

## Output

Output ONLY the system prompt markdown. No preamble, no "Here is..." — just the prompt ready to paste into an agent config. Start with "# System Prompt: <Role Name>"."""


# ── LLM call ────────────────────────────────────────────────────────
def call_llm(prompt, config):
    """Call the LLM API. OpenAI-compatible format."""
    url = f"{config['base_url'].rstrip('/')}/v1/chat/completions"

    body = json.dumps({
        "model": config["model"],
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }).encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {config['api_key']}")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"API error ({e.code}): {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        sys.exit(1)


# ── CLI ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Prompt Enhancer — transform rough ideas into production system prompts",
    )
    parser.add_argument(
        "seed", nargs="?", default=None,
        help="The rough prompt idea to enhance (reads stdin if omitted)"
    )
    parser.add_argument(
        "--file", "-f", type=str, default=None,
        help="Read seed prompt from file"
    )
    parser.add_argument(
        "--context", "-c", type=str, nargs="*", default=[],
        help="Path(s) to context files (AGENTS.md, CLAUDE.md, etc.)"
    )
    parser.add_argument(
        "--no-auto-context", action="store_true",
        help="Disable auto-discovery of AGENTS.md / CLAUDE.md in CWD"
    )
    parser.add_argument(
        "--profile", "-p", type=str, default=None,
        choices=list(ENHANCEMENT_PROFILES.keys()),
        help="Enhancement profile (senior-dev, architect, reviewer, sre, product, mentor)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show the enhancement prompt without calling the LLM"
    )
    args = parser.parse_args()

    # Get seed
    if args.file:
        seed = Path(args.file).expanduser().read_text().strip()
    elif args.seed:
        seed = args.seed
    elif not sys.stdin.isatty():
        seed = sys.stdin.read().strip()
    else:
        print("Error: provide a seed prompt as argument, --file, or via stdin", file=sys.stderr)
        sys.exit(1)

    if not seed:
        print("Error: seed prompt is empty", file=sys.stderr)
        sys.exit(1)

    # Collect context
    workspace_context = collect_context(args.context, auto_discover=not args.no_auto_context)

    # Build enhancement prompt
    enhancement_prompt = build_enhancement_prompt(seed, workspace_context, args.profile)

    if args.dry_run:
        print("=== Enhancement Prompt (dry-run) ===")
        print(enhancement_prompt)
        return

    # Load config
    config = load_config()
    if not config["api_key"]:
        print("Error: LLM_API_KEY not set. Set it in env or ~/.prompt-enhancer.env", file=sys.stderr)
        print("Example: echo 'LLM_API_KEY=sk-xxx' > ~/.prompt-enhancer.env", file=sys.stderr)
        sys.exit(1)

    # Enhance!
    print(f"Enhancing with {config['model']} via {config['base_url']}...", file=sys.stderr)
    result = call_llm(enhancement_prompt, config)
    print(result)


if __name__ == "__main__":
    main()
