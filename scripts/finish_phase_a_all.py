#!/usr/bin/env python3
"""Finish Phase A: remove <style> blocks and add page_header includes."""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates" / "core"

# Non-gradebook Phase A PARTIAL files
PHASE_A_OTHER = [
    ("fees/fee_masters.html", "detail"),
    ("fees/student_management.html", "detail"),
    ("finance/collections/list.html", "list"),
    ("admission/detail.html", "detail"),
    ("batch_transfer/batch_transfer_detail.html", "detail"),
    ("students/detail.html", "detail"),
    ("students/list_api.html", "list"),
]

def remove_style_block(content):
    """Remove entire {% block extra_css %} ... {% endblock %} or <style>...</style>."""
    content = re.sub(
        r"{% block extra_css %}\s*\n<style>.*?</style>\s*\n{% endblock %}\n",
        "",
        content,
        flags=re.DOTALL
    )
    content = re.sub(
        r"<style>.*?</style>\s*\n?",
        "",
        content,
        flags=re.DOTALL
    )
    return content

def add_page_header_if_missing(content):
    """Add page_header include after {% block layout_header %} if not present."""
    if "page_header" in content:
        return content  # Already has page_header

    # Find {% block layout_header %} and add page_header include
    pattern = r"({% block layout_header %})\n"
    replacement = r"\1\n{% include 'core/components/page_header.html' with icon='fa-file' back_url=back_url crumbs=crumbs %}\n"
    content = re.sub(pattern, replacement, content)
    return content

def main():
    count = 0
    for rel_path, layout_type in PHASE_A_OTHER:
        filepath = TEMPLATES_DIR / rel_path
        if not filepath.exists():
            print(f"  SKIP {rel_path} (not found)")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            original = f.read()

        modified = remove_style_block(original)
        modified = add_page_header_if_missing(modified)

        if modified != original:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(modified)
            style_before = original.count("<style")
            style_after = modified.count("<style")
            header_before = original.count("page_header")
            header_after = modified.count("page_header")
            print(f"  OK {rel_path} (style: {style_before}->{style_after}, header: {header_before}->{header_after})")
            count += 1
        else:
            print(f"  -- {rel_path} (no change)")

    print(f"\n[DONE] Processed {count}/{len(PHASE_A_OTHER)} files")

if __name__ == "__main__":
    main()
