#!/usr/bin/env python3
"""Checks that must pass before the repository is made public: no project IDs, account emails, home paths,
or wording about a named customer pursuit, in the tree or (with --history) in any commit.

    python scripts/scrub_check.py [--history]
"""
from __future__ import annotations

import re
import subprocess
import sys

PATTERNS = {
    "gcp project id": re.compile(r"genial-union-\d+-\w+|\b[a-z][a-z0-9-]{4,28}-\d{6}\b"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@(?!anthropic\.com|example\.com|noreply)[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "home path": re.compile(r"/Users/[A-Za-z0-9._-]+|/home/[a-z_][a-z0-9_-]*/"),
    "customer pursuit wording": re.compile(
        r"(?i)(sell|selling|licen[cs]e sale)[^\n]{0,40}(gemini|agy|opus|licen[cs]es?)"
        r"|mitsubishi[^\n]{0,40}(leaders?|pm\b|product manager|customer|pursuit|audience|meeting|room)"
        r"|(customer|prospect|pursuit)[^\n]{0,20}mitsubishi"),
}
SKIP = (".venv/", "logs/", "demo/out/", "evals/cassettes/", "scripts/scrub_check.py")


def tracked() -> list[str]:
    return [f for f in subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.split("\n")
            if f and not f.startswith(SKIP)]


def main() -> int:
    findings = []
    for path in tracked():
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except (IsADirectoryError, FileNotFoundError):
            continue
        for name, rx in PATTERNS.items():
            for m in rx.finditer(text):
                findings.append(f"{path}: {name}: {m.group(0)[:60]}")
    if "--history" in sys.argv:
        log = subprocess.run(["git", "log", "-p", "--all"], capture_output=True, text=True).stdout
        for name, rx in PATTERNS.items():
            n = len(rx.findall(log))
            if n:
                findings.append(f"history: {name}: {n} occurrence(s)")
    for f in findings[:200]:
        print(f)
    print(f"scrub check: {'FAIL' if findings else 'clean'} ({len(findings)} finding(s))")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
