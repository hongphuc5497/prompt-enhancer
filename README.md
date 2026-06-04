# Prompt Enhancer

Reverse-engineered from Auggie's Ctrl+P Prompt Enhancer. Takes a rough idea and transforms it into a production-quality system prompt for AI coding agents (Claude Code, Codex, Cursor, Hermes, Copilot).

## How it works

```
rough idea: "a senior React dev who likes clean code"
     │
     ▼
┌─────────────────┐
│ Workspace Context│  ← AGENTS.md, CLAUDE.md, package.json auto-discovered
│ (Auggie pattern) │
└────────┬────────┘
     │
     ▼
┌─────────────────┐
│  Enhancement     │  ← LLM transformation with 7-section structure
│  Engine (LLM)    │     ROLE → CONTEXT → RULES → TECH → FORMAT → PITFALLS → EXAMPLES
└────────┬────────┘
     │
     ▼
production system prompt (ready to paste into agent config)
```

Key Auggie patterns replicated:
- **Workspace awareness**: Auto-discovers AGENTS.md, CLAUDE.md, package.json, etc.
- **Structure injection**: Adds file references, conventions, and patterns from context
- **Profile system**: Pre-set enhancement styles (senior-dev, architect, reviewer, SRE, product, mentor)

## Quick start

```bash
# Set API key (once)
echo 'LLM_API_KEY=sk-xxx' > ~/.prompt-enhancer.env

# Generate a system prompt
python3 prompt-enhancer.py "a senior Rust developer who prefers functional style"

# With workspace context auto-discovery
cd ~/repos/myproject
python3 prompt-enhancer.py "a code reviewer who focuses on security"

# From a file
python3 prompt-enhancer.py --file rough-idea.md

# With enhancement profile
python3 prompt-enhancer.py --profile architect "system design reviewer"

# Pipe
echo "a terse SRE who hates alerts" | python3 prompt-enhancer.py
```

## Options

| Flag | Description |
|------|-------------|
| `seed` | The rough prompt idea (positional arg) |
| `--file`, `-f` | Read seed from file |
| `--context`, `-c` | Explicit context file paths |
| `--no-auto-context` | Disable auto-discovery of AGENTS.md |
| `--profile`, `-p` | Enhancement style: `senior-dev`, `architect`, `reviewer`, `sre`, `product`, `mentor` |
| `--dry-run` | Show the enhancement prompt without calling LLM |

## Profiles

| Profile | Focus |
|---------|-------|
| `senior-dev` | Technical depth, testing, edge cases |
| `architect` | System design, trade-offs, scalability |
| `reviewer` | Security, performance, code smells |
| `sre` | Observability, reliability, incident response |
| `product` | User experience, feature prioritization |
| `mentor` | Teaching, onboarding, pair-programming |

## Architecture

```
prompt-enhancer.py          # CLI entry point
├── collect_context()       # Auto-discovers AGENTS.md, CLAUDE.md, package.json
├── build_enhancement_prompt()  # Constructs the LLM enhancement prompt
├── call_llm()              # OpenAI-compatible API call (zero deps beyond stdlib)
└── ENHANCEMENT_PROFILES    # Pre-set enhancement styles
```

Dependencies: **zero** (stdlib only: `json`, `os`, `sys`, `pathlib`, `urllib`, `argparse`)

## What it generates

Every enhanced prompt includes 7 sections:

1. **ROLE** — Specific identity (not vague "helpful assistant")
2. **CONTEXT** — Project/team specifics from workspace files
3. **BEHAVIORAL RULES** — Communication style, decision-making, guardrails
4. **TECHNICAL GUIDELINES** — Testing, code style, architecture patterns
5. **OUTPUT FORMAT** — Code blocks, explanation style, structure
6. **PITFALLS / GUARDRAILS** — Anti-patterns and security warnings
7. **EXAMPLES** — 1-2 realistic interactions showing desired behavior

Plus a "pro tip" — the single most impactful rule for that role.

## Config

Set via environment variables or `~/.prompt-enhancer.env`:

```env
LLM_API_KEY=sk-xxx          # Required
LLM_BASE_URL=https://api.deepseek.com  # Default
LLM_MODEL=deepseek-chat     # Default
```

Any OpenAI-compatible API works: DeepSeek, OpenRouter, OpenAI, Together, Groq, etc.

## Reverse-engineered from Auggie

The Auggie CLI's Prompt Enhancer (Ctrl+P) works by:
1. Capturing user input + workspace context
2. Sending to an enhancement service (LLM)
3. Replacing input with structured, context-aware prompt

Source: https://docs.augmentcode.com/cli/interactive/prompt-enhancer
