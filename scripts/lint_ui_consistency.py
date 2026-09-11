#!/usr/bin/env python
"""
UI consistency lint — Phase 1 of the UI consolidation plan (see
docs/UI_COMPONENTS.md).

Rejects *newly introduced* lines in feature templates (templates/core/**,
excluding core/components/, core/layouts/, and core/base.html itself) that:

  - add a <style> block, or
  - hand-write a raw Bootstrap `class="table ..."` / `class="modal ..."`
    instead of using components/table_open.html or components/modal.html.

This is deliberately diff-aware, not a whole-tree scan: the app currently
has ~213 templates that predate this component system and are migrated
incrementally (Phase 2), so flagging all of that existing debt would be
noise. This script only stops *new* debt from being added while the
migration is in progress. Once Phase 2/3 are complete, this can be swapped
for a whole-tree scan.

Usage:
    python scripts/lint_ui_consistency.py [<base-ref>]

    <base-ref> defaults to "origin/main" — the script diffs the current
    working tree (including uncommitted changes) against it. In CI, run on
    a clean checkout of the PR branch and pass the PR's target branch.

Exit code 1 if any violation is found, 0 otherwise.
"""
import re
import subprocess
import sys

EXCLUDED_PREFIXES = (
    "templates/core/components/",
    "templates/core/layouts/",
    "templates/core/base.html",
)

STYLE_TAG_RE = re.compile(r"<style\b")
CLASS_ATTR_RE = re.compile(r'class="([^"]*)"')


def has_raw_class_token(line: str, token: str) -> bool:
    """True if `token` appears as a whole class name in any class="..."
    attribute on this line — not merely as a substring. A naive \\b-bounded
    regex would wrongly flag legitimate classes like "table-export-btn" or
    "pinewood-table" ('-' counts as a word boundary too), so split each
    class="..." value on whitespace and compare tokens exactly instead."""
    for class_value in CLASS_ATTR_RE.findall(line):
        if token in class_value.split():
            return True
    return False


def is_excluded(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def get_diff(base_ref: str) -> str:
    # Two-dot diff against the working tree (not base_ref...HEAD, which only
    # compares commits and silently ignores uncommitted changes — exactly
    # the changes this script needs to catch during local development).
    result = subprocess.run(
        ["git", "diff", "--unified=0", base_ref, "--", "templates/core/**/*.html"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0 and not result.stdout:
        # Fall back to diffing against the working tree if base_ref doesn't resolve
        result = subprocess.run(
            ["git", "diff", "--unified=0", "--", "templates/core/**/*.html"],
            capture_output=True, text=True, check=False,
        )
    return result.stdout


def find_violations(diff_text: str):
    violations = []
    current_file = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if current_file is None or is_excluded(current_file):
            continue
        added_line = line[1:]
        if STYLE_TAG_RE.search(added_line):
            violations.append((current_file, "new <style> block", added_line.strip()))
        if has_raw_class_token(added_line, "table"):
            violations.append((current_file, 'raw class="table" — use components/table_open.html', added_line.strip()))
        if has_raw_class_token(added_line, "modal"):
            violations.append((current_file, 'raw class="modal" — use components/modal.html', added_line.strip()))
    return violations


def main():
    base_ref = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    diff_text = get_diff(base_ref)
    violations = find_violations(diff_text)
    if not violations:
        print("UI consistency lint: no new violations.")
        return 0
    print(f"UI consistency lint: {len(violations)} new violation(s):\n")
    for path, reason, snippet in violations:
        print(f"  {path}: {reason}\n    {snippet}\n")
    print(
        "See docs/UI_COMPONENTS.md — feature templates should compose the "
        "shared components instead of hand-writing styles/tables/modals."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
