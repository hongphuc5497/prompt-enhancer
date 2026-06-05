# Prompt Enhancer (`pe`) — Project Handoff

> **Tagline:** Compile rough intent into agent-ready system prompts.
> **Repo:** https://github.com/hongphuc5497/prompt-enhancer
> **Current version:** v1.4.1
> **Tests:** 38 passing (stdlib `unittest`, zero deps)
> **Dependencies:** 0 (Python stdlib only)
> **License:** MIT

---

## What `pe` does

Takes a vague sentence like *"a senior Rust developer who prefers functional programming"* and generates a 7-section production-ready system prompt that an AI coding agent can load as its personality. The seven sections: **ROLE → CONTEXT → RULES → TECH → FORMAT → PITFALLS → EXAMPLES**.

Two enhancement modes:
- **`pe persona "..."`** — generates a persistent 7-section system prompt (for saving, sharing, installing into agent configs)
- **`pe enhance-task "..."`** — inline task refinement with workspace context (like Auggie's Ctrl+P)

---

## Architecture

```
src/prompt_enhancer/
├── cli.py           # Unified CLI: persona, enhance-task, install, benchmark, store, dashboard, doctor
├── view.py           # ANSI-styled rich prompt viewer + spinner progress indicator
├── dashboard.py      # Terminal analytics dashboard (sparklines, bar charts, panels)
├── agents.py         # Agent delegation backends (claude, codex, auggie, opencode)
├── __init__.py       # Version marker

prompt-enhancer.py     # Legacy standalone enhancer (stdlib only)
prompt-benchmark.py    # Legacy standalone benchmark
prompt-install.py      # Legacy standalone installer
prompt-store.py        # Legacy standalone store
```

### CLI surface

```
pe persona "a Rust dev..."              # 7-section system prompt
pe enhance-task "fix the login bug"     # inline task refinement
pe install "..." --agent claude         # safe install into agent config
pe benchmark --enhance "a Go dev..."    # score before/after on 7-dim rubric
pe dashboard                            # terminal analytics dashboard
pe doctor                               # health check
pe store {list,stats,search,export,delete,clear}
pe version
```

### Key flags

| Flag | Purpose |
|------|---------|
| `--via claude\|codex\|auggie\|opencode` | Delegate enhancement to existing agent (no API key needed) |
| `--copy` / `-c` | Copy output to system clipboard |
| `--json` | Machine-readable JSON output |
| `--raw` | Skip rich ANSI viewer, print raw text |
| `--profile {senior-dev,architect,reviewer,sre,product,mentor}` | Enhancement style |
| `--no-store` | Skip auto-saving to analytics store |
| `--since 24h\|7d\|2026-06-01` | Filter by date (dashboard, store) |
| `--refresh 30` | Auto-refresh dashboard every N seconds |
| `--agent claude` | Filter by agent (dashboard) |
| `--ascii` | ASCII-only fallback (no Unicode) |
| `--show-prompts` | Show unredacted seed text in recent table |

---

## Version history

| Version | What |
|---------|------|
| **v1.4.1** | 38-unit test suite (stdlib unittest), bold parameter fix in viewer |
| **v1.4.0** | Rich ANSI prompt viewer + progress spinner with elapsed timer |
| **v1.3.0** | `pe dashboard` — stdlib-only ANSI analytics TUI (sparklines, bars, panels) |
| **v1.2.0** | All 4 Auggie blockers fixed: workspace context, safe install, README, no-seed crash. Added `pe doctor`, `pe persona`/`pe enhance-task`, privacy store |
| **v1.1.0** | `pe` alias, SVG logo (terminal prism), VHS demo tape, Auggie tagline |
| **v1.0.1** | Open source ready: LICENSE, CONTRIBUTING.md, CHANGELOG.md, PyPI classifiers |
| **v1.0.0** | Unified CLI, auto-store, Homebrew formula, install script, `--json` mode |
| **v0.2.0** | Benchmark, install into agent configs, verified vs Auggie |
| **v0.1.0** | Initial release: `prompt-enhancer.py`, 7-section output, workspace context |

---

## Auggie's audit (v1.2.0 review)

Auggie gave the tool a **5.5/10** initially, identifying 12 issues. All were fixed:

| # | Issue | Status |
|---|-------|--------|
| 1 | No workspace context in packaged CLI | ✅ Fixed v1.2.0 |
| 2 | `install` overwrites without backup | ✅ Fixed v1.2.0 (`.bak` + `--force`) |
| 3 | README install commands broken | ✅ Fixed v1.2.0 |
| 4 | `pe persona` with no seed crashes | ✅ Fixed v1.2.0 |
| 5 | `--dry-run` still writes to store | ✅ Fixed v1.2.0 |
| 6 | Version mismatch (1.0.0 vs 1.1.0) | ✅ Fixed v1.2.0 |
| 7 | No test suite | ✅ Fixed v1.4.1 (38 tests) |
| 8 | Hard-coded local paths in scripts | ✅ Legacy scripts, packaged CLI uses relative paths |
| 9 | Homebrew formula not ready | 📋 SHA placeholder remains |
| 10 | Privacy implications of auto-store | ✅ First-run notice + `store delete/clear` |
| 11 | Auggie comparison overclaimed | ✅ Repositioned as complementary tools |
| 12 | Agent mappings incorrect (codex vs copilot) | ✅ Fixed (`.codex/system.md` vs `.github/copilot-instructions.md`) |

---

## Benchmark methodology

Uses the **SurePrompts 7-Dimension Rubric** (LLM-as-judge):
1. Role Clarity (1-5)
2. Context Sufficiency (1-5)
3. Instruction Specificity (1-5)
4. Format Structure (1-5)
5. Example Quality (1-5)
6. Constraint Tightness (1-5)
7. Output Validation (1-5)
**Max: 35**

Score ranges: 28-35 production-ready, 21-27 working draft, 14-20 needs revision, 7-13 rewrite.

**Known limitation:** Same LLM can both generate and judge. Scores reward structure. Auggie flagged this as not methodologically valid for agent-behavior claims.

---

## Agent delegation (`--via`)

No API key? No problem. `pe` can delegate enhancement to any installed coding agent:

```bash
pe persona "..." --via claude    # Claude Code
pe persona "..." --via codex     # Codex CLI
pe persona "..." --via auggie    # Auggie (Augment)
pe persona "..." --via opencode  # OpenCode
```

Each agent produces a different enhancement style. Claude is philosophical, Auggie is workspace-aware, Codex is terse and code-forward.

### How it works
1. `pe doctor` auto-discovers agent binaries on PATH and common locations
2. `--via claude` shells out: `claude -p "Enhance this prompt: ..."`
3. Returns the enhanced prompt, styled in the rich viewer

---

## Install

```bash
pip install git+https://github.com/hongphuc5497/prompt-enhancer.git
# or: brew install hongphuc5497/tap/prompt-enhancer
# or: curl install.sh | sh

echo "LLM_API_KEY=*** > ~/.prompt-enhancer.env
pe doctor    # verify everything works
```

---

## Key design decisions

1. **Zero dependencies.** Every feature (dashboard, viewer, benchmark) uses stdlib-only ANSI/Unicode. No `rich`, `textual`, `click`, or `colorama`.
2. **`pe` is the human command; `prompt-enhancer` is the script/CI command.** Both point to the same CLI.
3. **Auto-store is on by default with first-run privacy notice.** Everything logged to `~/.prompt-enhancer/store.jsonl`. Use `--no-store` to opt out.
4. **Rich viewer only activates on TTY.** Pipes, CI, `--json`, and `--raw` all bypass it.
5. **Agent-first, not API-first.** The `--via` flag makes the tool zero-config for teams that already have coding agents installed.

---

## Running tests

```bash
cd prompt-enhancer
python3 -m unittest tests/test_all.py -v
# 38 tests, all passing
```

---

## Future roadmap (not yet implemented)

- **`pe serve`** — local web UI for exploring the store
- **Textual-based interactive TUI** — if users want arrow-key navigation
- **PyPI publication** — `pip install prompt-enhancer` without git URL
- **GitHub Actions CI** — auto-run tests on push
- **`pe diff`** — compare two enhanced prompts side-by-side
- **`pe share`** — generate a shareable link/gist of a prompt
- **Blind judging** — use a different model for benchmark scores than generation
- **Homebrew formula with real SHA256** — currently placeholder
