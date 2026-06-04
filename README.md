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

## Benchmarking: prompt-benchmark

Measure prompt quality before and after enhancement using the **SurePrompts 7-Dimension Rubric** (LLM-as-judge). Each dimension is scored 1–5, max 35.

### Dimensions
| # | Dimension | What it measures |
|---|-----------|-----------------|
| 1 | Role Clarity | Specific, coherent role with scope and voice |
| 2 | Context Sufficiency | All background, constraints, domain knowledge |
| 3 | Instruction Specificity | Task, sub-tasks, success criteria |
| 4 | Format Structure | Expected output format (schema, tone, length) |
| 5 | Example Quality | Few-shot examples covering diverse cases |
| 6 | Constraint Tightness | Must NOT do, length limits, banned patterns |
| 7 | Output Validation | Validation plan (schema, checklist, tests) |

### Score interpretation
| Range | Verdict |
|-------|---------|
| 28–35 | Production-ready |
| 21–27 | Working draft |
| 14–20 | Needs major revision |
| 7–13 | Rewrite from scratch |

### Usage

```bash
# Score a single prompt
python3 prompt-benchmark.py --prompt my-prompt.md

# Compare before vs after
python3 prompt-benchmark.py --before raw-idea.txt --after enhanced.md

# Full pipeline: enhance + benchmark in one shot
python3 prompt-benchmark.py --enhance "a Rust dev who prefers functional style"

# JSON output
python3 prompt-benchmark.py --before raw.txt --after enhanced.md --json

# Dynamic: run against test cases, compare output quality
python3 prompt-benchmark.py --before raw.txt --after enhanced.md --execute --tests test_cases.json
```

### Example output
```
════════════════════════════════════════════════════════════
  PROMPT QUALITY BENCHMARK — SurePrompts 7-Dimension Rubric
════════════════════════════════════════════════════════════

  BEFORE:  17/35  (needs-revision)
  AFTER:   34/35  (production-ready)
  DELTA:   ↑17 points (+100%)

  Dimension                     BEFORE   AFTER     Δ
  ---------------------------- ------- ------- -----
  Role Clarity                       4       5    +1
  Context Sufficiency                2       5    +3
  Instruction Specificity            1       5    +4
  Format Structure                   1       5    +4
  Example Quality                    5       5     0
  Constraint Tightness               3       5    +2
  Output Validation                  1       4    +3
```

### How the benchmark works

1. **Static analysis** (default): An LLM judge reads the prompt text and scores each dimension on the rubric — no execution needed. This is like `promptfoo`'s quality assertions but focused on prompt structure, not outputs.

2. **Dynamic analysis** (`--execute`): Runs both prompts against real test cases, then a second LLM judge scores the outputs on task completion, code quality, structure, and contextual fit. This is the A/B testing equivalent for prompts.

The judge model (configurable via `JUDGE_MODEL` env var) uses `temperature=0.3` for consistent, repeatable scoring.
