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
echo 'LLM_API_KEY=*** > ~/.prompt-enhancer.env

# Verify
prompt-enhancer version
```

## Running Tests

```bash
# Dry-run the enhancer (no API call)
prompt-enhancer benchmark --enhance "test" --json

# Check the store
prompt-enhancer store list
```

## Project Structure

```
src/prompt_enhancer/
├── cli.py          # Unified CLI (enhance, install, benchmark, store)
├── __init__.py     # Package metadata

prompt-enhancer.py  # Legacy standalone enhancer (stdlib only)
prompt-benchmark.py # Legacy standalone benchmark
prompt-install.py   # Legacy standalone installer
prompt-store.py     # Legacy standalone store
```

## Design Principles

- **Stdlib only**: The core tools (`prompt-enhancer.py`, `prompt-benchmark.py`) have zero dependencies beyond Python's stdlib. The pip package adds only `setuptools`.
- **Auto-store**: Every enhancement is logged automatically. No `--save` flag needed.
- **7-dimension rubric**: Benchmark scoring follows the SurePrompts Quality Rubric (Role Clarity, Context, Instructions, Format, Examples, Constraints, Validation).

## Pull Request Guidelines

1. Keep changes small and focused — one concern per PR.
2. Test locally: `prompt-enhancer enhance "test" --no-store`
3. Ensure the legacy scripts still work (`python3 prompt-enhancer.py "test"`).
4. Update the CHANGELOG if your change is user-facing.

## Issues

- **Bugs**: Include the exact command, expected output, and actual output.
- **Features**: Describe the use case and why you need it.
- **Enhancement profiles**: Proposals for new `--profile` values are welcome — include example seed→enhanced pairs.

## License

MIT. See [LICENSE](LICENSE).
