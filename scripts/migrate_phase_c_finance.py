#!/usr/bin/env python3
"""Migrate Phase C (11 LEGACY finance templates) to new layout system."""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates" / "core" / "finance"

# Phase C LEGACY finance files (layout type inferred from name pattern)
PHASE_C_FILES = {
    "collections/create": {"layout": "form.html", "icon": "fa-calendar-check"},
    "currency_configuration": {"layout": "form.html", "icon": "fa-money-bill-wave"},
    "family_accounts": {"layout": "list.html", "icon": "fa-users"},
    "fee_receipts": {"layout": "list.html", "icon": "fa-receipt"},
    "fee_structure": {"layout": "list.html", "icon": "fa-file-invoice"},
    "particular_wise_student_transaction_report": {"layout": "list.html", "icon": "fa-chart-bar"},
    "quickbooks_settings": {"layout": "form.html", "icon": "fa-quickbooks"},
    "quickbooks_webhook_review": {"layout": "list.html", "icon": "fa-flag"},
    "reports": {"layout": "list.html", "icon": "fa-chart-line"},
    "settings": {"layout": "list.html", "icon": "fa-cog"},
    "track": {"layout": "list.html", "icon": "fa-chart-line"},
}

def migrate_extends(content, layout):
    """Replace {% extends 'core/base.html' %} with new layout."""
    return re.sub(
        r"{% extends 'core/base\.html' %}",
        f"{{% extends 'core/layouts/{layout}' %}}",
        content,
        count=1
    )

def remove_page_header_div(content):
    """Remove hand-rolled <div class="page-header"> and related markup."""
    # Match various page-header div patterns
    patterns = [
        # <div class="page-header">...</div>
        r"<div class=\"page-header[^>]*>.*?</div>\s*",
        # <nav class="breadcrumb-nav">...</nav>
        r"<nav[^>]*breadcrumb[^>]*>.*?</nav>\s*",
        # <div class="page-header d-flex">...</div>
        r"<div class=\"page-header d-flex[^>]*>.*?</div>\s*",
        # Hand-rolled breadcrumb nav with <ol class="breadcrumb">
        r"<nav[^>]*>.*?<ol class=\"breadcrumb\">.*?</ol>.*?</nav>\s*",
    ]
    for pattern in patterns:
        content = re.sub(pattern, "", content, flags=re.DOTALL, count=1)
    return content

def add_layout_blocks(content, layout_type):
    """Wrap content in proper layout blocks."""
    # Extract main content from {% block content %}...{% endblock %}
    match = re.search(
        r"{% block content %}\s*(.*?)\s*{% endblock %}",
        content,
        re.DOTALL
    )
    if not match:
        print(f"    WARN: No content block found")
        return content

    body = match.group(1)

    # Build layout block structure
    if layout_type == "list.html":
        # For list: filters | table | pagination | extra
        new_blocks = (
            "{% block layout_filters %}\n"
            "<!-- Filters will be extracted and moved here -->\n"
            "{% endblock %}\n\n"
            "{% block layout_table %}\n"
            + body +
            "\n{% endblock %}\n\n"
            "{% block layout_pagination %}{% endblock %}\n\n"
            "{% block layout_extra %}{% endblock %}"
        )
    elif layout_type == "detail.html":
        new_blocks = (
            "{% block layout_summary %}\n"
            + body +
            "\n{% endblock %}\n\n"
            "{% block layout_sections %}{% endblock %}\n\n"
            "{% block layout_extra %}{% endblock %}"
        )
    elif layout_type == "form.html":
        new_blocks = (
            "{% block layout_form %}\n"
            + body +
            "\n{% endblock %}\n\n"
            "{% block layout_extra %}{% endblock %}"
        )
    else:
        return content

    return content.replace(match.group(0), new_blocks)

def add_page_header(content, icon):
    """Add page_header include after layout_header."""
    # Check if page_header already exists
    if "page_header" in content:
        return content

    # Find {% block layout_header %} if it exists, or add it
    if "{% block layout_header %}" not in content:
        # Add layout_header block at the beginning after page_title
        match = re.search(r"({% block page_title %}[^}]*{% endblock %})", content)
        if match:
            insert_pos = match.end()
            header_block = f"\n\n{{% block layout_header %}}\n{{% include 'core/components/page_header.html' with icon='{icon}' back_url=back_url crumbs=crumbs %}}\n{{% endblock %}}\n"
            content = content[:insert_pos] + header_block + content[insert_pos:]
    else:
        # Add page_header inside existing layout_header block
        content = re.sub(
            r"({% block layout_header %})\n",
            rf"\1\n{{% include 'core/components/page_header.html' with icon='{icon}' back_url=back_url crumbs=crumbs %}}\n",
            content
        )

    return content

def migrate_file(filename, config):
    """Migrate a single file."""
    path = TEMPLATES_DIR / f"{filename}.html"

    if not path.exists():
        print(f"  SKIP {filename}.html (not found)")
        return False

    print(f"  [FILE] Migrating {filename}.html")

    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    content = original

    # Apply transformations
    content = migrate_extends(content, config["layout"])
    content = remove_page_header_div(content)
    content = add_layout_blocks(content, config["layout"])
    content = add_page_header(content, config["icon"])

    if content == original:
        print(f"    -- No changes made")
        return False

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"    [OK] Migrated to layouts/{config['layout']}")
    return True

def main():
    print("\n[MIGRATION] Phase C Finance LEGACY Template Migration")
    print(f"   Target: {len(PHASE_C_FILES)} files")

    success = 0
    for filename, config in PHASE_C_FILES.items():
        if migrate_file(filename, config):
            success += 1

    print(f"\n[RESULT] Migrated {success}/{len(PHASE_C_FILES)} files")
    return 0 if success == len(PHASE_C_FILES) else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
