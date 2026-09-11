#!/usr/bin/env python3
"""
Phase E Misc: Migrate remaining single-page apps and misc templates.
"""
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates', 'core')

# Misc files: relative_path -> (layout, icon)
# NOTE: 'dashboard' is excluded (unique landing page with bespoke Fedena-style CSS grid,
# not a CRUD screen; kept on core/base.html with inline styles)
MISC_FILES = {
    'configuration': ('form.html', 'fa-cogs'),
    'programs': ('list.html', 'fa-graduation-cap'),
    'configuration/school_settings': ('form.html', 'fa-school'),
    'configuration/activity_catalogue': ('form.html', 'fa-list'),
    'settings/configuration': ('form.html', 'fa-cog'),
    'users/index': ('list.html', 'fa-users'),
    'news/index': ('list.html', 'fa-newspaper'),
    'communication/index': ('list.html', 'fa-envelope'),
    'library/index': ('list.html', 'fa-book'),
    'hostel/index': ('list.html', 'fa-building'),
    'transport/index': ('list.html', 'fa-bus'),
    'parents/detail': ('detail.html', 'fa-user-tie'),
    'assignments/index': ('list.html', 'fa-tasks'),
    'assignments/detail': ('detail.html', 'fa-file-alt'),
}


def migrate_extends(content, layout):
    """Replace {% extends 'core/base.html' %} with the appropriate layout."""
    pattern = r"{%\s*extends\s+['\"]core/base\.html['\"]\s*%}"
    replacement = f"{{% extends 'core/layouts/{layout}' %}}"
    return re.sub(pattern, replacement, content)


def remove_inline_styles(content):
    """Remove {% block extra_css %} and inline <style> blocks."""
    content = re.sub(
        r'{%\s*block\s+extra_css\s*%}.*?{%\s*endblock\s*%}',
        '',
        content,
        flags=re.DOTALL | re.IGNORECASE
    )
    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
    return content


def remove_page_header_div(content):
    """Remove hand-rolled page-header divs and related markup."""
    patterns = [
        r'<div\s+class="[^"]*page-header[^"]*"[^>]*>.*?</div>',
        r'<nav[^>]*aria-label="breadcrumb"[^>]*>.*?</nav>',
        r'<!-- Breadcrumb -->.*?<!-- /Breadcrumb -->',
    ]
    result = content
    for pattern in patterns:
        result = re.sub(pattern, '', result, flags=re.DOTALL | re.IGNORECASE)
    return result


def add_layout_blocks(content, layout):
    """Wrap content in appropriate layout_* blocks based on layout type."""
    pattern = r'{%\s*block\s+content\s*%}(.*?){%\s*endblock\s*%}'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        return content

    inner_content = match.group(1).strip()

    if layout == 'form.html':
        block_name = 'layout_form'
    elif layout == 'list.html':
        block_name = 'layout_table'
    elif layout == 'detail.html':
        block_name = 'layout_sections'
    elif layout == 'dashboard.html':
        block_name = 'layout_primary'
    else:
        block_name = 'layout_primary'

    wrapped = f"{{% block {block_name} %}}\n{inner_content}\n{{% endblock %}}"
    return re.sub(pattern, wrapped, content, flags=re.DOTALL)


def add_page_header(content, icon):
    """Add page_header component after layout_header block."""
    if 'layout_header' in content:
        pattern = r'({%\s*block\s+layout_header\s*%})(.*?)({%\s*endblock\s*%})'
        replacement = f"\\1\n{{% include 'core/components/page_header.html' with icon='{icon}' back_url=back_url crumbs=crumbs %}}\n\\3"
        return re.sub(pattern, replacement, content, flags=re.DOTALL)
    else:
        pattern = r'({% extends.*?%}\n)'
        replacement = f"\\1\n{{% block layout_header %}}\n{{% include 'core/components/page_header.html' with icon='{icon}' back_url=back_url crumbs=crumbs %}}\n{{% endblock %}}\n"
        return re.sub(pattern, replacement, content, flags=re.DOTALL)


def migrate_file(filepath, layout, icon):
    """Migrate a single template file."""
    if not os.path.exists(filepath):
        return False, "File not found"

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if already migrated
        if 'core/layouts/' in content:
            return False, "Already migrated"

        # Apply transformations
        content = migrate_extends(content, layout)
        content = remove_inline_styles(content)
        content = remove_page_header_div(content)
        content = add_page_header(content, icon)
        content = add_layout_blocks(content, layout)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return True, f"Migrated to {layout}"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    print("[MIGRATION] Phase E Misc Single-Page Apps (14 files; dashboard excluded)")

    success_count = 0
    for filename, (layout, icon) in MISC_FILES.items():
        filepath = os.path.join(TEMPLATES_DIR, f"{filename}.html")
        ok, msg = migrate_file(filepath, layout, icon)

        status = "[OK]" if ok else "[SKIP]"
        print(f"  {status} {filename}.html - {msg}")
        if ok:
            success_count += 1

    print(f"[RESULT] {success_count}/{len(MISC_FILES)} files migrated")
    return 0 if success_count == len(MISC_FILES) else 1


if __name__ == "__main__":
    sys.exit(main())
