# Contributing to Prompt Enhancer

Thanks for your interest! Here's how to get started.

## Development Setup

```bash
# Clone
git clone https://github.com/hongphuc5497/prompt-enhancer.git
cd prompt-enhancer

# Install in editable mode
python3 -m pip install --user -e .

# Configure your LLM API key
echo 'LLM_API_KEY=sk-your-key' > ~/.prompt-enhancer.env

# Verify
prompt-enhancer version
```

## Running Tests

```bash
# Unit tests (stdlib only, no API key needed)
python3 -m unittest tests/test_all.py -v

# Check the store
pe store list
```

## Project Structure

```
src/prompt_enhancer/   # The distributed package (what pip / brew install)
├── cli.py             # Unified CLI (persona, enhance-task, install, benchmark, store, dashboard, lint, doctor)
├── agents.py          # --via delegation to existing agent CLIs
├── dashboard.py       # Analytics TUI
├── lint.py            # Static prompt analysis (no API key)
├── term.py / view.py  # Zero-dependency terminal UI primitives
└── __init__.py        # Package metadata + version (single source of truth)

legacy/                # Frozen standalone scripts — not packaged, kept for reference
├── prompt-enhancer.py
├── prompt-benchmark.py
├── prompt-install.py
└── prompt-store.py
```

## Design Principles

- **Stdlib only**: The package has zero runtime dependencies beyond Python's stdlib; the build needs only `setuptools`.
- **Auto-store**: Every enhancement is logged automatically. No `--save` flag needed.
- **7-dimension rubric**: Benchmark scoring follows the SurePrompts Quality Rubric (Role Clarity, Context, Instructions, Format, Examples, Constraints, Validation).

## Pull Request Guidelines

1. Keep changes small and focused — one concern per PR.
2. Test locally: `python3 -m unittest tests/test_all.py -v` and `pe persona "test" --no-store`.
3. The package under `src/prompt_enhancer/` is the source of truth; `legacy/` is frozen and not part of the test gate.
4. Update the CHANGELOG if your change is user-facing.

## Issues

- **Bugs**: Include the exact command, expected output, and actual output.
- **Features**: Describe the use case and why you need it.
- **Enhancement profiles**: Proposals for new `--profile` values are welcome — include example seed→enhanced pairs.

## License

MIT. See [LICENSE](LICENSE).
