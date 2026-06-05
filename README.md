# <img src="docs/logo.svg" alt="pe" height="60"> Prompt Enhancer

<p align="center">
  <strong>Generate reusable 7-section agent system prompts from rough persona ideas.</strong><br>
  <sub>With optional install helpers, benchmarking, and local history.</sub>
</p>

<p align="center">
  <a href="https://github.com/hongphuc5497/prompt-enhancer/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT"></a>
  <a href="https://github.com/hongphuc5497/prompt-enhancer/releases"><img src="https://img.shields.io/badge/version-1.5.0-blue" alt="Version"></a>
  <a href="https://github.com/hongphuc5497/prompt-enhancer"><img src="https://img.shields.io/badge/python-3.12+-blue" alt="Python 3.12+"></a>
  <a href="https://github.com/hongphuc5497/prompt-enhancer"><img src="https://img.shields.io/badge/dependencies-0-lightgrey" alt="Zero dependencies"></a>
</p>

Two CLI modes for two use cases:
- **`pe persona`** — Generate persistent 7-section system prompts (for saving, sharing, installing into agent configs)
- **`pe enhance-task`** — Inline task refinement with workspace context (like Auggie's Ctrl+P)

The CLI is `pe` (short) and `prompt-enhancer` (long). Both work identically.

## Install

```bash
pip install pe-cli
```

Or install directly from source:

```bash
pip install git+https://github.com/hongphuc5497/prompt-enhancer.git
```

> The PyPI distribution is `pe-cli` (the name `prompt-enhancer` was already taken).
> The command is still `pe` (or `prompt-enhancer`) — only the install line changes.

Set your API key:
```bash
echo "LLM_API_KEY=*** > ~/.prompt-enhancer.env
```

Config (`~/.prompt-enhancer.env`):
```env
LLM_API_KEY=***i...ps://api.deepseek.com
LLM_MODEL=deepseek-chat
```

Any OpenAI-compatible API works: DeepSeek, OpenAI, OpenRouter, Together, Groq, etc.

## Quick start

```bash
# Generate a 7-section system prompt
pe persona "a senior Rust developer who prefers functional programming"

# Inline task refinement (Auggie Ctrl+P style)
pe enhance-task "fix the login bug in the auth module"

# Safe install into agent config (creates backup if exists)
pe install "a security reviewer" --agent claude

# Benchmark before vs after
pe benchmark --enhance "a Go backend dev"

# Health check
pe doctor

# View analytics
pe store stats
```

## Two modes

| Command | Purpose | Output |
|---------|---------|--------|
| `pe persona` | Generate persistent system prompt | 7 sections: ROLE, CONTEXT, RULES, TECH, FORMAT, PITFALLS, EXAMPLES |
| `pe enhance-task` | Inline task refinement | 3-5 sentence focused task prompt with workspace context |

Both modes auto-discover workspace context (`AGENTS.md`, `CLAUDE.md`, `package.json`, `Cargo.toml`, etc.) from the current project.

## What `pe persona` generates

1. **ROLE** — Specific, well-scoped identity
2. **CONTEXT** — Project specs from workspace files
3. **BEHAVIORAL RULES** — Communication style, decision-making
4. **TECHNICAL GUIDELINES** — Testing, code style, architecture
5. **OUTPUT FORMAT** — Code blocks, explanation style
6. **PITFALLS / GUARDRAILS** — Anti-patterns, security warnings
7. **EXAMPLES** — 1-2 realistic interactions

Plus a "pro tip".

## Benchmark

7-dimension rubric scoring (SurePrompts): Role Clarity, Context Sufficiency, Instruction Specificity, Format Structure, Example Quality, Constraint Tightness, Output Validation. Each scored 1–5, max 35.

```bash
pe benchmark --before raw.txt --after enhanced.md
pe benchmark --enhance "a Go backend dev"   # all-in-one
```

| Score | Verdict |
|-------|---------|
| 28-35 | Production-ready |
| 21-27 | Working draft |
| 14-20 | Needs major revision |
| 7-13 | Rewrite from scratch |

## Comparison with Auggie

Both this tool and Auggie's native `--enhance-prompt` have their strengths:

| | `pe persona` | `pe enhance-task` | Auggie `--enhance-prompt` |
|---|---|---|---|
| **Best for** | Persistent system prompts | Inline task refinement | Inline task refinement |
| **Output** | 7-section document | 3-5 sentences | 1-3 sentences |
| **Workspace aware** | Yes (auto-discovers context) | Yes | Yes (native) |
| **Installable** | Yes (`pe install`) | No | No |
| **Reusable** | Save, share, version | Session-scoped | Session-scoped |
| **Benchmark** | Built-in rubric | No | No |
| **Analytics** | Auto-store | Auto-store | No |

They are complementary tools, not competitors.

## Profiles

| Profile | Focus |
|---------|-------|
| `senior-dev` | Technical depth, testing, edge cases |
| `architect` | System design, trade-offs, scalability |
| `reviewer` | Security, performance, code smells |
| `sre` | Observability, reliability, incident response |
| `product` | User experience, feature prioritization |
| `mentor` | Teaching, onboarding, pair-programming |

## Agent integration

```bash
pe install "a Rust dev..." --agent claude    # → CLAUDE.md
pe install "..." --agent codex               # → .codex/system.md
pe install "..." --agent cursor              # → .cursorrules
pe install "..." --agent all                 # → all compatible configs
```

Safe by default — creates `.bak` backup of existing files. Use `--force` to skip backup, `--dry-run` to preview.

| Agent | Config file | Auto-loaded? |
|-------|------------|:---:|
| **Claude Code** | `CLAUDE.md` | ✅ |
| **Codex** | `.codex/system.md` | ✅ |
| **OpenCode** | `AGENTS.md` | ✅ |
| **Cursor** | `.cursorrules` | ✅ |
| **Auggie** | `AGENTS.md` | ✅ |
| **Copilot** | `.github/copilot-instructions.md` | ✅ |
| **Aider** | `.aider-persona.md` | `--system-prompt` flag |

## Analytics store

Every enhancement is auto-logged to `~/.prompt-enhancer/store.jsonl`:

```bash
pe store list              # Recent enhancements
pe store stats             # Analytics
pe store search "rust"     # Search by keyword
pe store show <id>         # Detailed view
pe store delete <id>       # Remove a record
pe store clear             # Wipe all data
pe store export --format csv  # Export for analysis
```

First run shows a privacy notice. Use `--no-store` to opt out.

## Demo

See [docs/demo.tape](docs/demo.tape) for the VHS terminal recording script.

## Config

```env
# ~/.prompt-enhancer.env
LLM_API_KEY=***i...ps://api.deepseek.com   # Default
LLM_MODEL=deepseek-chat                    # Default
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome.

## License

MIT — see [LICENSE](LICENSE).
