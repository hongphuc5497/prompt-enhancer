# Legacy standalone scripts

These are the **original, unmaintained** single-file versions of Prompt Enhancer,
kept for reference and offline/no-install use. They are **not** part of the
distributed package — `pip install prompt-enhancer-cli` and the Homebrew formula
ship only the `prompt_enhancer` package under [`../src`](../src).

| Script | Superseded by |
|--------|---------------|
| `prompt-enhancer.py` | `pe persona` / `pe enhance-task` |
| `prompt-benchmark.py` | `pe benchmark` |
| `prompt-install.py` | `pe install` |
| `prompt-store.py` | `pe store` / `pe dashboard` |

They run directly from this directory (their cross-references resolve relative to
their own location):

```bash
python3 legacy/prompt-enhancer.py "a senior Rust developer"
```

New development and the test suite target the package only. Do not add features
here — port them to `src/prompt_enhancer/` instead.
