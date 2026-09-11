#!/usr/bin/env python3
"""
Phase D: Migrate 7 admission LEGACY templates from core/base.html to appropriate layouts.
Removes hand-rolled header markup and inline styles, adds page_header components.
"""
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates', 'core', 'admission')

# Phase D admission files: layout type, icon
PHASE_D_FILES = {
    "application": {"layout": "form.html", "icon": "fa-user-plus"},
    "batch_assignment_detail": {"layout": "detail.html", "icon": "fa-list-check"},
    "batch_assignment_list": {"layout": "list.html", "icon": "fa-list-check"},
    "diagnostics": {"layout": "form.html", "icon": "fa-stethoscope"},
    "list_api": {"layout": "list.html", "icon": "fa-file-alt"},
    "management_list": {"layout": "list.html", "icon": "fa-file-alt"},
    "report": {"layout": "detail.html", "icon": "fa-file-pdf"},
}


def migrate_extends(content, layout):
    """Replace {% extends 'core/base.html' %} with the appropriate layout."""
    pattern = r"{%\s*extends\s+['\"]core/base\.html['\"]\s*%}"
    replacement = f"{{% extends 'core/layouts/{layout}' %}}"
    return re.sub(pattern, replacement, content)


def remove_page_header_div(content):
    """Remove hand-rolled page-header divs and breadcrumb nav elements."""
    patterns = [
        # Hand-rolled .mgmt-header style divs
        r'<div\s+class="mgmt-header"[^>]*>.*?</div>',
        # Generic page-header divs with breadcrumb + h1
        r'<div\s+class="[^"]*page-header[^"]*"[^>]*>.*?</div>',
        # Standalone breadcrumb navs
        r'<nav[^>]*aria-label="breadcrumb"[^>]*>.*?</nav>',
        # Inline breadcrumb divs
        r'<!-- Breadcrumb -->.*?<!-- /Breadcrumb -->',
    ]
    result = content
    for pattern in patterns:
        result = re.sub(pattern, '', result, flags=re.DOTALL | re.IGNORECASE)
    return result


def add_layout_blocks(content, layout):
    """Wrap content in appropriate layout_* blocks based on layout type."""
    # Extract content from {% block content %}...{% endblock %}
    pattern = r'{%\s*block\s+content\s*%}(.*?){%\s*endblock\s*%}'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        return content

    inner_content = match.group(1).strip()

    if layout == "form.html":
        block_name = "layout_form"
    elif layout == "list.html":
        block_name = "layout_table"
    elif layout == "detail.html":
        block_name = "layout_sections"
    else:
        block_name = "layout_primary"

    wrapped = f"{{% block {block_name} %}}\n{inner_content}\n{{% endblock %}}"
    return re.sub(pattern, wrapped, content, flags=re.DOTALL)


def add_page_header(content, icon):
    """Add page_header component after layout_header block."""
    # Check if layout_header block already exists
    if "layout_header" in content:
        # Insert page_header into existing layout_header block
        pattern = r'({%\s*block\s+layout_header\s*%})(.*?)({%\s*endblock\s*%})'
        replacement = f"\\1\n{{% include 'core/components/page_header.html' with icon='{icon}' back_url=back_url crumbs=crumbs %}}\n\\3"
        return re.sub(pattern, replacement, content, flags=re.DOTALL)
    else:
        # Create a new layout_header block after extends
        pattern = r'({% extends.*?%}\n)'
        replacement = f"\\1\n{{% block layout_header %}}\n{{% include 'core/components/page_header.html' with icon='{icon}' back_url=back_url crumbs=crumbs %}}\n{{% endblock %}}\n"
        return re.sub(pattern, replacement, content, flags=re.DOTALL)


def remove_inline_styles(content):
    """Remove {% block extra_css %} and inline <style> blocks."""
    # Remove {% block extra_css %}...{% endblock %} including content
    content = re.sub(
        r'{%\s*block\s+extra_css\s*%}.*?{%\s*endblock\s*%}',
        '',
        content,
        flags=re.DOTALL | re.IGNORECASE
    )
    # Remove standalone <style>...</style> blocks
    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
    return content


def migrate_file(filename, layout, icon):
    """Migrate a single template file."""
    filepath = os.path.join(TEMPLATES_DIR, f"{filename}.html")

    if not os.path.exists(filepath):
        print(f"  [SKIP] File not found: {filename}.html")
        return False

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Apply transformations
        content = migrate_extends(content, layout)
        content = remove_inline_styles(content)
        content = remove_page_header_div(content)
        content = add_page_header(content, icon)
        content = add_layout_blocks(content, layout)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  [OK] Migrated to {layout}")
        return True
    except Exception as e:
        print(f"  [ERR] {filename}.html: {e}")
        return False


def main():
    print("[MIGRATION] Phase D Admission LEGACY Template Migration")
    print(f"   Target: {len(PHASE_D_FILES)} files")

    success_count = 0
    for filename, config in PHASE_D_FILES.items():
        print(f"  [FILE] Migrating {filename}.html")
        if migrate_file(filename, config["layout"], config["icon"]):
            success_count += 1

    print(f"[RESULT] Migrated {success_count}/{len(PHASE_D_FILES)} files")
    return 0 if success_count == len(PHASE_D_FILES) else 1


if __name__ == "__main__":
    sys.exit(main())
