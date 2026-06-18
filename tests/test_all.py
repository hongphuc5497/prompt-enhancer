"""
Test suite for prompt-enhancer. Stdlib unittest only — zero dependencies.

Run:
    python3 -m pytest tests/ -v
    python3 -m unittest discover tests/ -v

Or from the repo root:
    python3 -m pytest
"""

import argparse
import contextlib
import io
import itertools
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prompt_enhancer.cli import (
    load_config, collect_context, VERSION,
    store_save, store_read, store_delete, store_clear,
    copy_to_clipboard, _get_seed, die,
    AGENT_CONFIGS, PROFILES, STORE_FILE, STORE_DIR,
)
from prompt_enhancer.dashboard import (
    sparkline, bar_chart, load_records, compute_stats,
    parse_since,
)
from prompt_enhancer.agents import (
    _find_binary, get_available_agents, AGENT_ENHANCERS,
)
from prompt_enhancer import cli


# ═══════════════════════════════════════════════════════════════════
# Config Tests
# ═══════════════════════════════════════════════════════════════════

class TestConfig(unittest.TestCase):
    def test_load_config_no_file(self):
        """Config loading returns defaults when no env file."""
        # Patch both env vars AND env file loading
        with patch.dict(os.environ, {}, clear=True), \
             patch("pathlib.Path.exists", return_value=False):
            config = load_config()
        self.assertEqual(config["api_key"], "")
        self.assertIn("deepseek.com", config["base_url"])
        self.assertEqual(config["model"], "deepseek-chat")

    def test_load_config_from_env(self):
        """Config loading reads from environment variables."""
        with patch.dict(os.environ, {
            "LLM_API_KEY": "sk-test123",
            "LLM_BASE_URL": "https://api.test.com",
            "LLM_MODEL": "test-model",
        }):
            config = load_config()
        self.assertEqual(config["api_key"], "sk-test123")
        self.assertEqual(config["base_url"], "https://api.test.com")
        self.assertEqual(config["model"], "test-model")

    def test_base_url_strips_trailing_slash(self):
        """Trailing slashes are stripped from the base URL."""
        with patch.dict(os.environ, {"LLM_BASE_URL": "https://api.test.com/"}, clear=True), \
             patch("pathlib.Path.exists", return_value=False):
            config = load_config()
        self.assertEqual(config["base_url"], "https://api.test.com")

    def test_base_url_strips_v1_suffix(self):
        """A trailing /v1 is stripped so callers don't double the path."""
        with patch.dict(os.environ, {"LLM_BASE_URL": "https://api.test.com/v1"}, clear=True), \
             patch("pathlib.Path.exists", return_value=False):
            config = load_config()
        self.assertEqual(config["base_url"], "https://api.test.com")

    def test_base_url_strips_v1_with_trailing_slash(self):
        """A trailing /v1/ is normalized the same as /v1."""
        with patch.dict(os.environ, {"LLM_BASE_URL": "https://api.test.com/v1/"}, clear=True), \
             patch("pathlib.Path.exists", return_value=False):
            config = load_config()
        self.assertEqual(config["base_url"], "https://api.test.com")

    def test_version_is_string(self):
        self.assertIsInstance(VERSION, str)
        self.assertIn(".", VERSION)

    def test_agent_configs_valid(self):
        """All agent configs have required fields."""
        for name, cfg in AGENT_CONFIGS.items():
            self.assertIn("path", cfg)
            self.assertIn("desc", cfg)

    def test_profiles_list(self):
        """Profiles list is non-empty."""
        self.assertGreater(len(PROFILES), 0)
        self.assertIn("senior-dev", PROFILES)
        self.assertIn("architect", PROFILES)


# ═══════════════════════════════════════════════════════════════════
# Store Tests
# ═══════════════════════════════════════════════════════════════════

