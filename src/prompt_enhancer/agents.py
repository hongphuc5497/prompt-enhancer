"""
Agent backends for prompt-enhancer — delegate enhancement to existing coding agents.

Each backend takes a seed prompt and returns an enhanced version by shelling out
to the agent's CLI. No API key needed — uses the agent's existing configuration.

Supported agents:
    claude   — Claude Code (claude -p)
    codex    — Codex CLI (codex)
    auggie   — Auggie (auggie --print)
    opencode — OpenCode (opencode --print)
"""

import subprocess
import sys
import os
from pathlib import Path


ENHANCEMENT_PROMPT_TEMPLATE = """Transform this rough idea into a 7-section system prompt for AI coding agents. 

SECTIONS: ROLE → CONTEXT → BEHAVIORAL RULES → TECHNICAL GUIDELINES → OUTPUT FORMAT → PITFALLS/GUARDRAILS → EXAMPLES

RULES:
- Be concrete — reference actual tools, patterns, conventions
- Be actionable — rules translate directly into agent behavior
- Be concise — 2-4 bullets per section
- Include a "pro tip" at the end
- Output ONLY the system prompt markdown, start with "# System Prompt: <Role>"

## Rough idea
{seed}

## Output
# System Prompt:"""


def _find_binary(names):
    """Find the first available binary from a list of names."""
    for name in names:
        # Check common locations
        for prefix in ["", str(Path.home() / ".local/bin/"), str(Path.home() / ".nvm/versions/node/v26.1.0/bin/")]:
            path = os.path.join(prefix, name)
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
        # Try which
        try:
            result = subprocess.run(["which", name], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
    return None


def enhance_via_claude(seed, config=None):
    """Enhance via Claude Code."""
    binary = _find_binary(["claude"])
    if not binary:
        raise RuntimeError("Claude Code not found. Install: npm install -g @anthropic-ai/claude-code")

    prompt = ENHANCEMENT_PROMPT_TEMPLATE.format(seed=seed)
    result = subprocess.run(
        [binary, "-p", prompt],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "CLAUDE_CODE_HEADLESS": "1"}
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude Code failed: {result.stderr[:200]}")
    return result.stdout.strip()


def enhance_via_codex(seed, config=None):
    """Enhance via Codex CLI."""
    binary = _find_binary(["codex"])
    if not binary:
        raise RuntimeError("Codex not found. Install: npm install -g @openai/codex")

    prompt = ENHANCEMENT_PROMPT_TEMPLATE.format(seed=seed)
    result = subprocess.run(
        [binary, prompt],
        capture_output=True, text=True, timeout=120,
        env={**os.environ}
    )
    if result.returncode != 0:
        raise RuntimeError(f"Codex failed: {result.stderr[:200]}")
    return result.stdout.strip()


def enhance_via_auggie(seed, config=None):
    """Enhance via Auggie (Augment)."""
    binary = _find_binary(["auggie"])
    if not binary:
        raise RuntimeError("Auggie not found. Install: npm install -g @augmentcode/auggie")

    prompt = ENHANCEMENT_PROMPT_TEMPLATE.format(seed=seed)
    result = subprocess.run(
        [binary, "--print", prompt],
        capture_output=True, text=True, timeout=120,
        env={**os.environ}
    )
    if result.returncode != 0:
        raise RuntimeError(f"Auggie failed: {result.stderr[:200]}")

    output = result.stdout.strip()
    # Strip Auggie's thinking/exploration prefix
    if "🤖" in output:
        output = output.split("🤖")[-1].strip()
    # Strip ANSI escape codes
    import re
    output = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', output)
    return output


def enhance_via_opencode(seed, config=None):
    """Enhance via OpenCode."""
    binary = _find_binary(["opencode"])
    if not binary:
        raise RuntimeError("OpenCode not found.")

    prompt = ENHANCEMENT_PROMPT_TEMPLATE.format(seed=seed)
    result = subprocess.run(
        [binary, "--print", prompt],
        capture_output=True, text=True, timeout=120,
        env={**os.environ}
    )
    if result.returncode != 0:
        raise RuntimeError(f"OpenCode failed: {result.stderr[:200]}")
    return result.stdout.strip()


# Map agent names to enhancers
AGENT_ENHANCERS = {
    "claude": enhance_via_claude,
    "codex": enhance_via_codex,
    "auggie": enhance_via_auggie,
    "opencode": enhance_via_opencode,
}


def enhance(seed, via_agent=None, config=None):
    """Enhance a seed prompt. If via_agent is set, delegate to that agent.
    Otherwise, use the API key (legacy path).
    """
    if via_agent:
        enhancer = AGENT_ENHANCERS.get(via_agent)
        if not enhancer:
            raise RuntimeError(f"Unknown agent: {via_agent}. Supported: {', '.join(AGENT_ENHANCERS.keys())}")
        return enhancer(seed, config)

    # Fall through to API-key mode — caller must handle
    raise RuntimeError("No enhancement method available. Use --via <agent> or set LLM_API_KEY.")


def get_available_agents():
    """Return list of agents with available binaries."""
    available = []
    for agent, enhancer in AGENT_ENHANCERS.items():
        try:
            binary = _find_binary([agent])
            if binary:
                available.append((agent, binary, "ready"))
            else:
                available.append((agent, None, "not found"))
        except Exception:
            available.append((agent, None, "error"))
    return available
