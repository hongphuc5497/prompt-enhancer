"""
Static analysis for system prompts — no LLM required.

Heuristic checks that catch structural issues before scoring with `pe benchmark`:
    - Missing sections from the canonical 7-section rubric
    - Vague hedging language ("should", "try to", "maybe", ...)
    - Empty / stub sections
    - Naive contradictions ("always X" + "never X")
    - Length sanity (too short / runaway long)
    - Mixed heading levels

Severity levels:
    error    — likely to mis-steer an agent; should be fixed
    warning  — quality smell; worth reviewing
    info     — note only
"""

import re

from . import term

# Canonical sections and accepted synonyms (case-insensitive substring match).
CANONICAL_SECTIONS = [
    ("role",     ["role", "persona", "identity"]),
    ("context",  ["context", "background", "situation"]),
    ("rules",    ["rules", "behavioral", "behaviour", "principles"]),
    ("tech",     ["tech", "technical", "stack", "tools"]),
    ("format",   ["format", "output", "response"]),
    ("pitfalls", ["pitfalls", "guardrails", "avoid", "constraints", "anti-patterns"]),
    ("examples", ["examples", "sample", "demonstration"]),
]

VAGUE_TERMS = [
    "maybe", "perhaps", "kind of", "sort of", "ideally", "try to",
    "where possible", "if possible", "consider ", "you might",
    "you could", "feel free", "in general",
]

# Heading regex: markdown ATX (# .. ######) at start of line.
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def lint(prompt_text):
    """Return a list of findings: each is dict(severity, code, line, message)."""
    findings = []
    if not prompt_text or not prompt_text.strip():
        findings.append({"severity": "error", "code": "empty",
                         "line": 1, "message": "Prompt is empty."})
        return findings

    lines = prompt_text.splitlines()
    text_len = len(prompt_text)
    lower = prompt_text.lower()

    if text_len < 200:
        findings.append({"severity": "warning", "code": "too-short", "line": 1,
                         "message": f"Prompt is only {text_len} chars — likely missing detail."})
    if text_len > 8000:
        findings.append({"severity": "warning", "code": "too-long", "line": 1,
                         "message": f"Prompt is {text_len} chars — consider trimming."})

    # Section coverage
    headings = [(i + 1, m.group(1), m.group(2).lower())
                for i, line in enumerate(lines)
                for m in [HEADING_RE.match(line)] if m]
    heading_text = " ".join(h[2] for h in headings) + " " + lower
    for canonical, synonyms in CANONICAL_SECTIONS:
        if not any(s in heading_text for s in synonyms):
            findings.append({"severity": "warning", "code": f"missing-section:{canonical}",
                             "line": 1,
                             "message": f"No '{canonical}' section detected (tried: {', '.join(synonyms[:3])})."})

    # Mixed heading levels — if both H1 and H3+ appear without H2, flag it
    levels = sorted({len(h[1]) for h in headings})
    if len(levels) >= 2 and levels[0] == 1 and 2 not in levels:
        findings.append({"severity": "info", "code": "heading-skip",
                         "line": headings[0][0],
                         "message": "Heading hierarchy skips H2 — agents parse structure better with H1→H2→H3."})

    # Vague terms
    for i, line in enumerate(lines, start=1):
        ll = line.lower()
        for term in VAGUE_TERMS:
            if term in ll:
                findings.append({"severity": "warning", "code": "vague",
                                 "line": i,
                                 "message": f"Vague phrase '{term.strip()}' weakens the rule."})
                break  # one finding per line is enough

    # Naive contradiction detection: same verb after "always" and "never"
    always_verbs = set(re.findall(r"\balways\s+([a-z]+)\b", lower))
    never_verbs = set(re.findall(r"\bnever\s+([a-z]+)\b", lower))
    overlap = always_verbs & never_verbs
    for verb in sorted(overlap):
        findings.append({"severity": "error", "code": "contradiction",
                         "line": 1,
                         "message": f"Contradiction: prompt says both 'always {verb}' and 'never {verb}'."})

    # Stub EXAMPLES section: heading present but < 50 chars before next heading
    for idx, (lineno, _, htext) in enumerate(headings):
        if "example" in htext:
            next_lineno = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines) + 1
            body = "\n".join(lines[lineno:next_lineno - 1]).strip()
            if len(body) < 50:
                findings.append({"severity": "warning", "code": "empty-section:examples",
                                 "line": lineno,
                                 "message": "EXAMPLES section is empty or near-empty — agents need concrete examples."})
            break

    return findings


def score(findings):
    """Compute a 0-100 lint score. Errors weigh more than warnings."""
    if not findings:
        return 100
    penalty = 0
    for f in findings:
        sev = f["severity"]
        penalty += {"error": 15, "warning": 5, "info": 1}.get(sev, 1)
    return max(0, 100 - penalty)


def format_report(findings, score_value, color=True):
    """Format findings as a human-readable terminal report.

    Shares glyphs, the branded header, and the dim divider with the rest of
    the CLI via term.py. The `color` flag is honored explicitly so `pe lint
    --no-color` stays plain even on a TTY.
    """
    def col(text, name, bold=False):
        if not color:
            return text
        prefix = term.ANSI["bold"] if bold else ""
        return f"{prefix}{term.ANSI.get(name, '')}{text}{term.ANSI['reset']}"

    width = 60
    icons = {
        "error": col("✖", "red"),
        "warning": col("⚠", "yellow"),
        "info": col("ℹ", "cyan"),
    }
    lines = []
    if not findings:
        lines.append(f"  {icons['info']} No issues found.")
    else:
        for f in findings:
            icon = icons.get(f["severity"], "•")
            loc = col(f"L{f['line']:>3}", "dim")
            lines.append(f"  {icon} {loc}  [{f['code']}] {f['message']}")
    counts = {sev: sum(1 for f in findings if f["severity"] == sev)
              for sev in ("error", "warning", "info")}
    summary = (f"  errors: {counts['error']}   warnings: {counts['warning']}"
               f"   info: {counts['info']}   score: {score_value}/100")
    bar = col(term.BOX["h"] * width, "dim")
    title = col("  ⚡ pe lint — static analysis", "cyan", bold=True)
    return "\n".join([title, bar, *lines, "", summary, bar])
