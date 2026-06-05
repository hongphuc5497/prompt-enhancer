#!/usr/bin/env python3
"""
Prompt Benchmark — measures prompt quality before and after enhancement.

Two evaluation modes:
  1. STATIC (default): LLM-as-judge scores the prompt text on 7 dimensions
     using the SurePrompts Quality Rubric (no execution needed).
  2. DYNAMIC (--execute): Runs both prompts against test cases, then an LLM
     judge scores the outputs on task completion quality.

The 7-Dimension SurePrompts Rubric:
  Role Clarity · Context Sufficiency · Instruction Specificity ·
  Format Structure · Example Quality · Constraint Tightness · Output Validation
  Each scored 1–5, max 35.

Usage:
  # Score a single prompt
  python3 prompt-benchmark.py --prompt raw-idea.txt

  # Compare before vs after enhancement
  python3 prompt-benchmark.py --before raw-idea.txt --after enhanced-prompt.md

  # Full pipeline: enhance + benchmark in one shot
  python3 prompt-benchmark.py --enhance "a Rust dev who..."

  # Dynamic: run prompts against test cases, compare output quality
  python3 prompt-benchmark.py --before raw.txt --after enhanced.md --execute --tests test_cases.json
"""

import json
import os
import sys
import argparse
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════

def load_config():
    """Load config from env vars and ~/.prompt-enhancer.env (shared with enhancer)."""
    env_file = Path.home() / ".prompt-enhancer.env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

    return {
        "api_key": os.environ.get("LLM_API_KEY", ""),
        "base_url": os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"),
        "model": os.environ.get("LLM_MODEL", "deepseek-chat"),
        # Use a stronger model for judging (more consistent scoring)
        "judge_model": os.environ.get("JUDGE_MODEL", os.environ.get("LLM_MODEL", "deepseek-chat")),
    }


# ═══════════════════════════════════════════════════════════════════
# LLM Call
# ═══════════════════════════════════════════════════════════════════

