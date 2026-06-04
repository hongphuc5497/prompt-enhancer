# Changelog

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