class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_file = Path(self.tmpdir) / "store.jsonl"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _patch_store(self):
        """Patch STORE_FILE to use temp file."""
        return patch("prompt_enhancer.cli.STORE_FILE", self.store_file)

    def test_save_and_read(self):
        with self._patch_store():
            rid = store_save("test seed", "# Enhanced prompt", agent="claude", project="/tmp")
            self.assertIsInstance(rid, str)
            records = store_read()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["seed"], "test seed")
            self.assertEqual(records[0]["enhanced"][:12], "# Enhanced p")
            self.assertEqual(records[0]["agent"], "claude")

    def test_read_empty_store(self):
        with self._patch_store():
            records = store_read()
            self.assertEqual(records, [])

    def test_delete(self):
        with self._patch_store():
            rid = store_save("seed", "enhanced")
            self.assertTrue(store_delete(rid))
            self.assertEqual(len(store_read()), 0)

    def test_delete_nonexistent(self):
        with self._patch_store():
            self.assertFalse(store_delete("nonexistent"))

    def test_clear(self):
        with self._patch_store():
            store_save("s1", "e1")
            store_save("s2", "e2")
            self.assertTrue(store_clear())
            self.assertEqual(len(store_read()), 0)

    def test_truncation(self):
        """Seed and enhanced content are truncated."""
        with self._patch_store():
            rid = store_save("x" * 1000, "y" * 10000)
            records = store_read()
            self.assertEqual(len(records), 1)
            self.assertLess(len(records[0]["seed"]), 600)
            self.assertLess(len(records[0]["enhanced"]), 6000)


# ═══════════════════════════════════════════════════════════════════
# Context Tests
# ═══════════════════════════════════════════════════════════════════

