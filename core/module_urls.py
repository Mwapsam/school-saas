"""
URL to Module Mapping Registry

Maps Django URL names to their corresponding module keys for module-level access control.

This registry is the single source of truth for determining which module a given URL
belongs to. The ModuleAccessMiddleware uses this to enforce module availability at the
server level before the view executes.

Every module-specific URL must be listed here with its corresponding module key.
If a URL is not in this mapping, it is not subject to module-level access control
(default-allow behavior).

Structure: URL name (string) -> module key (string)
Module keys are validated against MODULES keys in core/modules.py
"""

URL_MODULE_MAP = {
    # ───────────────────────────────────────────────────────────────────────────
    # HR Settings & Lookups
    # ───────────────────────────────────────────────────────────────────────────
    "hr_dashboard": "hr",
    "hr_settings": "hr",
    "hr_cashier_settings": "hr",
    "hr_lookup_list": "hr",
    "hr_lookup_create": "hr",
    "hr_lookup_update": "hr",
    "hr_lookup_toggle_status": "hr",
    "hr_lookup_delete": "hr",
    "hr_working_days_update": "hr",
    "hr_cashier_settings_update": "hr",

    # ───────────────────────────────────────────────────────────────────────────
    # HR Employee Management
    # ───────────────────────────────────────────────────────────────────────────
    "employee_detail": "hr",
    "employees_api": "hr",
    "employee_categories_api": "hr",
    "employee_positions_api": "hr",
    "employee_grades_api": "hr",
    "hr_subject_assignments": "hr",
    "employee_subjects_tab": "hr",
    "employee_subjects_update": "hr",
    "employee_roles_tab": "hr",
    "employee_roles_update": "hr",
    "hr_reports": "hr",

    # ───────────────────────────────────────────────────────────────────────────
    # HR Employee Records: Contracts, Documents, Qualifications
    # ───────────────────────────────────────────────────────────────────────────
    "hr_contract_list": "hr",
    "hr_employee_contracts_tab": "hr",
    "hr_contract_create": "hr",
    "hr_contract_renew": "hr",
    "hr_contract_decision": "hr",
    "hr_employee_documents_tab": "hr",
    "hr_document_upload": "hr",
    "hr_document_delete": "hr",
    "hr_employee_qualifications_tab": "hr",
    "hr_qualification_add": "hr",
    "hr_qualification_delete": "hr",
    "hr_employee_history_tab": "hr",

    # ───────────────────────────────────────────────────────────────────────────
    # HR Employee Lifecycle: Onboarding & Exit
    # ───────────────────────────────────────────────────────────────────────────
    "hr_onboarding_list": "hr",
    "hr_employee_onboarding_tab": "hr",
    "hr_onboarding_add_item": "hr",
    "hr_onboarding_toggle_item": "hr",
    "hr_exit_list": "hr",
    "hr_employee_exit_tab": "hr",
    "hr_exit_start": "hr",
    "hr_exit_toggle_item": "hr",
    "hr_exit_update": "hr",
    "hr_exit_complete": "hr",

    # ───────────────────────────────────────────────────────────────────────────
    # HR Employee Lifecycle: Performance & Training
    # ───────────────────────────────────────────────────────────────────────────
    "hr_performance_list": "hr",
    "hr_review_create": "hr",
    "hr_review_save": "hr",
    "hr_review_complete": "hr",
    "hr_performance_detail": "hr",
    "hr_employee_performance_tab": "hr",
    "hr_training_list": "hr",
    "hr_employee_training_tab": "hr",
    "hr_training_add": "hr",
    "hr_training_delete": "hr",

    # ───────────────────────────────────────────────────────────────────────────
    # HR Recruitment
    # ───────────────────────────────────────────────────────────────────────────
    "hr_vacancy_list": "hr",
    "hr_vacancy_create": "hr",
    "hr_vacancy_detail": "hr",
    "hr_vacancy_update": "hr",
    "hr_applicant_create": "hr",
    "hr_applicant_advance": "hr",
    "hr_applicant_convert": "hr",

    # ───────────────────────────────────────────────────────────────────────────
    # HR Employee Relations
    # ───────────────────────────────────────────────────────────────────────────
    "hr_relations": "hr",
    "hr_disciplinary_create": "hr",
    "hr_disciplinary_update": "hr",
    "hr_grievance_create": "hr",
    "hr_grievance_update": "hr",
    "hr_employee_disciplinary_tab": "hr",

    # ───────────────────────────────────────────────────────────────────────────
    # HR Operations: Tasks, Policies, Audit
    # ───────────────────────────────────────────────────────────────────────────
    "hr_task_list": "hr",
    "hr_task_create": "hr",
    "hr_task_update": "hr",
    "hr_policy_list": "hr",
    "hr_policy_create": "hr",
    "hr_policy_update": "hr",
    "hr_policy_delete": "hr",
    "hr_policy_acks": "hr",
    "hr_audit_list": "hr",

    # ───────────────────────────────────────────────────────────────────────────
    # HR Employee Leave & Attendance
    # ───────────────────────────────────────────────────────────────────────────
    "hr_leave_list": "hr",
    "hr_attendance_register": "hr",
    "hr_attendance_records": "hr",
    "hr_attendance_report": "hr",
    "hr_attendance_report_pdf": "hr",
    "hr_leave_balances": "hr",
    "hr_leave_balance_report": "hr",
    "hr_leave_balance_report_pdf": "hr",
    "hr_leave_create": "hr",
    "hr_leave_approve": "hr",
    "hr_leave_reject": "hr",
    "hr_attendance_mark": "hr",

    # ───────────────────────────────────────────────────────────────────────────
    # HR Payroll & Payslips
    # ───────────────────────────────────────────────────────────────────────────
    "hr_payroll_settings": "hr",
    "hr_payroll_group_detail": "hr",
    "hr_payslip_generate": "hr",
    "hr_payslip_list": "hr",
    "hr_payslip_settings": "hr",
    "hr_payslip_report": "hr",
    "hr_payroll_runs": "hr",
    "hr_payroll_lookup_list": "hr",
    "hr_payroll_lookup_create": "hr",
    "hr_payroll_lookup_update": "hr",
    "hr_payroll_lookup_toggle_status": "hr",
    "hr_payroll_lookup_delete": "hr",
    "hr_payroll_group_component_add": "hr",
    "hr_payroll_group_component_remove": "hr",
    "employee_payroll_tab": "hr",
    "employee_payroll_update": "hr",
    "hr_payslip_generate_single": "hr",
    "hr_payslip_generate_group": "hr",
    "hr_payslip_approve": "hr",
    "hr_payslip_reject": "hr",
    "hr_payslip_regenerate": "hr",
    "hr_payslip_mark_paid": "hr",
    "hr_payslip_unmark_paid": "hr",
    "hr_payslip_pdf": "hr",
    "hr_payslip_settings_update": "hr",
    "hr_payslip_report_template_save": "hr",
    "hr_payslip_report_template_run": "hr",

    # ───────────────────────────────────────────────────────────────────────────
    # Admission Management
    # ───────────────────────────────────────────────────────────────────────────
    "admission_apply": "admissions",
    "admission_success": "admissions",
    "admission_list": "admissions",
    "admission_list_api": "admissions",
    "admission_detail": "admissions",
    "admission_review": "admissions",
    "admission_dashboard": "admissions",
    "admission_report": "admissions",
    "admission_manage": "admissions",
    "admission_delete": "admissions",
    "admission_admit": "admissions",
    "admission_assign_batch": "admissions",
    "admission_approve": "admissions",
    "admission_reject": "admissions",
    "admission_duplicate": "admissions",
    "admission_export_pdf": "admissions",
    "admission_diagnostics": "admissions",
    "admission_data_status_ajax": "admissions",

    # ───────────────────────────────────────────────────────────────────────────
    # Enquiry Management
    # ───────────────────────────────────────────────────────────────────────────
    "enquiry_list": "admissions",
    "enquiry_create": "admissions",
    "enquiry_detail": "admissions",
    "enquiry_update": "admissions",
    "enquiry_delete": "admissions",
    "enquiry_add_follow_up": "admissions",
    "enquiry_add_stage_note": "admissions",
    "enquiry_export": "admissions",
    "enquiry_bulk_action": "admissions",

    # ───────────────────────────────────────────────────────────────────────────
    # Batch Assignment
    # ───────────────────────────────────────────────────────────────────────────
    "batch_assignment_list": "admissions",
    "batch_assignment": "admissions",
    "batch_assignment_detail": "admissions",

    # ───────────────────────────────────────────────────────────────────────────
    # Finance Dashboard & Collections
    # ───────────────────────────────────────────────────────────────────────────
    "finance_dashboard": "finance",
    "fee_collections": "finance",
    "fee_collection_create": "finance",
    "fee_collection_detail": "finance",
    "fee_collection_delete": "finance",
    "fee_collection_bulk_publish": "finance",
    "fee_collection_batches": "finance",
    "fee_collection_particulars": "finance",
    "fee_collection_add_particular": "finance",
    "fee_collection_bulk_add_particular": "finance",
    "fee_collection_remove_particular": "finance",
    "fee_collection_bulk_delete": "finance",
    "fee_collection_bulk_delete_json": "finance",
    "fee_collection_bulk_edit": "finance",

    # ───────────────────────────────────────────────────────────────────────────
    # Finance Workflow & Fee Management
    # ───────────────────────────────────────────────────────────────────────────
    "fee_structure": "finance",
    "collect_fees": "finance",
    "finance_track": "finance",
    "family_accounts": "finance",
    "finance_settings": "finance",
    "finance_reports": "finance",
    "finance_fee_receipts": "finance",
    "finance_fee_receipt_pdf": "finance",
    "family_invoice_pdf": "finance",
    "particular_wise_student_transaction_report": "finance",
    "finance_day_book": "finance",

    # ───────────────────────────────────────────────────────────────────────────
    # Finance QuickBooks Integration
    # ───────────────────────────────────────────────────────────────────────────
    "quickbooks_settings": "finance",
    "quickbooks_config_update": "finance",
    "quickbooks_items": "finance",
    "quickbooks_status": "finance",
    "quickbooks_connect": "finance",
    "quickbooks_callback": "finance",
    "quickbooks_disconnect": "finance",
    "quickbooks_test": "finance",
    "quickbooks_webhook_review": "finance",
    "quickbooks_reconciliation": "finance",
    "quickbooks_fee_payment": "finance",
    "quickbooks_student_sync": "finance",
    "quickbooks_bulk_student_sync": "finance",
    "quickbooks_receipt_reconciliation": "finance",

    # ───────────────────────────────────────────────────────────────────────────
    # Finance Currency Configuration
    # ───────────────────────────────────────────────────────────────────────────
    "currency_configuration": "finance",
    "currency_configuration_update": "finance",
    "currency_preview": "finance",

    # ───────────────────────────────────────────────────────────────────────────
    # Finance Fee Management
    # ───────────────────────────────────────────────────────────────────────────
    "fee_dashboard": "finance",
    "fee_categories": "finance",
    "fee_category_create": "finance",
    "fee_batch_assignment": "finance",
    "fee_batch_assignment_create": "finance",
    "fee_batch_assignment_delete": "finance",
    "fee_batch_assignment_bulk_delete": "finance",
    "fee_batch_assignment_students": "finance",
    "fee_student_management": "finance",
    "fee_student_payment": "finance",
    "fee_add_student_particular": "finance",
    "fee_remove_student_charge": "finance",
    "fee_add_student_discount": "finance",
    "fee_add_student_fine": "finance",
    "fee_batch_report": "finance",
    "fee_reports": "finance",
    "fee_student_statement": "finance",
    "fee_student_statement_pdf": "finance",
    "fee_collection_payment_receipt_pdf": "finance",
    "statement_distribution_data": "finance",
    "statement_distribute_send": "finance",
    "fee_payment_reversal": "finance",
    "fee_grant_waiver": "finance",
    "fee_defaulters_report": "finance",
    "fee_defaulters_report_pdf": "finance",
    "fee_year_reports": "finance",
    "fee_statistics_report": "finance",

    # ───────────────────────────────────────────────────────────────────────────
    # Finance Payment Agreements
    # ───────────────────────────────────────────────────────────────────────────
    "payment_agreement_list": "finance",
    "payment_agreement_create": "finance",
    "payment_agreement_bulk_create": "finance",
    "payment_agreement_detail": "finance",
    "payment_agreement_pdf": "finance",

    # ───────────────────────────────────────────────────────────────────────────
    # Finance Advanced Fee Management (Masters)
    # ───────────────────────────────────────────────────────────────────────────
    "fee_masters": "finance",
    "fee_master_particular_save": "finance",
    "fee_master_particular_delete": "finance",
    "fee_master_particular_usage": "finance",
    "fee_master_discount_save": "finance",
    "fee_master_discount_delete": "finance",
    "fee_master_discount_usage": "finance",
    "fee_applicability_rule_save": "finance",
    "fee_applicability_rule_delete": "finance",
    "fee_particulars": "finance",
    "fee_particulars_create": "finance",
    "fee_discounts": "finance",
    "fee_discounts_create": "finance",
    "fee_discounts_view": "finance",
    "fee_waivers": "finance",
    "fee_waivers_create": "finance",
    "fee_waivers_revoke": "finance",
    "fine_slabs": "finance",
    "fine_slabs_create": "finance",

    # ───────────────────────────────────────────────────────────────────────────
    # Transport Management
    # ───────────────────────────────────────────────────────────────────────────
    "transport": "transport",
    "transport_dashboard": "transport",
    "transport_settings": "transport",
    "transport_settings_update": "transport",
    "transport_stops": "transport",
    "transport_vehicles": "transport",
    "transport_staff": "transport",
    "transport_routes": "transport",
    "transport_assignments": "transport",
    "transport_stop_list": "transport",
    "transport_vehicle_list": "transport",
    "transport_staff_list": "transport",
    "transport_route_list": "transport",
    "transport_assignment_list": "transport",
    "transport_route_stop_options": "transport",
    "transport_student_search": "transport",
    "transport_write": "transport",
    "transport_write_pk": "transport",

    # ───────────────────────────────────────────────────────────────────────────
    # Library Management
    # ───────────────────────────────────────────────────────────────────────────
    "library": "library",
    "library_scan": "library",

    # ───────────────────────────────────────────────────────────────────────────
    # Hostel Management
    # ───────────────────────────────────────────────────────────────────────────
    "hostel": "hostel",
}