def call_llm(prompt, config, model=None, max_tokens=4096, temperature=0.3):
    """Call OpenAI-compatible API. Lower temperature for judging (consistency)."""
    url = f"{config['base_url'].rstrip('/')}/v1/chat/completions"
    body = json.dumps({
        "model": model or config["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {config['api_key']}")

    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode())
        return result["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════════════════
# 7-Dimension Rubric Scoring (Static Analysis)
# ═══════════════════════════════════════════════════════════════════

RUBRIC_PROMPT = """You are a prompt quality evaluator. Score the following prompt on 7 dimensions using the SurePrompts Quality Rubric. Each dimension is scored 1 (worst) to 5 (best).

## Scoring Dimensions

1. **Role Clarity** — Does the prompt assign a specific, coherent role?
   - 5: Explicit role with scope, voice, expertise level, posture
   - 3: Role present but vague ("helpful assistant")
   - 1: No role; model guesses identity

2. **Context Sufficiency** — Does the prompt include everything needed?
   - 5: All relevant background, constraints, prior decisions, domain knowledge
   - 3: Some context; model will make assumptions
   - 1: Near-zero context; model will fabricate

3. **Instruction Specificity** — How precise is the task description?
   - 5: Task, sub-tasks, and success criteria named explicitly
   - 3: Task named; sub-steps implicit
   - 1: Vague verb, no sub-structure

4. **Format Structure** — Is the expected output format specified?
   - 5: Exact structure defined (schema, headers, tone, length), ideally with example
   - 3: Format named but not detailed
   - 1: No format instructions

5. **Example Quality** — Are examples well-chosen? (Score N/A as 5 if zero-shot is viable)
   - 5: 2-4 examples covering diverse cases + edge cases, or zero-shot is clearly viable
   - 3: 1-2 generic examples
   - 1: No examples, and task clearly needs them

6. **Constraint Tightness** — Are constraints specified?
   - 5: Explicit constraints covering known failure modes
   - 3: Some constraints, common failures unaddressed
   - 1: No constraints

7. **Output Validation** — Is there a plan for validating output?
   - 5: Machine-validated (schema, regex) or explicit human-review checklist
   - 3: Human-reviewed without checklist
   - 1: No validation path

## Score Interpretation
- 28-35: Production-ready
- 21-27: Working draft — fix lowest dimensions
- 14-20: Needs major revision
- 7-13: Rewrite from scratch

## Output Format
Return ONLY a JSON object. No explanation, no markdown fences:

{
  "role_clarity": {"score": N, "reasoning": "1 sentence"},
  "context_sufficiency": {"score": N, "reasoning": "1 sentence"},
  "instruction_specificity": {"score": N, "reasoning": "1 sentence"},
  "format_structure": {"score": N, "reasoning": "1 sentence"},
  "example_quality": {"score": N, "reasoning": "1 sentence"},
  "constraint_tightness": {"score": N, "reasoning": "1 sentence"},
  "output_validation": {"score": N, "reasoning": "1 sentence"},
  "total": N,
  "verdict": "production-ready|working-draft|needs-revision|rewrite",
  "summary": "1-2 sentence overall assessment"
}

## Prompt to Evaluate
---PROMPT_START---
{prompt_text}
---PROMPT_END---"""


def score_prompt(prompt_text: str, config: dict) -> dict:
    """Score a single prompt on the 7-dimension rubric."""
    judge_prompt = RUBRIC_PROMPT.replace("{prompt_text}", prompt_text)
    result = call_llm(judge_prompt, config, model=config["judge_model"], temperature=0.3)
    # Parse JSON from response (handle markdown fences)
    cleaned = result.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return json.loads(cleaned)


# ═══════════════════════════════════════════════════════════════════
# Dynamic Benchmark: Run prompts against test cases, score outputs
# ═══════════════════════════════════════════════════════════════════

OUTPUT_JUDGE_PROMPT = """You are evaluating the quality of two AI agent responses to the same task request. One was given a RAW prompt (vague, unenhanced). The other was given an ENHANCED prompt (structured system prompt).

## Task Context
{task_context}

## Test Input
{test_input}

## Response from RAW prompt
{raw_output}

## Response from ENHANCED prompt
{enhanced_output}

## Scoring (score each 1-10)

Score each response on:
1. **Task Completion**: Did it actually do what was asked?
2. **Quality**: Code quality, explanation clarity, correctness
3. **Structure**: Was the output well-organized?
4. **Contextual Fit**: Did it respect conventions and constraints?

Return ONLY JSON:
{{
  "raw": {{"task_completion": N, "quality": N, "structure": N, "contextual_fit": N, "total": N, "comment": "1 sentence"}},
  "enhanced": {{"task_completion": N, "quality": N, "structure": N, "contextual_fit": N, "total": N, "comment": "1 sentence"}},
  "winner": "raw|enhanced|tie",
  "delta_pct": N
}}"""


def run_dynamic_benchmark(raw_prompt: str, enhanced_prompt: str, test_cases: list, config: dict) -> dict:
    """Run both prompts against test cases and compare outputs."""
    results = []

    for i, tc in enumerate(test_cases):
        task = tc.get("task", f"Task {i+1}")
        user_input = tc.get("input", tc.get("prompt", ""))

        # Build full prompts
        raw_full = f"{raw_prompt}\n\nUser: {user_input}"
        enhanced_full = f"{enhanced_prompt}\n\nUser: {user_input}"

        # Run both
        raw_output = call_llm(raw_full, config, max_tokens=2048, temperature=0.7)
        enhanced_output = call_llm(enhanced_full, config, max_tokens=2048, temperature=0.7)

        # Judge
        judge_prompt = OUTPUT_JUDGE_PROMPT.replace("{task_context}", task).replace("{test_input}", user_input).replace("{raw_output}", raw_output[:3000]).replace("{enhanced_output}", enhanced_output[:3000])
        judge_result = call_llm(judge_prompt, config, model=config["judge_model"], temperature=0.2)
        cleaned = judge_result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        try:
            verdict = json.loads(cleaned)
        except json.JSONDecodeError:
            verdict = {"raw": {}, "enhanced": {}, "winner": "error", "delta_pct": 0}

        results.append({
            "test": task,
            "input": user_input,
            "verdict": verdict,
        })

    # Aggregate
    raw_scores = [r["verdict"]["raw"].get("total", 0) for r in results if "raw" in r["verdict"]]
    enhanced_scores = [r["verdict"]["enhanced"].get("total", 0) for r in results if "enhanced" in r["verdict"]]
    wins = sum(1 for r in results if r["verdict"].get("winner") == "enhanced")

    return {
        "results": results,
        "aggregate": {
            "raw_avg": sum(raw_scores) / len(raw_scores) if raw_scores else 0,
            "enhanced_avg": sum(enhanced_scores) / len(enhanced_scores) if enhanced_scores else 0,
            "total_tests": len(test_cases),
            "enhanced_wins": wins,
            "raw_wins": len(test_cases) - wins,
        }
    }


# ═══════════════════════════════════════════════════════════════════
# Report Formatting
# ═══════════════════════════════════════════════════════════════════

BAR = "═" * 60

def print_static_report(before: Optional[dict], after: Optional[dict]):
    """Print a side-by-side comparison of rubric scores."""
    dimensions = [
        ("role_clarity", "Role Clarity"),
        ("context_sufficiency", "Context Sufficiency"),
        ("instruction_specificity", "Instruction Specificity"),
        ("format_structure", "Format Structure"),
        ("example_quality", "Example Quality"),
        ("constraint_tightness", "Constraint Tightness"),
        ("output_validation", "Output Validation"),
    ]

    print(f"\n{BAR}")
    print("  PROMPT QUALITY BENCHMARK — SurePrompts 7-Dimension Rubric")
    print(f"{BAR}")

    if before:
        b_total = before.get("total", 0)
        b_v = before.get("verdict", "?")
        print(f"\n  BEFORE:  {b_total}/35  ({b_v})")
    if after:
        a_total = after.get("total", 0)
        a_v = after.get("verdict", "?")
        print(f"  AFTER:   {a_total}/35  ({a_v})")

    if before and after:
        delta = after.get("total", 0) - before.get("total", 0)
        symbol = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        pct = (delta / max(before.get("total", 1), 1)) * 100
        print(f"  DELTA:   {symbol}{abs(delta)} points ({pct:+.0f}%)\n")

    print(f"  {'Dimension':<28} {'BEFORE':>7} {'AFTER':>7} {'Δ':>5}")
    print(f"  {'-'*28} {'-'*7} {'-'*7} {'-'*5}")

    for key, label in dimensions:
        b_s = before.get(key, {}).get("score", "—") if before else "—"
        a_s = after.get(key, {}).get("score", "—") if after else "—"
        if isinstance(b_s, int) and isinstance(a_s, int):
            d = a_s - b_s
            d_str = f"+{d}" if d > 0 else str(d)
        else:
            d_str = "—"
        print(f"  {label:<28} {str(b_s):>7} {str(a_s):>7} {d_str:>5}")

    # Reasoning section
    if after:
        print(f"\n  AFTER — Dimension Analysis:")
        for key, label in dimensions:
            reasoning = after.get(key, {}).get("reasoning", "")
            if reasoning:
                print(f"    {label}: {reasoning}")

    if after:
        summary = after.get("summary", "")
        if summary:
            print(f"\n  Summary: {summary}")

    print(f"\n{BAR}")

    # Interpretation guide
    print("""
  Score Ranges:
    28-35  Production-ready — ship it
    21-27  Working draft — fix lowest dimensions
    14-20  Needs major revision — address 3 lowest scores
     7-13  Rewrite from scratch
""")


def print_dynamic_report(dynamic_result: dict):
    """Print output-quality benchmark results."""
    agg = dynamic_result["aggregate"]
    print(f"\n{BAR}")
    print("  DYNAMIC BENCHMARK — Output Quality Comparison")
    print(f"{BAR}")
    print(f"\n  Tests run: {agg['total_tests']}")
    print(f"  RAW avg score:      {agg['raw_avg']:.1f}/40")
    print(f"  ENHANCED avg score: {agg['enhanced_avg']:.1f}/40")
    improvement = agg['enhanced_avg'] - agg['raw_avg']
    print(f"  Improvement:        +{improvement:.1f} ({improvement/agg['raw_avg']*100:+.0f}%)" if improvement > 0 else f"  Change: {improvement:.1f}")
    print(f"  Enhanced wins:      {agg['enhanced_wins']}/{agg['total_tests']}")

    for r in dynamic_result["results"]:
        v = r["verdict"]
        winner = v.get("winner", "?")
        symbol = "✅" if winner == "enhanced" else ("➖" if winner == "tie" else "❌")
        print(f"\n  {symbol} {r['test']}")
        print(f"     Input: {r['input'][:80]}...")
        print(f"     RAW:      {v.get('raw', {}).get('total', '?')}/40 — {v.get('raw', {}).get('comment', '')}")
        print(f"     ENHANCED: {v.get('enhanced', {}).get('total', '?')}/40 — {v.get('enhanced', {}).get('comment', '')}")

    print(f"\n{BAR}")


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Prompt Benchmark — measure prompt quality before/after enhancement",
    )
    parser.add_argument("--prompt", type=str, help="Score a single prompt")
    parser.add_argument("--before", type=str, help="Path to raw/before prompt file")
    parser.add_argument("--after", type=str, help="Path to enhanced/after prompt file")
    parser.add_argument("--enhance", type=str, help="Enhance a seed idea via prompt-enhancer.py, then benchmark both")
    parser.add_argument("--enhancer-path", type=str,
                        default=str(Path(__file__).resolve().parent / "prompt-enhancer.py"),
                        help="Path to prompt-enhancer.py")
    parser.add_argument("--execute", action="store_true", help="Run dynamic benchmark (execute prompts, compare outputs)")
    parser.add_argument("--tests", type=str, default=None, help="Path to test cases JSON for dynamic benchmark")
    parser.add_argument("--python", type=str, default=sys.executable,
                        help="Python path for enhancer subprocess")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--save", type=str, help="Save benchmark results to file")
    args = parser.parse_args()

    config = load_config()
    if not config["api_key"]:
        print("Error: LLM_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # ── Mode 1: Single prompt scoring ──
    if args.prompt and not args.before and not args.after and not args.enhance:
        prompt_text = Path(args.prompt).expanduser().read_text() if os.path.isfile(args.prompt) else args.prompt
        scores = score_prompt(prompt_text, config)
        if args.json:
            print(json.dumps(scores, indent=2))
        else:
            print_static_report(None, scores)
        return

    # ── Mode 2: Enhance + benchmark ──
    if args.enhance:
        import subprocess
        print(f"Enhancing: {args.enhance[:60]}...", file=sys.stderr)
        result = subprocess.run(
            [args.python, args.enhancer_path, args.enhance],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            print(f"Enhancer failed: {result.stderr}", file=sys.stderr)
            sys.exit(1)

        # Parse enhancer output: first line is "Enhancing with..." on stderr, rest is the prompt
        enhanced = result.stdout.strip()
        # Extract just the system prompt (skip the "Enhancing with..." line)
        if "\n" in enhanced and enhanced.startswith("# System Prompt"):
            pass  # good, already just the prompt
        elif "\n# System Prompt" in enhanced:
            enhanced = enhanced[enhanced.index("# System Prompt"):]

        before_text = args.enhance  # the raw seed

        # Write enhanced to temp file for scoring
        enhanced_file = Path("/tmp/enhanced-benchmark.md")
        enhanced_file.write_text(enhanced)

        before_scores = score_prompt(before_text, config)
        after_scores = score_prompt(enhanced, config)

        if args.json:
            print(json.dumps({"before": before_scores, "after": after_scores}, indent=2))
        else:
            print_static_report(before_scores, after_scores)

        # Dynamic benchmark
        if args.execute:
            test_cases = []
            if args.tests:
                test_cases = json.loads(Path(args.tests).read_text())
            else:
                test_cases = [
                    {"task": "Code review request", "input": "Review this React component for performance issues"},
                    {"task": "Debug a bug", "input": "Users report that the login button doesn't work on mobile Safari"},
                    {"task": "Feature implementation", "input": "Add a search bar that filters results as you type"},
                ]
            dynamic = run_dynamic_benchmark(before_text, enhanced, test_cases, config)
            if args.json:
                print(json.dumps({"dynamic": dynamic}, indent=2))
            else:
                print_dynamic_report(dynamic)

            if args.save:
                Path(args.save).write_text(json.dumps({
                    "before": before_scores, "after": after_scores, "dynamic": dynamic
                }, indent=2))
        return

    # ── Mode 3: Compare before/after files ──
    before_text = Path(args.before).expanduser().read_text() if args.before else None
    after_text = Path(args.after).expanduser().read_text() if args.after else None

    before_scores = score_prompt(before_text, config) if before_text else None
    after_scores = score_prompt(after_text, config) if after_text else None

    if args.json:
        out = {}
        if before_scores: out["before"] = before_scores
        if after_scores: out["after"] = after_scores
        print(json.dumps(out, indent=2))
    else:
        print_static_report(before_scores, after_scores)

    if args.execute and before_text and after_text:
        test_cases = []
        if args.tests:
            test_cases = json.loads(Path(args.tests).read_text())
        else:
            test_cases = [
                {"task": "Code review", "input": "Review this code for bugs"},
                {"task": "Feature implementation", "input": "Add pagination to the list"},
            ]
        dynamic = run_dynamic_benchmark(before_text, after_text, test_cases, config)
        if args.json:
            print(json.dumps({"dynamic": dynamic}, indent=2))
        else:
            print_dynamic_report(dynamic)

    if args.save:
        Path(args.save).write_text(json.dumps({
            "before": before_scores, "after": after_scores
        }, indent=2))


if __name__ == "__main__":
    main()
