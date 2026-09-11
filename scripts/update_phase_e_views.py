#!/usr/bin/env python3
"""
Phase E: Add back_url and crumbs context to view classes.
Maps view classes to their corresponding templates and dashboard URLs.
"""

VIEW_UPDATES = {
    'core/view_modules/hr_leave_views.py': [
        {
            'class_name': 'EmployeeLeaveListView',
            'back_url_default': "reverse('core:hr_dashboard')",
            'crumbs': "[{'label': 'HR', 'url': reverse('core:hr_dashboard')}, {'label': 'Leave List'}]",
        },
        {
            'class_name': 'EmployeeAttendanceRegisterView',
            'back_url_default': "reverse('core:hr_dashboard')",
            'crumbs': "[{'label': 'HR', 'url': reverse('core:hr_dashboard')}, {'label': 'Attendance Register'}]",
        },
        {
            'class_name': 'DepartmentAttendanceReportView',
            'back_url_default': "reverse('core:hr_dashboard')",
            'crumbs': "[{'label': 'HR', 'url': reverse('core:hr_dashboard')}, {'label': 'Attendance Report'}]",
        },
        {
            'class_name': 'LeaveBalanceReportView',
            'back_url_default': "reverse('core:hr_dashboard')",
            'crumbs': "[{'label': 'HR', 'url': reverse('core:hr_dashboard')}, {'label': 'Leave Balance Report'}]",
        },
    ],
    'core/view_modules/hr_payroll_views.py': [
        {
            'class_name': 'PayrollSettingsLandingView',
            'back_url_default': "reverse('core:hr_dashboard')",
            'crumbs': "[{'label': 'HR', 'url': reverse('core:hr_dashboard')}, {'label': 'Payroll'}]",
        },
        {
            'class_name': 'PayrollGroupDetailView',
            'back_url_default': "reverse('core:hr_payroll_settings')",
            'crumbs': "[{'label': 'HR', 'url': reverse('core:hr_dashboard')}, {'label': 'Payroll', 'url': reverse('core:hr_payroll_settings')}, {'label': 'Group Detail'}]",
        },
        {
            'class_name': 'PayslipGenerateView',
            'back_url_default': "reverse('core:hr_payroll_settings')",
            'crumbs': "[{'label': 'HR', 'url': reverse('core:hr_dashboard')}, {'label': 'Payroll', 'url': reverse('core:hr_payroll_settings')}, {'label': 'Generate Payslip'}]",
        },
        {
            'class_name': 'PayslipListView',
            'back_url_default': "reverse('core:hr_payroll_settings')",
            'crumbs': "[{'label': 'HR', 'url': reverse('core:hr_dashboard')}, {'label': 'Payroll', 'url': reverse('core:hr_payroll_settings')}, {'label': 'Payslip List'}]",
        },
        {
            'class_name': 'PayslipSettingsView',
            'back_url_default': "reverse('core:hr_payroll_settings')",
            'crumbs': "[{'label': 'HR', 'url': reverse('core:hr_dashboard')}, {'label': 'Payroll', 'url': reverse('core:hr_payroll_settings')}, {'label': 'Settings'}]",
        },
        {
            'class_name': 'PayslipReportView',
            'back_url_default': "reverse('core:hr_payroll_settings')",
            'crumbs': "[{'label': 'HR', 'url': reverse('core:hr_dashboard')}, {'label': 'Payroll', 'url': reverse('core:hr_payroll_settings')}, {'label': 'Report'}]",
        },
    ],
    'core/view_modules/hr_settings_views.py': [
        {
            'class_name': 'HRSettingsLandingView',
            'back_url_default': "reverse('core:hr_dashboard')",
            'crumbs': "[{'label': 'HR', 'url': reverse('core:hr_dashboard')}, {'label': 'Settings'}]",
        },
        {
            'class_name': 'CashierSettingsView',
            'back_url_default': "reverse('core:hr_settings')",
            'crumbs': "[{'label': 'HR', 'url': reverse('core:hr_dashboard')}, {'label': 'Settings', 'url': reverse('core:hr_settings')}, {'label': 'Cashier Settings'}]",
        },
    ],
    'core/view_modules/enquiry_views.py': [
        {
            'class_name': 'EnquiryListView',
            'back_url_default': "reverse('core:dashboard')",
            'crumbs': "[{'label': 'Enquiry'}]",
        },
        {
            'class_name': 'EnquiryDetailView',
            'back_url_default': "reverse('core:enquiry_list')",
            'crumbs': "[{'label': 'Enquiry', 'url': reverse('core:enquiry_list')}, {'label': 'Detail'}]",
        },
        {
            'class_name': 'EnquiryCreateView',
            'back_url_default': "reverse('core:enquiry_list')",
            'crumbs': "[{'label': 'Enquiry', 'url': reverse('core:enquiry_list')}, {'label': 'New Enquiry'}]",
        },
        {
            'class_name': 'EnquiryDeleteView',
            'back_url_default': "reverse('core:enquiry_list')",
            'crumbs': "[{'label': 'Enquiry', 'url': reverse('core:enquiry_list')}, {'label': 'Confirm Delete'}]",
        },
    ],
}

import re
import os

def add_context_to_view(filepath, class_name, back_url_default, crumbs):
    """Add back_url and crumbs to a view's get_context_data method."""
    if not os.path.exists(filepath):
        return False, "File not found"

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find the class definition
        class_pattern = rf"class\s+{class_name}\s*\("
        if not re.search(class_pattern, content):
            return False, "Class not found"

        # Check if already has back_url
        if f"{class_name}" in content and "back_url" in content:
            # Simple heuristic: if back_url appears near the class, assume already done
            class_match = re.search(class_pattern, content)
            if class_match:
                section_start = class_match.start()
                section_end = min(section_start + 2000, len(content))
                if "back_url" in content[section_start:section_end]:
                    return False, "Already updated"

        # Find get_context_data return statement
        pattern = rf"(class\s+{class_name}\s*\([^)]*\):.*?def\s+get_context_data\s*\([^)]*\):.*?)(return\s+context)"

        def replace_func(match):
            method_content = match.group(1)
            return_stmt = match.group(2)

            # Add context updates before return
            new_code = f"""{method_content}context['back_url'] = self.request.GET.get('back', {back_url_default})
        context['crumbs'] = {crumbs}
        {return_stmt}"""
            return new_code

        new_content = re.sub(pattern, replace_func, content, flags=re.DOTALL)

        if new_content == content:
            return False, "Could not find return statement in get_context_data"

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return True, "Updated"
    except Exception as e:
        return False, f"Error: {str(e)}"


def main():
    print("[UPDATE] Phase E View Context Variables\n")

    total_updates = 0
    total_files = 0

    for filepath, updates_list in VIEW_UPDATES.items():
        if not os.path.exists(filepath):
            print(f"[SKIP] File not found: {filepath}\n")
            continue

        print(f"[FILE] {filepath}")
        total_files += 1

        for update in updates_list:
            class_name = update['class_name']
            back_url = update['back_url_default']
            crumbs = update['crumbs']

            ok, msg = add_context_to_view(filepath, class_name, back_url, crumbs)
            status = "[OK]" if ok else "[SKIP]"
            print(f"  {status} {class_name} - {msg}")
            if ok:
                total_updates += 1

        print()

    print(f"[RESULT] Updated {total_updates} view classes across {total_files} files")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
