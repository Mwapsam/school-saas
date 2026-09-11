#!/usr/bin/env python3
"""
Phase E: Migrate LEGACY templates from core/base.html to appropriate layouts.
Configurable for batch processing by module (hr, academic, subjects, etc).

Usage:
  python migrate_phase_e_batch.py hr
  python migrate_phase_e_batch.py academic
  python migrate_phase_e_batch.py --all
"""
import os
import re
import sys
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates', 'core')

# Module configurations: base_dir -> (layout, icon)
# layout: 'list.html', 'detail.html', 'form.html', 'dashboard.html'
# icon: FontAwesome class
MODULE_CONFIGS = {
    'hr': {
        'base_dir': os.path.join(TEMPLATES_DIR, 'hr'),
        'default_layout': 'list.html',
        'default_icon': 'fa-users',
        'files': {
            'leave/attendance_register': ('list.html', 'fa-clipboard-list'),
            'leave/attendance_report': ('list.html', 'fa-chart-bar'),
            'leave/leave_balance_report': ('list.html', 'fa-balance-scale'),
            'leave/leave_list': ('list.html', 'fa-list'),
            'payroll/group_detail': ('detail.html', 'fa-briefcase'),
            'payroll/payslip_generate': ('form.html', 'fa-file-invoice-dollar'),
            'payroll/payslip_list': ('list.html', 'fa-receipt'),
            'payroll/payslip_report': ('list.html', 'fa-chart-bar'),
            'payroll/payslip_settings': ('form.html', 'fa-cog'),
            'payroll/settings_landing': ('list.html', 'fa-cogs'),
            'settings/cashier_settings': ('form.html', 'fa-cog'),
            'settings/landing': ('list.html', 'fa-home'),
        }
    },
    'academic': {
        'base_dir': os.path.join(TEMPLATES_DIR, 'academic'),
        'default_layout': 'list.html',
        'default_icon': 'fa-graduation-cap',
        'files': {
            'academic_years': ('list.html', 'fa-calendar'),
            'attendance': ('list.html', 'fa-clipboard-list'),
            'attendance_dashboard': ('dashboard.html', 'fa-chart-pie'),
            'attendance_daywise_report': ('list.html', 'fa-chart-bar'),
            'attendance_label_edit': ('form.html', 'fa-edit'),
            'attendance_management': ('list.html', 'fa-users-cog'),
            'attendance_register': ('list.html', 'fa-list-check'),
            'attendance_report': ('list.html', 'fa-print'),
            'attendance_reports': ('list.html', 'fa-file-alt'),
            'attendance_settings': ('form.html', 'fa-cog'),
            'batches': ('list.html', 'fa-sitemap'),
            'batch_detail': ('detail.html', 'fa-info-circle'),
            'school_calendar': ('list.html', 'fa-calendar-alt'),
            'subjects': ('list.html', 'fa-book'),
            'teachers': ('list.html', 'fa-chalkboard-user'),
            'timetables': ('list.html', 'fa-clock'),
        }
    },
    'subjects': {
        'base_dir': os.path.join(TEMPLATES_DIR, 'subjects'),
        'default_layout': 'list.html',
        'default_icon': 'fa-book',
        'files': {
            'center': ('list.html', 'fa-home'),
            'class_subjects': ('list.html', 'fa-book'),
            'link_batches': ('form.html', 'fa-link'),
            'skill_sets_list': ('list.html', 'fa-star'),
            'skillset_detail': ('detail.html', 'fa-star'),
        }
    },
    'reports': {
        'base_dir': os.path.join(TEMPLATES_DIR, 'reports'),
        'default_layout': 'list.html',
        'default_icon': 'fa-chart-bar',
        'files': {
            'generated_reports': ('list.html', 'fa-file-pdf'),
            'generation': ('form.html', 'fa-plus-circle'),
            'report_template_preview': ('detail.html', 'fa-eye'),
            'template_list': ('list.html', 'fa-list'),
        }
    },
    'settings': {
        'base_dir': os.path.join(TEMPLATES_DIR, 'settings'),
        'default_layout': 'list.html',
        'default_icon': 'fa-cog',
        'files': {
            'configuration': ('form.html', 'fa-cogs'),
            'enrollment_conflicts': ('list.html', 'fa-exclamation-circle'),
            'manage_class_batch': ('form.html', 'fa-sitemap'),
            'roles/list': ('list.html', 'fa-users'),
            'roles/detail': ('detail.html', 'fa-user'),
        }
    },
    'enquiry': {
        'base_dir': os.path.join(TEMPLATES_DIR, 'enquiry'),
        'default_layout': 'list.html',
        'default_icon': 'fa-envelope',
        'files': {
            'confirm_delete': ('form.html', 'fa-trash'),
            'detail': ('detail.html', 'fa-envelope-open'),
            'form': ('form.html', 'fa-envelope'),
            'list': ('list.html', 'fa-inbox'),
        }
    },
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
        return False, f"File not found"

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if already migrated
        if 'core/layouts/' in content:
            return False, f"Already migrated"

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


def process_module(module_name):
    """Process all files in a module."""
    if module_name not in MODULE_CONFIGS:
        print(f"[ERROR] Unknown module: {module_name}")
        print(f"Available modules: {', '.join(MODULE_CONFIGS.keys())}")
        return 1

    config = MODULE_CONFIGS[module_name]
    files_config = config['files']

    print(f"[MIGRATION] Phase E {module_name.upper()} ({len(files_config)} files)")

    success_count = 0
    for filename, (layout, icon) in files_config.items():
        filepath = os.path.join(config['base_dir'], f"{filename}.html")
        ok, msg = migrate_file(filepath, layout, icon)

        status = "[OK]" if ok else "[SKIP]"
        print(f"  {status} {filename}.html - {msg}")
        if ok:
            success_count += 1

    print(f"[RESULT] {success_count}/{len(files_config)} files migrated\n")
    return 0


def main():
    parser = argparse.ArgumentParser(description='Phase E template migration')
    parser.add_argument('module', nargs='?', default=None, help='Module to migrate (hr, academic, etc.)')
    parser.add_argument('--all', action='store_true', help='Migrate all modules')
    args = parser.parse_args()

    if args.all:
        print("[MIGRATION] Phase E — All Modules")
        total_success = 0
        total_files = 0
        for module in MODULE_CONFIGS.keys():
            config = MODULE_CONFIGS[module]
            total_files += len(config['files'])
            process_module(module)
        return 0
    elif args.module:
        return process_module(args.module)
    else:
        print("Usage: python migrate_phase_e_batch.py <module> | --all")
        print(f"Modules: {', '.join(MODULE_CONFIGS.keys())}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
