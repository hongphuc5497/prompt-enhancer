# Changelog

## v1.6.1 (2026-06-08) — Config hardening
- **`LLM_BASE_URL` tolerates a trailing `/v1`** — the client appends
  `/v1/chat/completions` itself, so a base URL of `https://host`,
  `https://host/`, or `https://host/v1` now all resolve identically instead of
  producing a doubled `/v1/v1` path (404). Normalization happens once in
  `load_config()`.
- **`pe store` with no subcommand defaults to `list`** instead of erroring with
  "Unknown store action: None".
- Test suite grew 60 → 63 (added `TestConfig` base-URL normalization cases).

## v1.6.0 (2026-06-07) — A Joy to Look At
- **TUI overhaul (zero new dependencies)** — extracted a centralized terminal
  foundation in `term.py`: ANSI color policy (honors `NO_COLOR` / `TERM=dumb`),
  display-width-aware layout (⚡ and CJK count as 2 cells), boxed `panel`,
  `header` branding, `footer`, `rule`, and `truncate` — each with an ASCII
  fallback for dumb terminals and pipes.
- **Live interactive dashboard** — `pe dashboard` now opens a live, scrollable
  view by default on a TTY. Alt-screen + hidden cursor, signal-safe restore on
  `SIGINT`/`SIGTERM`. Keys: `j/↓ k/↑` scroll, `g/G` top/bottom, `space` page,
  `q/Esc` quit. The Recent table is a scroll window over the full history, not a
  fixed slice. Footer is honest per mode (no fake scroll keys in one-shot).
- **`--refresh N`** — auto-reloads records and redraws every N seconds (`0`,
  the default, stays event-driven with zero idle CPU).
- **`--ascii` / non-TTY fallback** — piping or redirecting `pe dashboard` emits
  clean ASCII and exits immediately (no hang, no alt-screen escapes).
- **Unified CLI branding** — `view.py`, `dashboard.py`, and `lint.py` all render
  through `term.py` for consistent headers, footers, and rules.
- **Per-record agent delta attribution** fixed in the dashboard stats.
- Test suite grew from 50 → 60 (added `TestTerm` coverage and a per-record
  delta-attribution regression test).

## v1.5.0 (2026-06-05) — Ready for the world
- **Python baseline bumped to 3.12+** (tested against 3.12, 3.13, 3.14). Drops 3.11.
- **`pe lint`** — static analysis of system prompts (no API key, no LLM). Detects
  missing 7-section coverage, vague hedging language, naive contradictions
  (`always X` vs `never X`), empty `EXAMPLES`, and length issues. Emits
  `--json` for CI; exits non-zero on error-level findings.
- **Blind judging in `pe benchmark`** — `--judge-via {claude,codex,auggie,opencode}`
  routes the rubric prompt through a different agent than the one that generated
  the prompt. `--judge-model <name>` overrides the API model for the judge call.
  Addresses Auggie audit issue #11 ("same model generates and judges").
- **GitHub Actions CI** — `.github/workflows/ci.yml` runs the 50-test suite on
  Ubuntu + macOS across Python 3.12 / 3.13 / 3.14 on every push and PR.
- **PyPI release workflow** — `.github/workflows/release.yml` publishes sdist +
  wheel via PyPI Trusted Publishing (OIDC) on tag push. Requires one-time PyPI
  setup of the `pypi` environment publisher.
- **PyPI distribution name is `prompt-enhancer-cli`** — the bare name
  `prompt-enhancer` was already claimed on PyPI by an unrelated project. The
  GitHub repo, the `prompt_enhancer` import package, and the `pe` /
  `prompt-enhancer` CLI binaries are unchanged. Only the install line
  changes: `pip install prompt-enhancer-cli`.
- Test suite grew from 38 → 50 (added lint and blind-judge coverage).
- Legacy scripts (`prompt-install.py`, `prompt-benchmark.py`) no longer hard-code
  `/Users/hongphuc/.pyenv/...` paths — now use `sys.executable` (audit issue #8).
- Homebrew formula updated to `python@3.13`.
- Version drift between `cli.py` / `__init__.py` / `pyproject.toml` resolved.

## v1.0.1 (2026-06-04)
- Added LICENSE (MIT), CONTRIBUTING.md
- Rewritten README as proper open source project
- Added PyPI classifiers to pyproject.toml

## v1.0.0 (2026-06-04)
- Unified CLI: `prompt-enhancer {enhance,install,benchmark,store}`
- Auto-store: every enhancement logged to `~/.prompt-enhancer/store.jsonl`
- Homebrew formula: `brew install hongphuc5497/tap/prompt-enhancer`
- Install script: `curl install.sh | sh`
- `--json` mode for AI agent consumption
- 6 enhancement profiles: senior-dev, architect, reviewer, sre, product, mentor

## v0.2.0 (2026-06-04)
- `prompt-benchmark.py`: 7-dimension rubric scoring
- `prompt-install.py`: pipe into agent configs (Claude, Codex, Cursor, etc.)
- Verified against Auggie's native `--enhance-prompt` flag
- 4.8× tool-call reduction in agent behavior tests

## v0.1.0 (2026-06-03)
- Initial release: `prompt-enhancer.py`
- Reverse-engineered from Auggie's Ctrl+P Prompt Enhancer
- 7-section system prompt output (Role, Context, Rules, Tech, Format, Pitfalls, Examples)
- Workspace context auto-discovery (AGENTS.md, CLAUDE.md, package.json)
- Zero dependencies (Python stdlib only)