def validate_module_urls():
    """
    Validate that all modules in URL_MODULE_MAP are valid module keys.

    Raises ValueError if any invalid module keys are found.
    Used by Django system checks and tests to ensure consistency.
    """
    from core.modules import MODULES

    invalid_modules = set(URL_MODULE_MAP.values()) - set(MODULES.keys())
    if invalid_modules:
        raise ValueError(
            f"Invalid module keys in URL_MODULE_MAP: {invalid_modules}. "
            f"Valid modules are: {list(MODULES.keys())}"
        )


def check_duplicate_mappings():
    """
    Check for duplicate URL name to module mappings (shouldn't happen, but guard against it).

    Raises ValueError if the same URL name is mapped to different modules.
    """
    from collections import defaultdict

    duplicates = defaultdict(list)
    for url_name, module in URL_MODULE_MAP.items():
        duplicates[url_name].append(module)

    conflicts = {k: v for k, v in duplicates.items() if len(v) > 1}
    if conflicts:
        raise ValueError(f"Duplicate URL mappings found: {conflicts}")


def find_unmapped_module_urls():
    """
    Find all URL names that belong to a module but have no entry in URL_MODULE_MAP.

    Walks the URLconf to collect all named URL patterns and checks whether they
    belong to a module-specific namespace/app (hr, finance, admissions, etc.) but
    are missing from the module-to-URL mapping. This detects drift when new URLs
    are added to a module's views without updating URL_MODULE_MAP.

    Returns:
        set: URL names that are unmapped module URLs.
    """
    from django.urls import get_resolver

    # Module-owning app prefixes in core/urls.py (derived from the groupings in URL_MODULE_MAP comments).
    # These are the core.urls.py URL path prefixes where module-specific routes are registered.
    module_app_prefixes = {
        "hr_dashboard": "hr",
        "admission": "admissions",
        "enquiry": "admissions",
        "batch": "admissions",
        "finance": "finance",
        "fee": "finance",
        "transport": "transport",
        "library": "library",
        "hostel": "hostel",
    }

    resolver = get_resolver()
    unmapped = set()

    def walk_patterns(patterns, prefix=""):
        for pattern in patterns:
            if hasattr(pattern, "url_patterns"):
                # Include/namespace pattern; recurse.
                walk_patterns(pattern.url_patterns, prefix + str(pattern.pattern))
            else:
                # Leaf pattern; check if it's a module URL.
                url_name = pattern.name
                if url_name:
                    # Check if this url_name looks like it belongs to a module
                    # by matching known module URL prefixes.
                    for prefix_key, module_key in module_app_prefixes.items():
                        if url_name.startswith(prefix_key.split("_")[0]):
                            # This url_name probably belongs to a module. Check if mapped.
                            if url_name not in URL_MODULE_MAP:
                                unmapped.add(url_name)
                            break

    walk_patterns(resolver.url_patterns)
    return unmapped
