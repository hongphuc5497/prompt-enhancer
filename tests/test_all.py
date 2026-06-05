"""
Test suite for prompt-enhancer. Stdlib unittest only — zero dependencies.

Run:
    python3 -m pytest tests/ -v
    python3 -m unittest discover tests/ -v

Or from the repo root:
    python3 -m pytest
"""

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


if __name__ == "__main__":
    unittest.main()
