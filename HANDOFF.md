# Prompt Enhancer (`pe`) — Project Handoff

> **Tagline:** Compile rough intent into agent-ready system prompts.
> **Repo:** https://github.com/hongphuc5497/prompt-enhancer
> **Current version:** v1.5.0
> **Tests:** 50 passing (stdlib `unittest`, zero deps) — CI matrix on Py 3.12/3.13/3.14, Ubuntu+macOS
> **Dependencies:** 0 (Python stdlib only)
> **Python:** 3.12+ required (3.14 recommended)
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
├── cli.py            # Unified CLI: persona, enhance-task, install, benchmark, store, dashboard, doctor, lint
├── view.py           # ANSI-styled rich prompt viewer + spinner progress indicator
├── dashboard.py      # Terminal analytics dashboard (sparklines, bar charts, panels)
├── agents.py         # Agent delegation backends (claude, codex, auggie, opencode) + blind-judge runner
├── lint.py           # Static analysis of system prompts (no LLM)
├── __init__.py       # Version marker

.github/workflows/
├── ci.yml            # Matrix tests on 3.12/3.13/3.14, Ubuntu+macOS
└── release.yml       # PyPI Trusted Publishing on tag push

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
pe benchmark --after p.md --judge-via claude   # blind judge via a different agent
pe lint p.md                            # static analysis, no LLM required
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
| `--judge-via {claude,codex,auggie,opencode}` | Blind judge: score via a different agent than the generator |
| `--judge-model <name>` | Blind judge: override the API model used for the rubric call |

---

## Version history

| Version | What |
|---------|------|
| **v1.5.0** | "Ready for the world": Python 3.12+ baseline, GitHub Actions CI matrix, PyPI release workflow (Trusted Publishing), `pe lint` static analysis, blind judging (`--judge-via` / `--judge-model`), 50 tests |
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
| 7 | No test suite | ✅ Fixed v1.5.0 (50 tests + CI matrix on 3.12/3.13/3.14) |
| 8 | Hard-coded local paths in scripts | ✅ Fixed v1.5.0 (legacy scripts now use `sys.executable`) |
| 9 | Homebrew formula not ready | 📋 SHA placeholder remains (auto-bump on next release) |
| 10 | Privacy implications of auto-store | ✅ First-run notice + `store delete/clear` |
| 11 | Auggie comparison overclaimed | ✅ Repositioned as complementary tools |
| 12 | Agent mappings incorrect (codex vs copilot) | ✅ Fixed (`.codex/system.md` vs `.github/copilot-instructions.md`) |
| 13 | Same model generates and judges (benchmark validity) | ✅ Fixed v1.5.0 (`--judge-via` / `--judge-model` blind judging) |

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

**Known limitation:** The same LLM can both generate and judge — this rewards
structure regardless of substance and isn't methodologically valid for
agent-behavior claims.

**Mitigation (v1.5.0): blind judging.** Pass `--judge-via <agent>` to route the
rubric prompt through a different agent CLI than the generator, or
`--judge-model <name>` to override just the model on the API call. Example:

```bash
# generator: DeepSeek API   judge: Claude Code
pe benchmark --enhance "a Rust dev" --judge-via claude
```

The judge's identity is recorded in `store.jsonl` under `benchmark.judge` so
historical results can be filtered by who scored them.

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
pip install prompt-enhancer-cli
# or: pip install git+https://github.com/hongphuc5497/prompt-enhancer.git
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
# 50 tests, all passing
```

CI runs the same matrix on every push: Ubuntu + macOS × Python 3.12 / 3.13 / 3.14.

---

## Releasing to PyPI (one-time setup)

The PyPI release workflow uses **Trusted Publishing** (OIDC, no API tokens).
Before the first `git tag v1.5.0 && git push --tags` will publish anything:

1. Sign in at <https://pypi.org/manage/account/publishing/>
2. Add a "pending publisher":
   - **PyPI Project Name:** `prompt-enhancer-cli` (the bare name `prompt-enhancer` was already taken)
   - **Owner:** `hongphuc5497`
   - **Repository:** `prompt-enhancer`
   - **Workflow filename:** `release.yml`
   - **Environment:** `pypi`
3. Push a tag — the workflow builds sdist + wheel, verifies the tag matches
   `pyproject.toml`, and publishes.

After the first publish, the trusted publisher becomes permanent.

---

## Future roadmap (not yet implemented)

- **`pe serve`** — local web UI for exploring the store
- **Textual-based interactive TUI** — if users want arrow-key navigation
- **`pe diff`** — compare two enhanced prompts side-by-side
- **`pe share`** — generate a shareable link/gist of a prompt
- **Multi-judge consensus** — average scores from 3 judges, report variance
- **Homebrew formula auto-bump** — GitHub Action that updates SHA256 on release
- **VS Code / Neovim integration** — call `pe enhance-task` on the current selection
