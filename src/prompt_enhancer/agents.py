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

import os
import re
import shutil
import subprocess


PERSONA_PROMPT_TEMPLATE = """Transform this rough idea into a 7-section system prompt for AI coding agents.

SECTIONS: ROLE → CONTEXT → BEHAVIORAL RULES → TECHNICAL GUIDELINES → OUTPUT FORMAT → PITFALLS/GUARDRAILS → EXAMPLES

RULES:
- Be concrete — reference actual tools, patterns, conventions
- Be actionable — rules translate directly into agent behavior
- Be concise — 2-4 bullets per section
- Include a "pro tip" at the end
- Output ONLY the system prompt markdown, start with "# System Prompt: <Role>"
{context_block}
## Rough idea
{seed}

## Output
# System Prompt:"""


TASK_PROMPT_TEMPLATE = """You are a prompt enhancer for AI coding agents. Transform a vague task request into a clear, actionable prompt.

RULES:
- Add relevant file references and context from the workspace
- Structure the task into clear steps
- Include relevant coding conventions and patterns
- Ask clarifying questions if the task is ambiguous
- Keep it concise — 3-5 sentences
- Output ONLY the enhanced task prompt, no preamble
{context_block}
## Raw task request
{seed}

## Output
Output ONLY the enhanced task prompt."""


def _context_block(workspace_context):
    """Render an optional workspace-context section for delegated prompts."""
    if not workspace_context:
        return ""
    return f"\n## Workspace context\n{workspace_context}\n"


def _build_prompt(seed, workspace_context="", task_mode=False):
    """Build the delegated prompt. task_mode picks the task-refinement template
    instead of the 7-section persona template."""
    template = TASK_PROMPT_TEMPLATE if task_mode else PERSONA_PROMPT_TEMPLATE
    return template.format(seed=seed, context_block=_context_block(workspace_context))


def _strip_auggie(output):
    """Strip Auggie's thinking/exploration prefix and ANSI escape codes."""
    if "🤖" in output:
        output = output.split("🤖")[-1].strip()
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', output)


def _find_binary(names):
    """Find the first available binary from a list of names (resolved via PATH)."""
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def enhance_via_claude(seed, config=None, workspace_context="", task_mode=False):
    """Enhance via Claude Code."""
    binary = _find_binary(["claude"])
    if not binary:
        raise RuntimeError("Claude Code not found. Install: npm install -g @anthropic-ai/claude-code")

    prompt = _build_prompt(seed, workspace_context, task_mode)
    result = subprocess.run(
        [binary, "-p", prompt],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "CLAUDE_CODE_HEADLESS": "1"}
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude Code failed: {result.stderr[:200]}")
    return result.stdout.strip()


def enhance_via_codex(seed, config=None, workspace_context="", task_mode=False):
    """Enhance via Codex CLI."""
    binary = _find_binary(["codex"])
    if not binary:
        raise RuntimeError("Codex not found. Install: npm install -g @openai/codex")

    prompt = _build_prompt(seed, workspace_context, task_mode)
    result = subprocess.run(
        [binary, prompt],
        capture_output=True, text=True, timeout=120,
        env={**os.environ}
    )
    if result.returncode != 0:
        raise RuntimeError(f"Codex failed: {result.stderr[:200]}")
    return result.stdout.strip()


def enhance_via_auggie(seed, config=None, workspace_context="", task_mode=False):
    """Enhance via Auggie (Augment)."""
    binary = _find_binary(["auggie"])
    if not binary:
        raise RuntimeError("Auggie not found. Install: npm install -g @augmentcode/auggie")

    prompt = _build_prompt(seed, workspace_context, task_mode)
    result = subprocess.run(
        [binary, "--print", prompt],
        capture_output=True, text=True, timeout=120,
        env={**os.environ}
    )
    if result.returncode != 0:
        raise RuntimeError(f"Auggie failed: {result.stderr[:200]}")
    return _strip_auggie(result.stdout.strip())


def enhance_via_opencode(seed, config=None, workspace_context="", task_mode=False):
    """Enhance via OpenCode."""
    binary = _find_binary(["opencode"])
    if not binary:
        raise RuntimeError("OpenCode not found.")

    prompt = _build_prompt(seed, workspace_context, task_mode)
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


# Invocation recipes for running an arbitrary prompt through an agent CLI.
# Used by the blind-judge path so the benchmark judge can differ from the generator.
AGENT_INVOKERS = {
    "claude":   {"binary": "claude",   "args": ["-p"],       "env": {"CLAUDE_CODE_HEADLESS": "1"}},
    "codex":    {"binary": "codex",    "args": [],           "env": {}},
    "auggie":   {"binary": "auggie",   "args": ["--print"],  "env": {}},
    "opencode": {"binary": "opencode", "args": ["--print"],  "env": {}},
}


def run_via_agent(prompt, via_agent, timeout=180):
    """Run a raw prompt through an agent CLI and return its stdout.

    Unlike enhance_via_*, this passes the prompt verbatim — no enhancement
    template wrapping. Used for blind judging in `pe benchmark --judge-via`.
    """
    recipe = AGENT_INVOKERS.get(via_agent)
    if not recipe:
        raise RuntimeError(f"Unknown agent: {via_agent}. Supported: {', '.join(AGENT_INVOKERS.keys())}")
    binary = _find_binary([recipe["binary"]])
    if not binary:
        raise RuntimeError(f"{via_agent} not found on PATH")
    result = subprocess.run(
        [binary, *recipe["args"], prompt],
        capture_output=True, text=True, timeout=timeout,
        env={**os.environ, **recipe["env"]},
    )
    if result.returncode != 0:
        raise RuntimeError(f"{via_agent} failed: {result.stderr[:200]}")
    output = result.stdout.strip()
    if via_agent == "auggie":
        output = _strip_auggie(output)
    return output


def enhance(seed, via_agent=None, config=None, workspace_context="", task_mode=False):
    """Enhance a seed prompt. If via_agent is set, delegate to that agent.
    Otherwise, use the API key (legacy path).

    workspace_context is injected into the delegated prompt; task_mode=True
    selects the inline task-refinement template instead of the persona template.
    """
    if via_agent:
        enhancer = AGENT_ENHANCERS.get(via_agent)
        if not enhancer:
            raise RuntimeError(f"Unknown agent: {via_agent}. Supported: {', '.join(AGENT_ENHANCERS.keys())}")
        return enhancer(seed, config, workspace_context=workspace_context, task_mode=task_mode)

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