class TestContext(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.project = Path(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_project(self):
        """Empty directory produces empty context."""
        ctx = collect_context(str(self.project))
        self.assertEqual(ctx, "")

    def test_finds_agents_md(self):
        (self.project / "AGENTS.md").write_text("# Agent Rules\nUse pnpm.")
        ctx = collect_context(str(self.project))
        self.assertIn("AGENTS.md", ctx)
        self.assertIn("pnpm", ctx)

    def test_finds_package_json(self):
        (self.project / "package.json").write_text('{"name": "test"}')
        ctx = collect_context(str(self.project))
        self.assertIn("package.json", ctx)

    def test_truncates_large_files(self):
        (self.project / "AGENTS.md").write_text("x" * 5000)
        ctx = collect_context(str(self.project))
        self.assertIn("truncated", ctx)


# ═══════════════════════════════════════════════════════════════════
# Dashboard Tests
# ═══════════════════════════════════════════════════════════════════

class TestDashboard(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_file = Path(self.tmpdir) / "store.jsonl"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_records(self, n=3):
        records = []
        for i in range(n):
            records.append({
                "id": f"test-{i}",
                "timestamp": f"2026-06-04T15:{i:02d}:00Z",
                "seed": f"test seed {i}",
                "seed_length": 10,
                "enhanced": f"# Enhanced {i}",
                "enhanced_length": 12,
                "agent": "claude" if i % 2 == 0 else "codex",
                "project": "/tmp",
                "benchmark": {
                    "before": {"total": 8 + i, "verdict": "needs-revision"},
                    "after": {"total": 28 + i, "verdict": "production-ready"},
                },
                "model": "deepseek-chat",
                "version": VERSION,
            })
        return records

    def test_sparkline(self):
        result = sparkline([1, 2, 3, 4, 5, 6, 7, 8])
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_sparkline_empty(self):
        self.assertEqual(sparkline([]), "(no data)")

    def test_sparkline_ascii(self):
        # ASCII blocks: ._-~=+#@ (8 levels, indices 0-7)
        # Use explicit values that hit both low and high
        result = sparkline([0, 50, 88, 100], use_ascii=True, width=4)
        self.assertIn("@", result)  # 100 maps to highest block
        self.assertIn("#", result)  # 88 maps to index 6 (#)

    def test_bar_chart(self):
        items = [("claude", 10), ("codex", 5)]
        result = bar_chart(items)
        self.assertIn("claude", result)
        self.assertIn("10", result)

    def test_bar_chart_empty(self):
        self.assertEqual(bar_chart([]), "(no data)")

    def test_compute_stats_empty(self):
        stats = compute_stats([])
        self.assertEqual(stats["total"], 0)

    def test_compute_stats(self):
        records = self._make_records(3)
        stats = compute_stats(records)

        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["with_benchmark"], 3)
        self.assertGreater(stats["avg_after"], stats["avg_before"])
        self.assertGreater(stats["avg_delta"], 0)
        self.assertEqual(stats["failures"], 0)
        self.assertEqual(stats["pass_rate"], 100)

        # Agent effectiveness
        self.assertGreater(len(stats["agent_effectiveness"]), 0)

        # Velocity
        self.assertGreater(len(stats["velocity"]), 0)

        # Recent
        self.assertEqual(len(stats["recent"]), 3)

    def test_agent_delta_attributed_per_record(self):
        # Regression: deltas must attach to the agent of THIS record, not the
        # global last delta. Distinct deltas + a no-benchmark record catch the
        # old cross-contamination bug.
        records = [
            {"timestamp": "2026-06-04T15:00:00Z", "agent": "claude",
             "benchmark": {"before": {"total": 10}, "after": {"total": 30}}},  # +20
            {"timestamp": "2026-06-04T15:01:00Z", "agent": "codex",
             "benchmark": {"before": {"total": 5}, "after": {"total": 10}}},   # +5
            {"timestamp": "2026-06-04T15:02:00Z", "agent": "gpt"},             # no benchmark
        ]
        stats = compute_stats(records)
        eff = {agent: avg_d for agent, avg_d, _count, _fails in stats["agent_effectiveness"]}
        self.assertEqual(eff["claude"], 20)
        self.assertEqual(eff["codex"], 5)
        self.assertEqual(eff["gpt"], 0)  # no benchmark → no delta, not the global last

    def test_load_records_empty(self):
        records = load_records(self.store_file)
        self.assertEqual(records, [])

    def test_load_records(self):
        recs = self._make_records(2)
        with open(self.store_file, "w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
        loaded = load_records(self.store_file)
        self.assertEqual(len(loaded), 2)

    def test_parse_since_relative(self):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)

        result = parse_since("24h")
        self.assertIsNotNone(result)
        self.assertLess((now - result).total_seconds(), 86401)

        result = parse_since("7d")
        self.assertIsNotNone(result)
        self.assertLess((now - result).total_seconds(), 7 * 86400 + 1)

    def test_parse_since_iso(self):
        result = parse_since("2026-06-01")
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 6)
        self.assertEqual(result.day, 1)

    def test_parse_since_today(self):
        from datetime import datetime, timezone
        result = parse_since("today")
        self.assertIsNotNone(result)
        now = datetime.now(timezone.utc)
        self.assertEqual(result.day, now.day)

    def test_parse_since_invalid(self):
        self.assertIsNone(parse_since("not a date"))


# ═══════════════════════════════════════════════════════════════════
# Agent Tests
# ═══════════════════════════════════════════════════════════════════

class TestAgents(unittest.TestCase):
    def test_agent_enhancers_registered(self):
        """All expected agents have enhancers."""
        for agent in ["claude", "codex", "auggie", "opencode"]:
            self.assertIn(agent, AGENT_ENHANCERS)

    def test_find_binary_nonexistent(self):
        result = _find_binary(["nonexistent_binary_xyz_123"])
        self.assertIsNone(result)

    def test_get_available_agents(self):
        agents = get_available_agents()
        self.assertGreaterEqual(len(agents), 4)
        self.assertEqual(agents[0][0], "claude")

    def test_find_binary_returns_path(self):
        """find_binary returns a path for something that exists."""
        result = _find_binary(["python3", "python"])
        self.assertIsNotNone(result)
        self.assertIn("python", result)


# ═══════════════════════════════════════════════════════════════════
# CLI Tests
# ═══════════════════════════════════════════════════════════════════

class TestCLI(unittest.TestCase):
    def test_get_seed_from_args(self):
        """_get_seed extracts seed from argparse namespace."""
        args = MagicMock()
        args.seed = "test prompt"
        args.file = None
        result = _get_seed(args)
        self.assertEqual(result, "test prompt")

    def test_get_seed_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("file prompt content")
            f.flush()
            args = MagicMock()
            args.seed = None
            args.file = f.name
            result = _get_seed(args)
        self.assertEqual(result, "file prompt content")
        os.unlink(f.name)

    def test_get_seed_empty(self):
        args = MagicMock()
        args.seed = None
        args.file = None
        result = _get_seed(args)
        self.assertIsNone(result)

    def test_copy_to_clipboard_macos(self):
        """copy_to_clipboard uses pbcopy on macOS."""
        with patch("platform.system", return_value="Darwin"), \
             patch("subprocess.run") as mock_run:
            result = copy_to_clipboard("test text")
            mock_run.assert_called_once()
            self.assertTrue(result)

    def test_copy_to_clipboard_failure(self):
        """copy_to_clipboard returns False on failure."""
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", return_value=None):
            result = copy_to_clipboard("test")
            self.assertFalse(result)


# ═══════════════════════════════════════════════════════════════════
# Version consistency
# ═══════════════════════════════════════════════════════════════════

class TestVersion(unittest.TestCase):
    def test_version_match(self):
        """cli.py and __init__.py should have the same version."""
        from prompt_enhancer import __version__ as init_version
        self.assertEqual(init_version, VERSION)

    def test_python_minimum(self):
        """Project targets Python >= 3.12."""
        self.assertGreaterEqual(sys.version_info, (3, 12))


# ═══════════════════════════════════════════════════════════════════
# Lint module (pe lint)
# ═══════════════════════════════════════════════════════════════════

from prompt_enhancer import lint as lint_mod


class TestLint(unittest.TestCase):
    def test_empty_prompt_is_error(self):
        findings = lint_mod.lint("")
        codes = [f["code"] for f in findings]
        self.assertIn("empty", codes)
        self.assertEqual(findings[0]["severity"], "error")

    def test_clean_prompt_has_no_missing_sections(self):
        prompt = (
            "# System Prompt: Rust Senior Dev\n\n"
            "## Role\nSenior Rust engineer with 10 years of experience.\n\n"
            "## Context\nWorking on a high-throughput backend service.\n\n"
            "## Rules\n- Prefer iterators over manual loops.\n- Use Result, not panic.\n\n"
            "## Tech\n- tokio, axum, sqlx\n\n"
            "## Format\nReturn diffs in unified format.\n\n"
            "## Pitfalls\nDo not use unwrap() in library code.\n\n"
            "## Examples\nGiven a slice, return the sum: `slice.iter().sum()`\n"
        )
        findings = lint_mod.lint(prompt)
        missing = [f for f in findings if f["code"].startswith("missing-section:")]
        self.assertEqual(missing, [], f"unexpected missing sections: {missing}")

    def test_missing_sections_are_flagged(self):
        prompt = "# Just a role\n\nYou are a developer. Be helpful.\n" * 10
        findings = lint_mod.lint(prompt)
        codes = {f["code"] for f in findings}
        # Several canonical sections should be reported missing
        self.assertTrue(any(c.startswith("missing-section:") for c in codes))

    def test_vague_terms_flagged(self):
        prompt = "# Role\n" + ("- You should maybe try to be careful.\n" * 5) + ("- Detail line.\n" * 20)
        findings = lint_mod.lint(prompt)
        codes = [f["code"] for f in findings]
        self.assertIn("vague", codes)

    def test_contradiction_detection(self):
        prompt = "# Role\nAlways use semicolons. Never use semicolons in this project." + "\nmore text" * 30
        findings = lint_mod.lint(prompt)
        codes = [f["code"] for f in findings]
        self.assertIn("contradiction", codes)
        contradiction = next(f for f in findings if f["code"] == "contradiction")
        self.assertEqual(contradiction["severity"], "error")

    def test_score_is_100_when_clean(self):
        self.assertEqual(lint_mod.score([]), 100)

    def test_score_penalizes_errors_more_than_warnings(self):
        err = [{"severity": "error", "code": "x", "line": 1, "message": ""}]
        warn = [{"severity": "warning", "code": "x", "line": 1, "message": ""}]
        self.assertLess(lint_mod.score(err), lint_mod.score(warn))

    def test_format_report_renders(self):
        report = lint_mod.format_report([], 100, color=False)
        self.assertIn("pe lint", report)
        self.assertIn("100/100", report)


# ═══════════════════════════════════════════════════════════════════
# Blind judging wiring (pe benchmark --judge-via / --judge-model)
# ═══════════════════════════════════════════════════════════════════

class TestBlindJudge(unittest.TestCase):
    def test_benchmark_score_routes_to_agent_when_judge_via_set(self):
        from prompt_enhancer import cli as cli_mod
        fake_json = '{"role_clarity":{"score":5,"reasoning":"x"},"total":35,"verdict":"production-ready","summary":"x"}'
        with patch.object(cli_mod, "call_llm") as mock_api, \
             patch("prompt_enhancer.agents.run_via_agent", return_value=fake_json) as mock_agent:
            result = cli_mod.benchmark_score("prompt text", {"api_key": "", "base_url": "", "model": ""},
                                             judge_via="claude")
            mock_agent.assert_called_once()
            mock_api.assert_not_called()
            self.assertEqual(result["total"], 35)

    def test_benchmark_score_passes_judge_model_to_api(self):
        from prompt_enhancer import cli as cli_mod
        fake_json = '{"total":28,"verdict":"production-ready","summary":"x"}'
        with patch.object(cli_mod, "call_llm", return_value=fake_json) as mock_api:
            cli_mod.benchmark_score("prompt text",
                                    {"api_key": "k", "base_url": "u", "model": "default-model"},
                                    judge_model="gpt-4o")
            _, kwargs = mock_api.call_args
            self.assertEqual(kwargs.get("model"), "gpt-4o")

    def test_run_via_agent_unknown_raises(self):
        from prompt_enhancer.agents import run_via_agent
        with self.assertRaises(RuntimeError):
            run_via_agent("hi", "no-such-agent")


# ═══════════════════════════════════════════════════════════════════
# Shared terminal primitives (term.py)
# ═══════════════════════════════════════════════════════════════════

from prompt_enhancer import term


class TestTerm(unittest.TestCase):
    def test_display_width_counts_wide_and_ignores_ansi(self):
        self.assertEqual(term.display_width("⚡"), 2)
        self.assertEqual(term.display_width("中文"), 4)
        self.assertEqual(term.display_width("abc"), 3)
        colored = term.ANSI["cyan"] + "abc" + term.ANSI["reset"]
        self.assertEqual(term.display_width(colored), 3)

    def test_panel_rows_are_all_equal_width(self):
        p = term.panel("Title", "plain\nemoji ⚡ row\nCJK 中文 row",
                       width=40, use_ascii=True)
        widths = {term.display_width(line) for line in p.split("\n")}
        self.assertEqual(widths, {40})

    def test_truncate_respects_display_width(self):
        out = term.truncate("hello world this is long", 12)
        self.assertLessEqual(term.display_width(out), 12)
        self.assertTrue(out.endswith("…"))

    def test_rule_width_and_ascii_fallback(self):
        self.assertEqual(term.display_width(term.strip_ansi(term.rule(40))), 40)
        ascii_rule = term.strip_ansi(term.rule(10, use_ascii=True))
        self.assertEqual(ascii_rule, "-" * 10)

    def test_header_brands_title_and_right_aligns(self):
        lines = term.header("pe dashboard", "v9.9.9", width=60)
        self.assertEqual(len(lines), 2)
        title = term.strip_ansi(lines[0])
        self.assertIn("⚡ pe dashboard", title)
        self.assertTrue(title.endswith("v9.9.9"))
        self.assertEqual(term.display_width(title), 60)
        self.assertEqual(term.display_width(term.strip_ansi(lines[1])), 60)

    def test_footer_joins_and_handles_empty(self):
        self.assertEqual(term.footer([]), "")
        joined = term.strip_ansi(term.footer(["a", "b"], use_ascii=True))
        self.assertEqual(joined, "  a  |  b")

    def test_read_key_returns_sentinel_when_stdin_not_tty(self):
        # Force the non-TTY path so this is deterministic whether tests are
        # launched from a pipe or an interactive terminal.
        with patch("prompt_enhancer.term.sys.stdin") as stdin:
            stdin.isatty.return_value = False
            self.assertEqual(term.read_key(), term.NO_TTY)

    def test_copy_to_clipboard_detects_tool(self):
        with patch("prompt_enhancer.term.shutil.which", return_value="/usr/bin/pbcopy"), \
             patch("prompt_enhancer.term.subprocess.run") as run:
            self.assertTrue(term.copy_to_clipboard("hi"))
            run.assert_called_once()

    def test_copy_to_clipboard_returns_false_without_tool(self):
        with patch("prompt_enhancer.term.shutil.which", return_value=None):
            self.assertFalse(term.copy_to_clipboard("hi"))


# ═══════════════════════════════════════════════════════════════════
# Endpoint construction (call_llm /v1 handling)
# ═══════════════════════════════════════════════════════════════════

class TestEndpoint(unittest.TestCase):
    def test_endpoint_never_doubles_v1(self):
        f = cli._endpoint
        self.assertEqual(f("https://h", "chat/completions"), "https://h/v1/chat/completions")
        self.assertEqual(f("https://h/", "chat/completions"), "https://h/v1/chat/completions")
        self.assertEqual(f("https://h/v1", "chat/completions"), "https://h/v1/chat/completions")
        self.assertEqual(f("https://h/v1/", "chat/completions"), "https://h/v1/chat/completions")
        self.assertEqual(f("https://h/v1/chat/completions", "chat/completions"),
                         "https://h/v1/chat/completions")
        self.assertEqual(f("https://h/v1", "models"), "https://h/v1/models")


def _ok_response(payload):
    """A urlopen() return value usable as a context manager."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    cm = MagicMock()
    cm.__enter__.return_value = resp
    cm.__exit__.return_value = False
    return cm


class TestCallLLMRetry(unittest.TestCase):
    CONFIG = {"api_key": "k", "base_url": "https://h", "model": "m"}

    def test_retries_then_succeeds(self):
        import urllib.error
        ok = _ok_response({"choices": [{"message": {"content": "hello"}}]})
        attempts = {"n": 0}

        def fake(req, timeout=None):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise urllib.error.URLError("temporary")
            return ok

        with patch("prompt_enhancer.cli.urllib.request.urlopen", side_effect=fake), \
             patch("prompt_enhancer.cli.time.sleep") as slept:
            out = cli.call_llm("p", self.CONFIG)
        self.assertEqual(out, "hello")
        self.assertEqual(attempts["n"], 3)
        self.assertEqual(slept.call_count, 2)

    def test_raises_llmerror_after_exhausting_retries(self):
        import urllib.error
        with patch("prompt_enhancer.cli.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("down")), \
             patch("prompt_enhancer.cli.time.sleep"):
            with self.assertRaises(cli.LLMError):
                cli.call_llm("p", self.CONFIG)

    def test_non_retryable_status_raises_immediately(self):
        import urllib.error
        err = urllib.error.HTTPError("u", 400, "Bad Request", None, None)
        with patch("prompt_enhancer.cli.urllib.request.urlopen", side_effect=err), \
             patch("prompt_enhancer.cli.time.sleep") as slept:
            with self.assertRaises(cli.LLMError):
                cli.call_llm("p", self.CONFIG)
            slept.assert_not_called()


# ═══════════════════════════════════════════════════════════════════
# collect_context hardening (dir pruning + sensitive-file skipping)
# ═══════════════════════════════════════════════════════════════════

class TestContextHardening(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.project = Path(self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_prunes_ignored_dirs(self):
        (self.project / "AGENTS.md").write_text("root rules here")
        vendored = self.project / "node_modules" / "pkg"
        vendored.mkdir(parents=True)
        (vendored / "CLAUDE.md").write_text("vendored noise")
        gitdir = self.project / ".git"
        gitdir.mkdir()
        (gitdir / "AGENTS.md").write_text("git internal noise")
        ctx = collect_context(str(self.project))
        self.assertIn("root rules here", ctx)
        self.assertNotIn("vendored noise", ctx)
        self.assertNotIn("git internal noise", ctx)

    def test_prefers_shallowest_match(self):
        (self.project / "AGENTS.md").write_text("ROOT level")
        sub = self.project / "sub"
        sub.mkdir()
        (sub / "AGENTS.md").write_text("NESTED level")
        ctx = collect_context(str(self.project))
        self.assertIn("ROOT level", ctx)
        self.assertNotIn("NESTED level", ctx)

    def test_is_sensitive(self):
        self.assertTrue(cli._is_sensitive(".env"))
        self.assertTrue(cli._is_sensitive(".env.local"))
        self.assertTrue(cli._is_sensitive("server.pem"))
        self.assertTrue(cli._is_sensitive("id_rsa"))
        self.assertFalse(cli._is_sensitive("AGENTS.md"))
        self.assertFalse(cli._is_sensitive("package.json"))


# ═══════════════════════════════════════════════════════════════════
# Command handlers (regression coverage for duration_ms + generator)
# ═══════════════════════════════════════════════════════════════════

class _DummyCM:
    """Stand-in for view.Spinner so handler tests don't spawn threads/timers."""
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestHandlers(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_dir = Path(self.tmpdir)
        self.store_file = self.store_dir / "store.jsonl"
        self.project = self.store_dir / "proj"
        self.project.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _common_patches(self):
        # A monotonic fake clock: each time.time() call advances 0.5s, so a
        # handler's (t0, end) pair yields a deterministic 500ms duration.
        clock = itertools.count(1000.0, 0.5)
        return [
            patch("prompt_enhancer.cli.STORE_FILE", self.store_file),
            patch("prompt_enhancer.cli.STORE_DIR", self.store_dir),
            patch("prompt_enhancer.view.Spinner", _DummyCM),
            patch("prompt_enhancer.view.log_progress"),
            patch("prompt_enhancer.cli.time.time", side_effect=lambda: next(clock)),
        ]

    def _run(self, fn, args, *extra_patches):
        buf = io.StringIO()
        with contextlib.ExitStack() as stack:
            for cm in self._common_patches() + list(extra_patches):
                stack.enter_context(cm)
            stack.enter_context(contextlib.redirect_stdout(buf))
            fn(args)
        return buf.getvalue()

    def _records(self):
        """Read the isolated temp store directly (the STORE_FILE patch is no
        longer active outside _run, so cli.store_read would hit the real file)."""
        if not self.store_file.exists():
            return []
        return [json.loads(line) for line in self.store_file.read_text().splitlines()
                if line.strip()]

    def test_persona_records_real_duration_and_generator(self):
        args = argparse.Namespace(
            seed="a rust dev", file=None, via=None, profile=None,
            project=str(self.project), no_context=True, concise=False,
            json=True, no_store=False, copy=False, raw=False)
        out = self._run(
            cli.cmd_persona, args,
            patch("prompt_enhancer.cli.load_config",
                  return_value={"api_key": "k", "base_url": "https://h", "model": "m"}),
            patch("prompt_enhancer.cli.call_llm", return_value="# System Prompt: X"),
        )
        payload = json.loads(out)
        self.assertEqual(payload["duration_ms"], 500)
        recs = self._records()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["duration_ms"], 500)
        self.assertEqual(recs[0]["generator"], "api")
        self.assertIsNone(recs[0]["agent"])

    def test_enhance_task_records_real_duration(self):
        args = argparse.Namespace(
            seed="fix the login bug", file=None, via=None,
            project=str(self.project), no_context=True,
            json=True, no_store=False, copy=False, raw=False)
        out = self._run(
            cli.cmd_enhance_task, args,
            patch("prompt_enhancer.cli.load_config",
                  return_value={"api_key": "k", "base_url": "https://h", "model": "m"}),
            patch("prompt_enhancer.cli.enhance_task", return_value="do the thing"),
        )
        payload = json.loads(out)
        self.assertEqual(payload["duration_ms"], 500)
        recs = self._records()
        self.assertEqual(recs[0]["duration_ms"], 500)
        self.assertEqual(recs[0]["generator"], "api")

    def test_enhance_task_via_passes_context_and_task_mode(self):
        (self.project / "AGENTS.md").write_text("PROJECT CONVENTIONS xyz")
        args = argparse.Namespace(
            seed="fix bug", file=None, via="claude",
            project=str(self.project), no_context=False,
            json=True, no_store=False, copy=False, raw=False)
        with patch("prompt_enhancer.agents.enhance", return_value="enhanced") as m:
            self._run(cli.cmd_enhance_task, args)
        m.assert_called_once()
        _, kwargs = m.call_args
        self.assertTrue(kwargs.get("task_mode"))
        self.assertIn("PROJECT CONVENTIONS xyz", kwargs.get("workspace_context", ""))
        recs = self._records()
        self.assertEqual(recs[0]["generator"], "claude")
        self.assertIsNone(recs[0]["agent"])

    def test_install_records_target_and_generator(self):
        args = argparse.Namespace(
            seed="a security reviewer", file=None, agent="claude", profile=None,
            project=str(self.project), no_context=True, dry_run=False, force=True,
            json=True, no_store=False, via=None)
        self._run(
            cli.cmd_install, args,
            patch("prompt_enhancer.cli.load_config",
                  return_value={"api_key": "k", "base_url": "https://h", "model": "m"}),
            patch("prompt_enhancer.cli.call_llm", return_value="# System Prompt: Reviewer"),
        )
        recs = self._records()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["agent"], "claude")       # install target
        self.assertEqual(recs[0]["generator"], "api")
        self.assertEqual(recs[0]["duration_ms"], 500)


if __name__ == "__main__":
    unittest.main()
