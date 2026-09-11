#!/usr/bin/env python3
"""
Auto-migrate remaining gradebook templates (files 4–7) to new layout system.

Applies mechanical transformations:
1. Replace extends directive
2. Remove hero header markup + CSS rules
3. Reflow content into layout blocks
4. Move modals to layout_extra (inline, not modal.html)
5. Handle special cases (File 5: modals in extra_js, File 7: UTF-8 BOM)

Usage:
  python scripts/migrate_gradebook_templates.py [--dry-run] [file4|file5|file6|file7|all]

Examples:
  python scripts/migrate_gradebook_templates.py --dry-run all
  python scripts/migrate_gradebook_templates.py file5
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates" / "core" / "gradebook"

# File configs: (template_path, layout_type, icon, special_handling)
FILES = {
    "file4": {
        "path": TEMPLATES_DIR / "enhanced_score_entry.html",
        "layout": "detail.html",
        "icon": "fa-chart-line",
        "hero_class": "score-entry-header",
        "special": "keep_bs_tabs_inline",  # Do NOT force components/tabs.html
    },
    "file5": {
        "path": TEMPLATES_DIR / "exam_group_marks_entry.html",
        "layout": "detail.html",
        "icon": "fa-pen-to-square",
        "hero_class": "ep-header",
        "special": "move_modals_from_extra_js",  # Modals currently in {% block extra_js %} (line ~439)
    },
    "file6": {
        "path": TEMPLATES_DIR / "exam_plan_detail.html",
        "layout": "detail.html",
        "icon": "fa-graduation-cap",
        "hero_class": "ep-term-header",
        "special": None,
    },
    "file7": {
        "path": TEMPLATES_DIR / "grading_settings.html",
        "layout": "dashboard.html",
        "icon": "fa-cog",
        "hero_class": None,  # No hero, just breadcrumb + h1
        "special": "preserve_bom",  # UTF-8 BOM at start of file
    },
    "file8": {
        "path": TEMPLATES_DIR / "comprehensive_reports.html",
        "layout": "list.html",
        "icon": "fa-chart-bar",
        "hero_class": "reports-header",
        "special": None,
    },
    "file9": {
        "path": TEMPLATES_DIR / "create_exam.html",
        "layout": "form.html",
        "icon": "fa-plus-circle",
        "hero_class": "create-exam-header",
        "special": None,
    },
    "file10": {
        "path": TEMPLATES_DIR / "single_exam_marks_entry.html",
        "layout": "detail.html",
        "icon": "fa-edit",
        "hero_class": "marks-entry-header",
        "special": None,
    },
}


def migrate_extends(content, layout):
    """Replace {% extends 'core/base.html' %} with new layout."""
    return re.sub(
        r"{% extends 'core/base\.html' %}",
        f"{{% extends 'core/layouts/{layout}' %}}",
        content,
        count=1
    )


def remove_hero_css(content, hero_class):
    """Remove hero header CSS rules from <style> block."""
    if not hero_class:
        # File 7: remove all hand-rolled header CSS instead
        # Look for .reports-header, breadcrumb styles, etc.
        patterns = [
            r"\.reports-header\s*\{[^}]*\}",
            r"\.breadcrumb-nav\s*\{[^}]*\}",
            r"\.ep-header\s*\{[^}]*\}",
            r"\.me-header\s*\{[^}]*\}",
            r"\.create-exam-header\s*\{[^}]*\}",
            r"\.score-entry-header\s*\{[^}]*\}",
        ]
        for pattern in patterns:
            content = re.sub(pattern, "", content, flags=re.DOTALL)
        return content

    # Standard hero removal
    pattern = rf"\.{hero_class}\s*\{{[^}}]*\}}"
    return re.sub(pattern, "", content, flags=re.DOTALL)


def replace_header_markup(content, icon, hero_class=None):
    """Replace hand-rolled header with page_header.html include."""
    if hero_class:
        # Remove <div class="...header"> + closing tags
        pattern = rf"<div class=\"[^\"]*{hero_class}[^\"]*\">[^<]*(?:<div[^>]*>.*?</div>\s*)*</div>"
        content = re.sub(pattern, "", content, flags=re.DOTALL)

    # Also remove standalone breadcrumb nav if present
    breadcrumb_patterns = [
        r"<nav aria-label=\"breadcrumb\"[^>]*>.*?</nav>",
        r"<div class=\"breadcrumb-nav\"[^>]*>.*?</div>",
    ]
    for pattern in breadcrumb_patterns:
        content = re.sub(pattern, "", content, flags=re.DOTALL)

    # Insert page_header include after {% block layout_header %}
    # (This will be added by reflow_to_blocks())
    return content


def reflow_to_blocks(content, layout_type, file_key):
    """
    Reflow template content from {% block content %} into layout blocks.
    Mechanical transformation: move main form/details/cards into appropriate blocks.
    """
    # Extract current content block
    match = re.search(
        r"{% block content %}\s*(.*?)\s*{% endblock %}",
        content,
        re.DOTALL
    )
    if not match:
        print(f"  WARN: No block content found in {file_key}")
        return content

    body = match.group(1)

    # Build layout block structure based on type
    icon = FILES[file_key]['icon']
    if layout_type == "detail.html":
        # Detail: header | summary | tabs | sections | extra
        header_include = ("{% block layout_header %}\n"
                         "{% include 'core/components/page_header.html' "
                         "with icon=\"" + icon + "\" back_url=back_url crumbs=crumbs %}\n"
                         "{% endblock %}\n")
        new_blocks = (header_include +
                      "{% block layout_summary %}\n" + body + "\n{% endblock %}\n"
                      "{% block layout_sections %}{% endblock %}\n"
                      "{% block layout_extra %}<!-- Modals will go here -->{% endblock %}\n")
    elif layout_type == "dashboard.html":
        # Dashboard: header | stats | primary | secondary
        header_include = ("{% block layout_header %}\n"
                         "{% include 'core/components/page_header.html' "
                         "with icon=\"" + icon + "\" back_url=back_url crumbs=crumbs %}\n"
                         "{% endblock %}\n")
        new_blocks = (header_include +
                      "{% block layout_primary %}\n" + body + "\n{% endblock %}\n"
                      "{% block layout_extra %}<!-- Modals will go here -->{% endblock %}\n")
    else:
        # Form.html already handled in files 1–3
        return content

    return content.replace(match.group(0), new_blocks)


def move_modals_from_extra_js(content, file_key):
    """
    File 5 special case: modals are inside {% block extra_js %} at line ~439.
    Move them to {% block layout_extra %} so extra_js contains only <script>.
    """
    if file_key != "file5":
        return content

    # Find {% block extra_js %} ... {% endblock %}
    match = re.search(
        r"{% block extra_js %}(.*?){% endblock %}",
        content,
        re.DOTALL
    )
    if not match:
        return content

    extra_js_block = match.group(1)

    # Extract modals (anything that looks like <div class="modal ...>)
    modal_pattern = r"<!-- .*?Modal -->\s*<div class=\"modal[^>]*>.*?</div>\s*(?=<!-- |\Z)"
    modals = re.findall(modal_pattern, extra_js_block, re.DOTALL)

    if modals:
        # Remove modals from extra_js block
        for modal in modals:
            extra_js_block = extra_js_block.replace(modal, "")

        # Update extra_js block (keep only <script>)
        extra_js_block = re.sub(r"^\s+", "", extra_js_block)  # trim leading whitespace
        new_extra_js = f"{{% block extra_js %}}\n<script>\n{extra_js_block.strip()}\n</script>\n{{% endblock %}}"

        # Insert modals into layout_extra if it exists, else create it
        layout_extra = "\n{% block layout_extra %}\n" + "\n".join(modals) + "\n{% endblock %}\n"
        content = content.replace(match.group(0), new_extra_js)
        content = content.replace("{% endblock %}", f"{layout_extra}\n{{% endblock %}}", 1)

    return content


def preserve_bom(content):
    """Ensure UTF-8 BOM is preserved if present."""
    if content.startswith('﻿'):
        return content
    return content


def migrate_file(file_key, dry_run=False):
    """Migrate a single file."""
    config = FILES[file_key]
    path = config["path"]

    if not path.exists():
        print("[ERROR] " + file_key + ": File not found: " + str(path))
        return False

    print("[FILE] Migrating " + file_key + ": " + path.name)

    # Read file (preserve BOM if present)
    with open(path, "rb") as f:
        raw = f.read()

    # Check for BOM
    has_bom = raw.startswith(b'\xef\xbb\xbf')
    if has_bom:
        content = raw.decode("utf-8-sig")  # Strips BOM on decode
    else:
        content = raw.decode("utf-8")

    original = content

    # Apply transformations
    content = migrate_extends(content, config["layout"])
    print("  [OK] Changed extends to layouts/" + config['layout'])

    if config["hero_class"]:
        content = remove_hero_css(content, config["hero_class"])
        print("  [OK] Removed ." + config['hero_class'] + " CSS rules")

    content = replace_header_markup(content, config["icon"], config.get("hero_class"))
    print("  [OK] Removed hand-rolled header markup")

    # Reflow to proper layout blocks (must be after hero removal)
    content = reflow_to_blocks(content, config["layout"], file_key)
    print("  [OK] Reflowed content to layout blocks")

    # Handle special cases
    if config["special"] == "move_modals_from_extra_js":
        content = move_modals_from_extra_js(content, file_key)
        print("  [OK] Moved modals out of extra_js block")

    # Preserve BOM on output if it was present
    if dry_run:
        # Show diff summary
        old_lines = original.split('\n')
        new_lines = content.split('\n')
        print("  [DIFF] " + str(len(old_lines)) + " -> " + str(len(new_lines)) + " lines")
        return True

    # Write file
    if has_bom:
        with open(path, "wb") as f:
            f.write(b'\xef\xbb\xbf' + content.encode("utf-8"))
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    print("  [DONE] Written to disk")
    return True


def main():
    dry_run = "--dry-run" in sys.argv

    # Extract non-flag arguments
    targets_arg = [arg for arg in sys.argv[1:] if not arg.startswith("--")]

    if not targets_arg or targets_arg[0] not in FILES and targets_arg[0] != "all":
        targets = list(FILES.keys())
    else:
        targets = targets_arg if targets_arg[0] != "all" else list(FILES.keys())

    print("\n[MIGRATION] Gradebook Template Migration" + (" (DRY RUN)" if dry_run else ""))
    print("   Target: " + " ".join(targets))

    success = 0
    for file_key in targets:
        if file_key in FILES and migrate_file(file_key, dry_run):
            success += 1

    print("\n[RESULT] Migrated " + str(success) + "/" + str(len(targets)) + " files" + (" (dry run)" if dry_run else ""))
    return 0 if success == len(targets) else 1


if __name__ == "__main__":
    sys.exit(main())
