from django.urls import path, include
from django.views.generic import RedirectView

from core.view_modules.library_hostel_transport_views import LibraryScanView
from . import views
from .view_modules import fee_management_views as fee_views
from .view_modules import fee_reporting_views as fee_report_views
from .view_modules import file_views
from .view_modules import fee_collection_views
from .view_modules import hr_settings_views
from .view_modules import transport_views
from .view_modules import hr_leave_views
from .view_modules import hr_payroll_views
from .view_modules import hr_record_views
from .view_modules import hr_lifecycle_views
from .view_modules import hr_recruitment_views
from .view_modules import hr_relations_views
from .view_modules import hr_ops_views
from .view_modules import role_views
from .view_modules import employee_role_views
from .view_modules import configuration_views as config_views

app_name = 'core'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Settings/Configuration
    path('configuration/', views.ConfigurationView.as_view(), name='configuration'),
    path('configuration/school_settings/', views.SchoolSettingsView.as_view(), name='school_settings'),
    path('configuration/general/', config_views.GeneralSettingsView.as_view(), name='general_settings'),
    path('configuration/student-categories/', config_views.StudentCategoryView.as_view(), name='student_category_config'),
    path('configuration/document-categories/', config_views.DocumentCategoryView.as_view(), name='document_category_config'),
    path('configuration/feature-access/', config_views.FeatureAccessView.as_view(), name='feature_access_config'),
    path('configuration/notification-control/', config_views.NotificationControlView.as_view(), name='notification_control_config'),
    path('configuration/admission-details/', config_views.AdmissionDetailsView.as_view(), name='admission_details_config'),
    path('configuration/exempted-students/', config_views.ExemptedStudentsView.as_view(), name='exempted_students_config'),
    path('configuration/students-sorting/', config_views.StudentsSortingView.as_view(), name='students_sorting_config'),
    path('configuration/custom-words/', config_views.CustomWordsView.as_view(), name='custom_words_config'),
    path('configuration/manage-clients/', config_views.ManageClientsView.as_view(), name='manage_clients_config'),
    path('programs/', views.ProgramsView.as_view(), name='programs'),
    path('settings/manage-class-batch/', views.ManageClassBatchView.as_view(), name='manage_class_batch'),
    path('settings/enrollment-conflicts/', views.EnrollmentConflictsView.as_view(), name='enrollment_conflicts'),
    path('api/enrollment-conflicts/resolve/', views.resolve_enrollment_conflict_api, name='resolve_enrollment_conflict_api'),

    # Batch Transfer
    path('batch-transfers/', views.BatchTransferListView.as_view(), name='batch_transfer_list'),
    path('batch-transfers/<uuid:batch_id>/', views.BatchTransferDetailView.as_view(), name='batch_transfer_detail'),
    
    # Student management
    path('students/', views.StudentListView.as_view(), name='student_list'),
    path('students/api/', views.StudentListAPIView.as_view(), name='student_list_api'),
    path('students/<uuid:pk>/', views.StudentDetailView.as_view(), name='student_detail'),
    path('students/<uuid:student_id>/documents/', views.StudentDocumentsView.as_view(), name='student_documents'),
    path('students/<uuid:pk>/edit/', views.StudentEditView.as_view(), name='student_edit'),
    path('students/<uuid:student_id>/guardians/attach/', views.AttachGuardianView.as_view(), name='student_attach_guardian'),
    path('students/<uuid:student_id>/guardians/<uuid:guardian_id>/primary-contact/', views.ChangePrimaryContactView.as_view(), name='student_change_primary_contact'),
    path('students/<uuid:student_id>/guardians/<uuid:guardian_id>/delete/', views.DeleteGuardianView.as_view(), name='student_delete_guardian'),

    # Parent/Guardian management
    path('parents/<uuid:pk>/', views.ParentDetailView.as_view(), name='parent_detail'),

    # Academic management
    path('academic/courses/', views.CourseListView.as_view(), name='course_list'),
    path('api/courses/create/', views.course_create_api, name='course_create_api'),
    path('api/courses/<uuid:course_id>/update/', views.course_update_api, name='course_update_api'),
    path('api/batches/<uuid:batch_id>/quick-update/', views.batch_quick_update_api, name='batch_quick_update_api'),
    path('api/batches/<uuid:batch_id>/exam-type-config/', views.batch_exam_type_config_api, name='batch_exam_type_config_api'),
    path('api/batches/<uuid:batch_id>/exam-type-config/update/', views.update_batch_exam_type_config_api, name='update_batch_exam_type_config_api'),
    path('academic/subjects/', views.SubjectListView.as_view(), name='subject_list'),
    path('academic/subjects-center/', views.SubjectsCenterView.as_view(), name='subjects_center'),
    path('academic/subjects-center/class-subjects/', views.ClassSubjectsView.as_view(), name='class_subjects'),
    path('academic/timetables/', views.TimetableListView.as_view(), name='timetable_list'),
    path('academic/attendance/', views.AttendanceListView.as_view(), name='attendance_list'),
    path('academic/years/', views.AcademicYearListView.as_view(), name='academic_year_list'),
    path('batches/', views.BatchListView.as_view(), name='batch_list'),
    path('batches/<uuid:pk>/', views.BatchDetailView.as_view(), name='batch_detail'),
    
    # Exam dashboard
    path('exam/', views.ExamIndexView.as_view(), name='exam_index'),

    # Exam Planner
    path('gradebook/exam-planners/', views.ExamPlannersListView.as_view(), name='exam_planners_list'),
    path('gradebook/exam-planners/<uuid:pk>/', views.ExamPlanDetailView.as_view(), name='exam_plan_detail'),
    path('gradebook/exam-planners/<uuid:pk>/manage-classes/', views.ManageExamPlanClassesView.as_view(), name='manage_exam_plan_classes'),
    path('gradebook/exam-planners/create/', views.CreateExamPlanView.as_view(), name='create_exam_plan'),
    path('gradebook/exam-planners/import/', views.import_exam_planner_api, name='import_exam_planner'),
    path('api/gradebook/create-exam-plan/', views.create_exam_plan_api, name='create_exam_plan_api'),
    path('api/academic/set-active-year/', views.set_active_academic_year_api, name='set_active_academic_year_api'),
    path('api/academic/create-year/', views.create_academic_year_api, name='create_academic_year_api'),
    path('api/academic/years/<uuid:year_id>/', views.get_academic_year_api, name='get_academic_year_api'),
    path('api/academic/years/<uuid:year_id>/update/', views.update_academic_year_api, name='update_academic_year_api'),
    path('api/academic/years/<uuid:year_id>/delete/', views.delete_academic_year_api, name='delete_academic_year_api'),
    path('api/gradebook/exam-plan-subjects/', views.get_exam_plan_subjects_api, name='get_exam_plan_subjects_api'),
    path('api/gradebook/exam-edit-subjects/', views.get_exam_edit_subjects_api, name='get_exam_edit_subjects_api'),
    path('api/gradebook/create-term-exams/', views.create_term_exams_api, name='create_term_exams_api'),
    path('api/gradebook/exam-plan/<uuid:exam_plan_id>/propagate/', views.propagate_exam_plan_api, name='propagate_exam_plan_api'),
    path('api/gradebook/exam-plan/<uuid:exam_plan_id>/delete/', views.delete_exam_plan_api, name='delete_exam_plan_api'),
    path('api/gradebook/term/<uuid:term_id>/delete/', views.delete_term_api, name='delete_term_api'),
    path('api/gradebook/term/<uuid:term_id>/update/', views.update_term_api, name='update_term_api'),
    path('api/gradebook/assign-exam-slot/', views.assign_exam_slot_api, name='assign_exam_slot_api'),
    path('api/gradebook/set-report-format/', views.set_report_format_api, name='set_report_format_api'),
    path('api/gradebook/exam/<uuid:exam_id>/', views.get_exam_details_api, name='get_exam_details_api'),
    path('api/gradebook/exam/<uuid:exam_id>/update/', views.update_exam_api, name='update_exam_api'),
    path('api/gradebook/exam/<uuid:exam_id>/delete/', views.delete_exam_api, name='delete_exam_api'),
    path('api/gradebook/exam/<uuid:exam_id>/undo-submission/', views.undo_marks_submission_api, name='undo_marks_submission_api'),
    path('api/gradebook/exam-type/delete/', views.delete_exam_type_api, name='delete_exam_type_api'),
    path('api/gradebook/exam-type/edit-subjects/', views.edit_exam_subjects_api, name='edit_exam_subjects_api'),
    path('api/gradebook/exam-plan/<uuid:exam_plan_id>/include-class/', views.include_exam_plan_class_api, name='include_exam_plan_class_api'),
    path('api/gradebook/exam-plan/<uuid:exam_plan_id>/exclude-class/', views.exclude_exam_plan_class_api, name='exclude_exam_plan_class_api'),
    path('academic/publish-exam-group/<uuid:exam_group_id>/', views.publish_exam_group_api, name='publish_exam_group_api'),
    
    # Attendance Management
    path('academic/attendance-management/', views.AttendanceManagementView.as_view(), name='attendance_management'),
    path('academic/attendance-reports/', views.AttendanceReportsView.as_view(), name='attendance_reports'),
    path('academic/mark-attendance/', views.mark_attendance_api, name='mark_attendance_api'),
    path('academic/batch-students-attendance/<uuid:batch_id>/', views.batch_students_attendance_api, name='batch_students_attendance_api'),
    path('academic/batch-monthly-attendance/<uuid:batch_id>/', views.batch_monthly_attendance_api, name='batch_monthly_attendance_api'),
    path('academic/attendance-summary/', views.attendance_summary_api, name='attendance_summary_api'),
    path('academic/export-attendance-report/', views.export_attendance_report_api, name='export_attendance_report_api'),
    
    # Teacher management
    path('teachers/', views.TeacherListView.as_view(), name='teacher_list'),

    # HR Settings
    path('hr/', hr_settings_views.HRDashboardView.as_view(), name='hr_dashboard'),
    path('hr/settings/', hr_settings_views.HRSettingsLandingView.as_view(), name='hr_settings'),
    path('hr/settings/cashier/', hr_settings_views.CashierSettingsView.as_view(), name='hr_cashier_settings'),
    path('hr/settings/<str:lookup_key>/', hr_settings_views.HRLookupListView.as_view(), name='hr_lookup_list'),

    # Admission management (legacy)
    path('admission/', views.AdmissionApplicationView.as_view(), name='admission_apply'),
    path('admission/success/<str:app_number>/', views.AdmissionSuccessView.as_view(), name='admission_success'),
    path('admission/list/', views.AdmissionListView.as_view(), name='admission_list'),
    path('admission/list/api/', views.AdmissionListAPIView.as_view(), name='admission_list_api'),
    path('admission/<uuid:pk>/', views.AdmissionDetailView.as_view(), name='admission_detail'),
    path('admission/review/<uuid:pk>/', views.AdmissionReviewView.as_view(), name='admission_review'),
    
    # Admission Dashboard
    path('admission/dashboard/', views.AdmissionDashboardView.as_view(), name='admission_dashboard'),

    # Attendance Dashboard
    path('attendance/dashboard/', views.AttendanceDashboardView.as_view(), name='attendance_dashboard'),
    path('attendance/register/', views.AttendanceRegisterView.as_view(), name='attendance_register'),
    path('attendance/reports/', views.AttendanceReportView.as_view(), name='attendance_reports'),
    path('attendance/reports/daywise/', views.AttendanceDaywiseReportView.as_view(), name='attendance_daywise_report'),
    path('attendance/settings/', views.AttendanceSettingsView.as_view(), name='attendance_settings'),
    path('attendance_labels/<uuid:label_id>/edit/', views.AttendanceLabelEditView.as_view(), name='attendance_label_edit'),
    path('school-calendar/', views.SchoolCalendarView.as_view(), name='school_calendar'),

    # Parents Portal (public — no login required)
    path('portal/', views.PortalLandingView.as_view(), name='portal_landing'),
    path('portal/apply/', views.PortalAdmissionRegistrationView.as_view(), name='portal_admission_register'),
    path('portal/apply/success/<str:app_number>/', views.PortalAdmissionSuccessView.as_view(), name='portal_admission_success'),
    path('portal/status/', views.PortalStatusCheckView.as_view(), name='portal_status_check'),

    # Extended Admission Registration System
    path('register/', views.AdmissionRegistrationView.as_view(), name='admission_register'),
    path('register/submit/', views.AdmissionRegistrationSubmitView.as_view(), name='admission_register_submit'),
    path('register/success/<str:app_number>/', views.ExtendedAdmissionSuccessView.as_view(), name='admission_register_success'),
    path('register/navigate/', views.AdmissionStepNavigationView.as_view(), name='admission_step_navigate'),
    path('status/', views.AdmissionStatusCheckView.as_view(), name='admission_status_check'),
    path('manage/', views.AdmissionManagementListView.as_view(), name='admission_manage'),
    path('management/<uuid:pk>/delete/', views.admission_delete_api, name='admission_delete'),
    path('management/<uuid:pk>/admit/', views.admission_admit_api, name='admission_admit'),
    path('management/<uuid:pk>/assign-batch/', views.admission_assign_batch_api, name='admission_assign_batch'),
    path('management/<uuid:pk>/approve/', views.admission_approve_api, name='admission_approve'),
    path('management/<uuid:pk>/reject/', views.admission_reject_api, name='admission_reject'),
    path('management/<uuid:pk>/duplicate/', views.admission_duplicate_api, name='admission_duplicate'),
    path('management/<uuid:pk>/export-pdf/', views.admission_export_pdf, name='admission_export_pdf'),
    
    # Admission Diagnostics
    path('diagnostics/', views.AdmissionDiagnosticsView.as_view(), name='admission_diagnostics'),

    # Admission Report
    path('admission/report/', views.AdmissionReportView.as_view(), name='admission_report'),

    # Enquiry Management
    path('enquiry/', views.ApplicantEnquiryListView.as_view(), name='enquiry_list'),
    path('enquiry/create/', views.ApplicantEnquiryCreateView.as_view(), name='enquiry_create'),
    path('enquiry/<uuid:pk>/', views.ApplicantEnquiryDetailView.as_view(), name='enquiry_detail'),
    path('enquiry/<uuid:pk>/update/', views.ApplicantEnquiryUpdateView.as_view(), name='enquiry_update'),
    path('enquiry/<uuid:pk>/delete/', views.ApplicantEnquiryDeleteView.as_view(), name='enquiry_delete'),
    path('enquiry/<uuid:enquiry_id>/follow-up/add/', views.add_follow_up, name='enquiry_add_follow_up'),
    path('enquiry/stage-log/<uuid:stage_log_id>/note/add/', views.add_stage_note, name='enquiry_add_stage_note'),
    path('enquiry/export/', views.export_enquiries, name='enquiry_export'),
    path('enquiry/bulk-action/', views.enquiry_bulk_action, name='enquiry_bulk_action'),
    
    # Batch Assignment
    path('batch-assignment/', views.BatchAssignmentListView.as_view(), name='batch_assignment_list'),
    path('batch-assignment/assign/', views.BatchAssignmentView.as_view(), name='batch_assignment'),
    path('batch-assignment/<uuid:application_id>/', views.BatchAssignmentDetailView.as_view(), name='batch_assignment_detail'),
    
    # Finance Dashboard
    path('finance/', views.FinanceDashboardView.as_view(), name='finance_dashboard'),

    # Finance workflow — Step 2: Collections
    path('finance/collections/', fee_collection_views.FeeCollectionListView.as_view(), name='fee_collections'),
    path('finance/collections/create/', fee_collection_views.FeeCollectionCreateView.as_view(), name='fee_collection_create'),
    path('finance/collections/<uuid:pk>/', fee_collection_views.FeeCollectionDetailView.as_view(), name='fee_collection_detail'),
    path('finance/collections/<uuid:pk>/delete/', fee_collection_views.FeeCollectionDeleteView.as_view(), name='fee_collection_delete'),
    path('finance/collections/publish/', fee_collection_views.FeeCollectionBulkPublishView.as_view(), name='fee_collection_bulk_publish'),
    path('api/finance/collections/batches/', fee_collection_views.FeeCollectionBatchesView.as_view(), name='fee_collection_batches'),
    path('api/finance/collections/particulars/', fee_collection_views.FeeCollectionParticularsView.as_view(), name='fee_collection_particulars'),
    path('finance/collections/<uuid:pk>/particulars/add/', fee_collection_views.FeeCollectionAddParticularView.as_view(), name='fee_collection_add_particular'),
    path('finance/collections/particulars/bulk-add/', fee_collection_views.FeeCollectionBulkAddParticularView.as_view(), name='fee_collection_bulk_add_particular'),
    path('finance/collections/<uuid:pk>/particulars/remove/', fee_collection_views.FeeCollectionRemoveParticularView.as_view(), name='fee_collection_remove_particular'),
    path('finance/collections/bulk-delete/', fee_collection_views.FeeCollectionBulkDeleteView.as_view(), name='fee_collection_bulk_delete'),
    path('finance/collections/bulk-delete-json/', fee_collection_views.FeeCollectionBulkDeleteJSONView.as_view(), name='fee_collection_bulk_delete_json'),
    path('finance/collections/bulk-edit/', fee_collection_views.FeeCollectionBulkEditView.as_view(), name='fee_collection_bulk_edit'),

    # Finance workflow — temporary redirects for steps not yet built (Tasks 4-6)
    path('finance/fee-structure/', views.FeeStructureView.as_view(), name='fee_structure'),
    path('finance/collect/', fee_views.StudentFeeManagementView.as_view(), name='collect_fees'),
    path('finance/track/', fee_report_views.FinanceTrackView.as_view(), name='finance_track'),
    path('finance/families/', fee_report_views.FamilyAccountView.as_view(), name='family_accounts'),

    path('finance/settings/', views.FinanceSettingsView.as_view(), name='finance_settings'),
    path('finance/reports/', views.FinanceReportsView.as_view(), name='finance_reports'),
    path('finance/fee-receipts/', views.FeeReceiptsView.as_view(), name='finance_fee_receipts'),
    path('finance/fee-receipts/<uuid:transaction_id>/pdf/', views.FeeReceiptPDFView.as_view(), name='finance_fee_receipt_pdf'),
    path('finance/family-invoices/<uuid:invoice_id>/pdf/', views.InvoicePDFView.as_view(), name='family_invoice_pdf'),
    path('finance/particular-wise-student-transaction-report/', views.ParticularWiseStudentTransactionReportView.as_view(), name='particular_wise_student_transaction_report'),
    path('finance/day-book/', views.DayBookReportView.as_view(), name='finance_day_book'),

    # QuickBooks Integration
    path('finance/quickbooks/', views.QuickBooksSettingsView.as_view(), name='quickbooks_settings'),
    path('finance/quickbooks/config/', views.QuickBooksConfigUpdateView.as_view(), name='quickbooks_config_update'),
    path('finance/quickbooks/items/', views.QuickBooksItemsView.as_view(), name='quickbooks_items'),
    path('finance/quickbooks/status/', views.QuickBooksStatusView.as_view(), name='quickbooks_status'),
    path('finance/quickbooks/connect/', views.QuickBooksConnectView.as_view(), name='quickbooks_connect'),
    path('finance/quickbooks/callback/', views.QuickBooksCallbackView.as_view(), name='quickbooks_callback'),
    path('finance/quickbooks/disconnect/', views.QuickBooksDisconnectView.as_view(), name='quickbooks_disconnect'),
    path('finance/quickbooks/test/', views.QuickBooksTestConnectionView.as_view(), name='quickbooks_test'),
    path('finance/quickbooks/webhook-review/', views.QuickBooksWebhookReviewView.as_view(), name='quickbooks_webhook_review'),
    
    # Currency Configuration
    path('finance/currency-configuration/', views.CurrencyConfigurationView.as_view(), name='currency_configuration'),
    path('finance/currency-configuration/update/', views.CurrencyConfigurationUpdateView.as_view(), name='currency_configuration_update'),
    path('finance/currency-configuration/preview/', views.CurrencyPreviewView.as_view(), name='currency_preview'),
    
    # Fee Management
    path('fees/', RedirectView.as_view(pattern_name='core:finance_dashboard', permanent=False), name='fee_dashboard'),
    path('fees/quickbooks-reconciliation/', views.QuickBooksReconciliationView.as_view(), name='quickbooks_reconciliation'),
    path('fees/categories/', fee_views.FeeCategoryListView.as_view(), name='fee_categories'),
    path('fees/categories/create/', fee_views.FeeCategoryCreateView.as_view(), name='fee_category_create'),
    path('fees/batch-assignment/', views.BatchFeeAssignmentView.as_view(), name='fee_batch_assignment'),
    path('fees/batch-assignment/create/', views.BatchFeeAssignmentCreateView.as_view(), name='fee_batch_assignment_create'),
    path('fees/batch-assignment/<uuid:pk>/delete/', views.BatchFeeAssignmentDeleteView.as_view(), name='fee_batch_assignment_delete'),
    path('fees/batch-assignment/bulk-delete/', fee_views.BatchFeeAssignmentBulkDeleteView.as_view(), name='fee_batch_assignment_bulk_delete'),
    path('api/fees/batch-assignment/students/', fee_views.BatchFeeAssignmentStudentsView.as_view(), name='fee_batch_assignment_students'),
    path('fees/student-management/', RedirectView.as_view(pattern_name='core:collect_fees', permanent=False, query_string=True), name='fee_student_management'),
    path('fees/student-payment/', views.StudentFeePaymentView.as_view(), name='fee_student_payment'),
    path('fees/student/add-particular/', fee_views.AddStudentParticularView.as_view(), name='fee_add_student_particular'),
    path('fees/student/remove-charge/', fee_views.RemoveStudentChargeView.as_view(), name='fee_remove_student_charge'),
    path('fees/student/add-discount/', fee_views.AddStudentDiscountView.as_view(), name='fee_add_student_discount'),
    path('fees/student/add-fine/', fee_views.AddStudentFineView.as_view(), name='fee_add_student_fine'),
    path('fees/batch-report/', views.BatchFeeReportView.as_view(), name='fee_batch_report'),
    path('fees/reports/', views.FeeReportsView.as_view(), name='fee_reports'),

    # Phase 3 — expose new finance capabilities in the staff UI
    path('fees/student-statement/', fee_report_views.StudentStatementView.as_view(), name='fee_student_statement'),
    path('fees/student-statement/pdf/', fee_report_views.StudentCollectionReceiptPDFView.as_view(), name='fee_student_statement_pdf'),
    path('fees/collection-receipt/payment/', fee_report_views.CollectFeePaymentReceiptPDFView.as_view(), name='fee_collection_payment_receipt_pdf'),
    path('fees/statement-distribution-data/', fee_report_views.StatementDistributionView.as_view(), name='statement_distribution_data'),
    path('fees/statement-distribute-send/', fee_report_views.StatementDistributeSendView.as_view(), name='statement_distribute_send'),
    path('fees/payment-reversal/', fee_report_views.PaymentReversalView.as_view(), name='fee_payment_reversal'),
    path('fees/grant-waiver/', fee_report_views.GrantWaiverView.as_view(), name='fee_grant_waiver'),
    path('fees/reports/defaulters/', fee_report_views.DefaultersReportView.as_view(), name='fee_defaulters_report'),
    path('fees/reports/defaulters/pdf/', fee_report_views.DefaultersReportPDFView.as_view(), name='fee_defaulters_report_pdf'),
    path('fees/reports/year/', fee_report_views.FeeYearReportsView.as_view(), name='fee_year_reports'),
    path('fees/reports/statistics/', fee_report_views.FeeStatisticsReportView.as_view(), name='fee_statistics_report'),

    # Payment Agreements
    path('fees/agreements/', fee_report_views.PaymentAgreementListView.as_view(), name='payment_agreement_list'),
    path('fees/agreements/new/', fee_report_views.PaymentAgreementCreateView.as_view(), name='payment_agreement_create'),
    path('fees/agreements/bulk-create/', fee_report_views.PaymentAgreementBulkCreateView.as_view(), name='payment_agreement_bulk_create'),
    path('fees/agreements/<uuid:pk>/detail/', fee_report_views.PaymentAgreementDetailView.as_view(), name='payment_agreement_detail'),
    path('fees/agreements/<uuid:pk>/pdf/', fee_report_views.PaymentAgreementPDFView.as_view(), name='payment_agreement_pdf'),

    # Advanced Fee Management
    path('fees/masters/', fee_views.FeeMastersView.as_view(), name='fee_masters'),
    path('fees/masters/particular/save/', fee_views.FeeMasterParticularSaveView.as_view(), name='fee_master_particular_save'),
    path('fees/masters/particular/<uuid:pk>/delete/', fee_views.FeeMasterParticularDeleteView.as_view(), name='fee_master_particular_delete'),
    path('fees/masters/particular/<uuid:pk>/usage/', fee_views.FeeMasterParticularUsageView.as_view(), name='fee_master_particular_usage'),
    path('fees/masters/discount/save/', fee_views.FeeMasterDiscountSaveView.as_view(), name='fee_master_discount_save'),
    path('fees/masters/discount/<uuid:pk>/delete/', fee_views.FeeMasterDiscountDeleteView.as_view(), name='fee_master_discount_delete'),
    path('fees/masters/discount/<uuid:pk>/usage/', fee_views.FeeMasterDiscountUsageView.as_view(), name='fee_master_discount_usage'),
    path('fees/masters/rule/save/', fee_views.FeeApplicabilityRuleSaveView.as_view(), name='fee_applicability_rule_save'),
    path('fees/masters/rule/<uuid:pk>/delete/', fee_views.FeeApplicabilityRuleDeleteView.as_view(), name='fee_applicability_rule_delete'),
    path('fees/particulars/', views.FeeParticularsView.as_view(), name='fee_particulars'),
    path('fees/particulars/create/', views.FeeParticularsCreateView.as_view(), name='fee_particulars_create'),
    path('fees/discounts/', views.FeeDiscountsView.as_view(), name='fee_discounts'),
    path('fees/discounts/create/', views.FeeDiscountsCreateView.as_view(), name='fee_discounts_create'),
    path('fees/discounts/view/', views.FeeDiscountsView.as_view(), name='fee_discounts_view'),
    path('fees/waivers/', views.FeeWaiversListView.as_view(), name='fee_waivers'),
    path('fees/waivers/create/', fee_report_views.GrantWaiverView.as_view(), name='fee_waivers_create'),
    path('fees/waivers/revoke/', views.FeeWaiverRevokeView.as_view(), name='fee_waivers_revoke'),
    path('fees/fine-slabs/', views.FineSlabsView.as_view(), name='fine_slabs'),
    path('fees/fine-slabs/create/', views.FineSlabsCreateView.as_view(), name='fine_slabs_create'),
    
    # API endpoints for HTMX/AJAX
    path('api/students/search/', views.student_search_api, name='student_search_api'),
    path('api/students/bulk-action/', views.student_bulk_action, name='student_bulk_action'),
    path('api/students/fee-search/', views.student_fee_search_api, name='student_fee_search_api'),
    path('api/students/<uuid:student_id>/reports/academic/', views.student_academic_report_api, name='student_academic_report_api'),
    path('api/students/<uuid:student_id>/reports/attendance/', views.student_attendance_report_api, name='student_attendance_report_api'),
    path('api/students/<uuid:student_id>/reports/fees/', views.student_fee_report_api, name='student_fee_report_api'),
    path('api/students/<uuid:student_id>/reports/profile/', views.student_profile_report_api, name='student_profile_report_api'),
    path('api/students/<uuid:student_id>/fee/add-particular/', views.add_fee_particular_api, name='add_fee_particular_api'),
    path('api/students/<uuid:student_id>/fee/add-discount/', views.add_fee_discount_api, name='add_fee_discount_api'),
    path('api/students/<uuid:student_id>/fee/add-fine/', views.add_fee_fine_api, name='add_fee_fine_api'),
    path('api/students/available-for-batch/', views.available_students_for_batch_api, name='available_students_for_batch_api'),
    path('api/batches/<uuid:batch_id>/students/fees/', views.batch_students_fees_api, name='batch_students_fees_api'),
    path('api/batches/<uuid:batch_id>/students/for-collection/', fee_views.batch_students_for_collection_api, name='batch_students_for_collection_api'),
    path('api/courses/by-academic-year/', views.courses_by_academic_year_api, name='courses_by_academic_year_api'),
    path('api/batches/by-course/', views.batches_by_course_api, name='batches_by_course_api'),
    path('api/batches/by-class/', views.batches_by_class_api, name='batches_by_class_api'),
    path('api/batches/<uuid:batch_id>/students/', views.batch_students_api, name='batch_students_api'),
    path('api/batches/by-academic-year/', views.batches_by_academic_year_api, name='batches_by_academic_year_api'),
    path('api/batches/<uuid:batch_id>/importable-students/', views.batch_importable_students_api, name='batch_importable_students_api'),
    path('api/batches/<uuid:batch_id>/students/add/', views.add_students_to_batch_api, name='add_students_to_batch_api'),
    path('api/batches/<uuid:batch_id>/students/<uuid:student_id>/remove/', views.remove_student_from_batch_api, name='remove_student_from_batch_api'),
    path('api/batches/<uuid:batch_id>/students/<uuid:student_id>/reassign-teacher/', views.batch_reassign_teacher_api, name='batch_reassign_teacher_api'),
    path('api/batches/<uuid:batch_id>/subjects/add/', views.add_subject_to_batch_api, name='add_subject_to_batch_api'),
    # Batch detail tab partials (HTMX) + subject management
    path('api/batches/<uuid:batch_id>/students/partial/', views.batch_students_partial, name='batch_students_partial'),
    path('api/batches/<uuid:batch_id>/subjects/partial/', views.batch_subjects_partial, name='batch_subjects_partial'),
    path('api/batches/<uuid:batch_id>/subjects/<uuid:subject_id>/edit/', views.batch_subject_update_api, name='batch_subject_update_api'),
    path('api/batches/<uuid:batch_id>/subjects/<uuid:subject_id>/remove/', views.batch_subject_remove_api, name='batch_subject_remove_api'),
    path('api/batches/<uuid:batch_id>/timetable/partial/', views.batch_timetable_partial, name='batch_timetable_partial'),
    path('api/batches/<uuid:batch_id>/build-schedule/', views.build_batch_schedule_api, name='build_batch_schedule_api'),
    path('api/batches/<uuid:batch_id>/generate-timetable/', views.generate_timetable_api, name='generate_timetable_api'),
    path('api/batches/<uuid:batch_id>/class-timings/', views.class_timings_api, name='class_timings_api'),
    path('api/weekdays/', views.weekdays_api, name='weekdays_api'),
    path('api/teachers/', views.teachers_api, name='teachers_api'),
    path('api/batches/<uuid:batch_id>/attendance/partial/', views.batch_attendance_partial, name='batch_attendance_partial'),
    path('api/batches/<uuid:batch_id>/exams/partial/', views.batch_exams_partial, name='batch_exams_partial'),
    path('api/batches/<uuid:batch_id>/class-teachers/', views.batch_class_teachers_api, name='batch_class_teachers_api'),
    path('api/batches/<uuid:batch_id>/class-teachers/assign/', views.batch_assign_teachers_api, name='batch_assign_teachers_api'),
    path('api/finance/summary/', views.finance_summary_api, name='finance_summary_api'),
    path('api/stats/quick/', views.quick_stats_api, name='quick_stats_api'),
    path('api/stats/dashboard/', views.dashboard_stats_api, name='dashboard_stats_api'),
    path('api/health/', views.service_health_api, name='service_health_api'),
    path('api/trends/enrollment/', views.enrollment_trends_api, name='enrollment_trends_api'),
    path('api/admission/status/<str:app_number>/', views.admission_status_api, name='admission_status_api'),
    
    # Academic API endpoints
    path('api/courses/', views.courses_api, name='courses_api'),
    path('api/subjects/', views.subjects_api, name='subjects_api'),
    path('api/subjects-by-class/<uuid:class_id>/', views.subjects_by_class_api, name='subjects_by_class_api'),
    path('api/timetable/', views.timetable_crud_api, name='timetable_api'),
    path('api/timetable/<uuid:timetable_id>/', views.timetable_crud_api, name='timetable_detail_api'),
    path('api/attendance/summary/', views.attendance_summary_api, name='attendance_summary_api'),
    path('api/employees/', views.employees_api, name='employees_api'),
    path('api/academic-years/', views.academic_years_api, name='academic_years_api'),
    path('api/departments/', views.departments_api, name='departments_api'),
    path('api/employee-categories/', views.employee_categories_api, name='employee_categories_api'),
    path('api/employee-positions/', views.employee_positions_api, name='employee_positions_api'),
    path('api/employee-grades/', views.employee_grades_api, name='employee_grades_api'),
    
    # Batch management API endpoints
    path('batches/create/', views.batch_create_api, name='batch_create'),
    path('api/batches/<uuid:batch_id>/', views.batch_detail_api, name='batch_detail_api'),
    path('batches/<uuid:batch_id>/edit/', views.batch_update_api, name='batch_update'),
    path('batches/<uuid:batch_id>/delete/', views.batch_delete_api, name='batch_delete'),
    path('api/batches/toggle-status/', views.toggle_batch_status_api, name='toggle_batch_status'),
    path('api/batches/transfer/', views.batch_transfer_api, name='batch_transfer_api'),
    
    # Teacher management API endpoints
    path('teachers/create/', views.teacher_create_api, name='teacher_create'),
    path('api/teachers/<uuid:teacher_id>/', views.teacher_detail_api, name='teacher_detail_api'),
    path('teachers/<uuid:teacher_id>/edit/', views.teacher_update_api, name='teacher_update'),
    path('teachers/<uuid:teacher_id>/toggle-status/', views.teacher_toggle_status_api, name='teacher_toggle_status'),
    path('teachers/<uuid:teacher_id>/delete/', views.teacher_delete_api, name='teacher_delete'),
    path('employees/<uuid:employee_id>/subjects/', views.employee_subjects_tab, name='employee_subjects_tab'),
    path('employees/<uuid:employee_id>/subjects/update/', views.employee_subjects_update_api, name='employee_subjects_update'),
    path('employees/<uuid:employee_id>/roles/', employee_role_views.employee_roles_tab, name='employee_roles_tab'),
    path('employees/<uuid:employee_id>/roles/update/', employee_role_views.employee_roles_update_api, name='employee_roles_update'),

    # HR Settings API endpoints
    path('hr/settings/<str:lookup_key>/create/', hr_settings_views.hr_lookup_create_api, name='hr_lookup_create'),
    path('hr/settings/<str:lookup_key>/<uuid:pk>/update/', hr_settings_views.hr_lookup_update_api, name='hr_lookup_update'),
    path('hr/settings/<str:lookup_key>/<uuid:pk>/toggle-status/', hr_settings_views.hr_lookup_toggle_status_api, name='hr_lookup_toggle_status'),
    path('hr/settings/<str:lookup_key>/<uuid:pk>/delete/', hr_settings_views.hr_lookup_delete_api, name='hr_lookup_delete'),
    path('hr/settings/working-days/update/', hr_settings_views.working_day_settings_update_api, name='hr_working_days_update'),
    path('hr/settings/cashier/update/', hr_settings_views.cashier_settings_update_api, name='hr_cashier_settings_update'),

    # HR employee profile, subject assignments & reports
    path('employees/<uuid:pk>/', views.EmployeeDetailView.as_view(), name='employee_detail'),
    path('hr/subject-assignments/', views.SubjectAssignmentsView.as_view(), name='hr_subject_assignments'),
    path('hr/reports/', hr_settings_views.HRReportsView.as_view(), name='hr_reports'),

    # HR employee record: contracts, documents, qualifications, history
    path('hr/contracts/', hr_record_views.ContractOrgListView.as_view(), name='hr_contract_list'),
    path('hr/contracts/employee/<uuid:employee_id>/', hr_record_views.employee_contracts_tab, name='hr_employee_contracts_tab'),
    path('hr/contracts/employee/<uuid:employee_id>/create/', hr_record_views.contract_create_api, name='hr_contract_create'),
    path('hr/contracts/<uuid:contract_id>/renew/', hr_record_views.contract_renew_api, name='hr_contract_renew'),
    path('hr/contracts/<uuid:contract_id>/decision/', hr_record_views.contract_decision_api, name='hr_contract_decision'),
    path('hr/employees/<uuid:employee_id>/documents/', hr_record_views.employee_documents_tab, name='hr_employee_documents_tab'),
    path('hr/employees/<uuid:employee_id>/documents/upload/', hr_record_views.document_upload_api, name='hr_document_upload'),
    path('hr/documents/<uuid:document_id>/delete/', hr_record_views.document_delete_api, name='hr_document_delete'),
    path('hr/employees/<uuid:employee_id>/qualifications/', hr_record_views.employee_qualifications_tab, name='hr_employee_qualifications_tab'),
    path('hr/employees/<uuid:employee_id>/qualifications/add/', hr_record_views.qualification_add_api, name='hr_qualification_add'),
    path('hr/qualifications/<uuid:qualification_id>/delete/', hr_record_views.qualification_delete_api, name='hr_qualification_delete'),
    path('hr/employees/<uuid:employee_id>/history/', hr_record_views.employee_history_tab, name='hr_employee_history_tab'),

    # HR lifecycle: onboarding
    path('hr/onboarding/', hr_lifecycle_views.OnboardingListView.as_view(), name='hr_onboarding_list'),
    path('hr/employees/<uuid:employee_id>/onboarding/', hr_lifecycle_views.employee_onboarding_tab, name='hr_employee_onboarding_tab'),
    path('hr/employees/<uuid:employee_id>/onboarding/add-item/', hr_lifecycle_views.onboarding_add_item_api, name='hr_onboarding_add_item'),
    path('hr/onboarding/items/<uuid:item_id>/toggle/', hr_lifecycle_views.onboarding_toggle_item_api, name='hr_onboarding_toggle_item'),

    # HR lifecycle: employee exit
    path('hr/exit/', hr_lifecycle_views.ExitListView.as_view(), name='hr_exit_list'),
    path('hr/employees/<uuid:employee_id>/exit/', hr_lifecycle_views.employee_exit_tab, name='hr_employee_exit_tab'),
    path('hr/employees/<uuid:employee_id>/exit/start/', hr_lifecycle_views.exit_start_api, name='hr_exit_start'),
    path('hr/exit/items/<uuid:item_id>/toggle/', hr_lifecycle_views.exit_toggle_item_api, name='hr_exit_toggle_item'),
    path('hr/exit/<uuid:exit_id>/update/', hr_lifecycle_views.exit_update_api, name='hr_exit_update'),
    path('hr/exit/<uuid:exit_id>/complete/', hr_lifecycle_views.exit_complete_api, name='hr_exit_complete'),

    # HR lifecycle: performance
    path('hr/performance/', hr_lifecycle_views.PerformanceListView.as_view(), name='hr_performance_list'),
    path('hr/performance/create/', hr_lifecycle_views.review_create_api, name='hr_review_create'),
    path('hr/performance/<uuid:review_id>/save/', hr_lifecycle_views.review_save_api, name='hr_review_save'),
    path('hr/performance/<uuid:review_id>/complete/', hr_lifecycle_views.review_complete_api, name='hr_review_complete'),
    path('hr/performance/<uuid:pk>/', hr_lifecycle_views.PerformanceDetailView.as_view(), name='hr_performance_detail'),
    path('hr/employees/<uuid:employee_id>/performance/', hr_lifecycle_views.employee_performance_tab, name='hr_employee_performance_tab'),

    # HR lifecycle: training
    path('hr/training/', hr_lifecycle_views.TrainingListView.as_view(), name='hr_training_list'),
    path('hr/employees/<uuid:employee_id>/training/', hr_lifecycle_views.employee_training_tab, name='hr_employee_training_tab'),
    path('hr/employees/<uuid:employee_id>/training/add/', hr_lifecycle_views.training_create_api, name='hr_training_add'),
    path('hr/training/<uuid:record_id>/delete/', hr_lifecycle_views.training_delete_api, name='hr_training_delete'),

    # HR recruitment
    path('hr/recruitment/', hr_recruitment_views.VacancyListView.as_view(), name='hr_vacancy_list'),
    path('hr/recruitment/vacancies/create/', hr_recruitment_views.vacancy_create_api, name='hr_vacancy_create'),
    path('hr/recruitment/vacancies/<uuid:pk>/', hr_recruitment_views.VacancyDetailView.as_view(), name='hr_vacancy_detail'),
    path('hr/recruitment/vacancies/<uuid:vacancy_id>/update/', hr_recruitment_views.vacancy_update_api, name='hr_vacancy_update'),
    path('hr/recruitment/vacancies/<uuid:vacancy_id>/applicants/', hr_recruitment_views.applicant_create_api, name='hr_applicant_create'),
    path('hr/recruitment/applicants/<uuid:applicant_id>/advance/', hr_recruitment_views.applicant_advance_api, name='hr_applicant_advance'),
    path('hr/recruitment/applicants/<uuid:applicant_id>/convert/', hr_recruitment_views.applicant_convert_api, name='hr_applicant_convert'),

    # HR employee relations (restricted)
    path('hr/relations/', hr_relations_views.RelationsView.as_view(), name='hr_relations'),
    path('hr/relations/disciplinary/create/', hr_relations_views.disciplinary_create_api, name='hr_disciplinary_create'),
    path('hr/relations/disciplinary/<uuid:case_id>/update/', hr_relations_views.disciplinary_update_api, name='hr_disciplinary_update'),
    path('hr/relations/grievances/create/', hr_relations_views.grievance_create_api, name='hr_grievance_create'),
    path('hr/relations/grievances/<uuid:grievance_id>/update/', hr_relations_views.grievance_update_api, name='hr_grievance_update'),
    path('hr/employees/<uuid:employee_id>/disciplinary/', hr_relations_views.employee_disciplinary_tab, name='hr_employee_disciplinary_tab'),

    # HR ops: tasks, policies, audit
    path('hr/tasks/', hr_ops_views.HRTaskListView.as_view(), name='hr_task_list'),
    path('hr/tasks/create/', hr_ops_views.hr_task_create_api, name='hr_task_create'),
    path('hr/tasks/<uuid:task_id>/update/', hr_ops_views.hr_task_update_api, name='hr_task_update'),
    path('hr/policies/', hr_ops_views.PolicyListView.as_view(), name='hr_policy_list'),
    path('hr/policies/create/', hr_ops_views.policy_create_api, name='hr_policy_create'),
    path('hr/policies/<uuid:policy_id>/update/', hr_ops_views.policy_update_api, name='hr_policy_update'),
    path('hr/policies/<uuid:policy_id>/delete/', hr_ops_views.policy_delete_api, name='hr_policy_delete'),
    path('hr/policies/<uuid:pk>/acknowledgements/', hr_ops_views.PolicyAckMatrixView.as_view(), name='hr_policy_acks'),
    path('hr/audit/', hr_ops_views.HRAuditLogView.as_view(), name='hr_audit_list'),

    # Employee leave & attendance
    path('hr/leave/', hr_leave_views.EmployeeLeaveListView.as_view(), name='hr_leave_list'),
    path('hr/attendance/', hr_leave_views.EmployeeAttendanceRegisterView.as_view(), name='hr_attendance_register'),
    path('hr/attendance/records/', hr_leave_views.EmployeeAttendanceRecordsView.as_view(), name='hr_attendance_records'),
    path('hr/attendance/report/', hr_leave_views.DepartmentAttendanceReportView.as_view(), name='hr_attendance_report'),
    path('hr/attendance/report/pdf/', hr_leave_views.DepartmentAttendanceReportPDFView.as_view(), name='hr_attendance_report_pdf'),
    path('hr/leave/balances/', hr_leave_views.LeaveBalancesView.as_view(), name='hr_leave_balances'),
    path('hr/leave/balance-report/', hr_leave_views.LeaveBalanceReportView.as_view(), name='hr_leave_balance_report'),
    path('hr/leave/balance-report/pdf/', hr_leave_views.LeaveBalanceReportPDFView.as_view(), name='hr_leave_balance_report_pdf'),

    # Employee leave & attendance API endpoints
    path('hr/leave/create/', hr_leave_views.leave_request_create_api, name='hr_leave_create'),
    path('hr/leave/<uuid:leave_id>/approve/', hr_leave_views.leave_approve_api, name='hr_leave_approve'),
    path('hr/leave/<uuid:leave_id>/reject/', hr_leave_views.leave_reject_api, name='hr_leave_reject'),
    path('hr/attendance/mark/', hr_leave_views.employee_attendance_mark_api, name='hr_attendance_mark'),

    # Payroll & Payslip management
    path('hr/payroll/settings/', hr_payroll_views.PayrollSettingsLandingView.as_view(), name='hr_payroll_settings'),
    path('hr/payroll/groups/<uuid:pk>/', hr_payroll_views.PayrollGroupDetailView.as_view(), name='hr_payroll_group_detail'),
    path('hr/payroll/payslips/generate/', hr_payroll_views.PayslipGenerateView.as_view(), name='hr_payslip_generate'),
    path('hr/payroll/payslips/', hr_payroll_views.PayslipListView.as_view(), name='hr_payslip_list'),
    path('hr/payroll/payslip-settings/', hr_payroll_views.PayslipSettingsView.as_view(), name='hr_payslip_settings'),
    path('hr/payroll/reports/', hr_payroll_views.PayslipReportView.as_view(), name='hr_payslip_report'),
    path('hr/payroll/runs/', hr_payroll_views.PayrollRunsView.as_view(), name='hr_payroll_runs'),

    # Payroll & Payslip API endpoints
    path('hr/payroll/<str:lookup_key>/', hr_payroll_views.PayrollLookupListView.as_view(), name='hr_payroll_lookup_list'),
    path('hr/payroll/<str:lookup_key>/create/', hr_payroll_views.payroll_lookup_create_api, name='hr_payroll_lookup_create'),
    path('hr/payroll/<str:lookup_key>/<uuid:pk>/update/', hr_payroll_views.payroll_lookup_update_api, name='hr_payroll_lookup_update'),
    path('hr/payroll/<str:lookup_key>/<uuid:pk>/toggle-status/', hr_payroll_views.payroll_lookup_toggle_status_api, name='hr_payroll_lookup_toggle_status'),
    path('hr/payroll/<str:lookup_key>/<uuid:pk>/delete/', hr_payroll_views.payroll_lookup_delete_api, name='hr_payroll_lookup_delete'),
    path('hr/payroll/groups/<uuid:pk>/components/add/', hr_payroll_views.payroll_group_component_add_api, name='hr_payroll_group_component_add'),
    path('hr/payroll/groups/<uuid:pk>/components/<uuid:component_id>/remove/', hr_payroll_views.payroll_group_component_remove_api, name='hr_payroll_group_component_remove'),
    path('employees/<uuid:employee_id>/payroll/', hr_payroll_views.employee_payroll_profile_tab, name='employee_payroll_tab'),
    path('employees/<uuid:employee_id>/payroll/update/', hr_payroll_views.employee_payroll_profile_update_api, name='employee_payroll_update'),
    path('hr/payroll/payslips/generate-single/', hr_payroll_views.payslip_generate_api, name='hr_payslip_generate_single'),
    path('hr/payroll/payslips/generate-group/', hr_payroll_views.payslip_generate_group_api, name='hr_payslip_generate_group'),
    path('hr/payroll/payslips/<uuid:pk>/approve/', hr_payroll_views.payslip_approve_api, name='hr_payslip_approve'),
    path('hr/payroll/payslips/<uuid:pk>/reject/', hr_payroll_views.payslip_reject_api, name='hr_payslip_reject'),
    path('hr/payroll/payslips/<uuid:pk>/regenerate/', hr_payroll_views.payslip_regenerate_api, name='hr_payslip_regenerate'),
    path('hr/payroll/payslips/<uuid:pk>/mark-paid/', hr_payroll_views.payslip_mark_paid_api, name='hr_payslip_mark_paid'),
    path('hr/payroll/payslips/<uuid:pk>/unmark-paid/', hr_payroll_views.payslip_unmark_paid_api, name='hr_payslip_unmark_paid'),
    path('hr/payroll/payslips/<uuid:pk>/pdf/', hr_payroll_views.PayslipPDFView.as_view(), name='hr_payslip_pdf'),
    path('hr/payroll/payslip-settings/update/', hr_payroll_views.payslip_settings_update_api, name='hr_payslip_settings_update'),
    path('hr/payroll/reports/templates/save/', hr_payroll_views.payslip_report_template_save_api, name='hr_payslip_report_template_save'),
    path('hr/payroll/reports/templates/<uuid:pk>/run/', hr_payroll_views.payslip_report_template_run_api, name='hr_payslip_report_template_run'),

    # File upload API
    path('api/upload/document/', views.upload_document_api, name='upload_document_api'),
    path('api/upload/cleanup/', views.cleanup_temp_files_api, name='cleanup_temp_files_api'),
    
    # Admission AJAX API endpoints
    path('api/academic-years/', views.AcademicYearAjaxView.as_view(), name='academic_years_ajax'),
    path('api/courses/', views.CourseAjaxView.as_view(), name='courses_ajax'),
    path('api/admission/initialize-data/', views.initialize_basic_data_ajax, name='initialize_data_ajax'),
    path('api/admission/data-status/', views.admission_data_status_ajax, name='admission_data_status_ajax'),
    path('api/admission/quick-academic-year/', views.create_quick_academic_year_ajax, name='quick_academic_year_ajax'),
    
    # Admission number generation endpoints
    path('api/generate-admission-number/', views.generate_admission_number_api, name='generate_admission_number_api'),
    path('api/validate-admission-number/', views.validate_admission_number_api, name='validate_admission_number_api'),
    path('api/batches/active/', views.active_batches_api, name='active_batches_api'),
    
    # QuickBooks fee sync API endpoints
    path('api/quickbooks/fee-payment/', fee_views.QuickBooksFeePaymentView.as_view(), name='quickbooks_fee_payment'),
    path('api/quickbooks/student-sync/', fee_views.QuickBooksStudentSyncView.as_view(), name='quickbooks_student_sync'),
    path('api/quickbooks/bulk-student-sync/', fee_views.QuickBooksBulkStudentSyncView.as_view(), name='quickbooks_bulk_student_sync'),
    path('api/quickbooks/receipt-reconciliation/', fee_views.QuickBooksReceiptReconciliationView.as_view(), name='quickbooks_receipt_reconciliation'),
    
    # Skillset management
    path('subject_skill_sets/', views.SkillSetsListView.as_view(), name='skill_sets_list'),
    path('skillsets/<uuid:pk>/', views.SkillSetDetailView.as_view(), name='skillset_detail'),

    # Link Batches
    path('subjects_center/link_batches/', views.LinkBatchesView.as_view(), name='link_batches'),
    
    # Subject Center API endpoints
    path('api/subjects/<uuid:subject_id>/', views.get_subject_api, name='get_subject_api'),
    path('api/create-subject/', views.create_subject_api, name='create_subject_api'),
    path('api/update-subject/', views.update_subject_api, name='update_subject_api'),
    path('api/delete-subject/', views.delete_subject_api, name='delete_subject_api'),
    path('api/copy-subjects-to-class/', views.copy_subjects_to_class_api, name='copy_subjects_to_class_api'),
    path('api/class-batches/', views.get_class_batches_api, name='get_class_batches_api'),
    path('api/create-subject-group/', views.create_subject_group_api, name='create_subject_group_api'),
    path('api/create-skill-set/', views.create_skill_set_api, name='create_skill_set_api'),
    path('api/create-skill/', views.create_skill_api, name='create_skill_api'),
    path('api/create-sub-skill/', views.create_sub_skill_api, name='create_sub_skill_api'),
    path('api/update-skill/', views.update_skill_api, name='update_skill_api'),
    path('api/delete-skill/', views.delete_skill_api, name='delete_skill_api'),
    path('api/create-elective-group/', views.create_elective_group_api, name='create_elective_group_api'),
    path('api/import-subjects/', views.import_subjects_api, name='import_subjects_api'),
    path('api/link-batches/save/', views.link_batches_save_api, name='link_batches_save_api'),

    # File storage (public/private) — reference endpoints
    path('files/public/upload/', file_views.PublicFileUploadView.as_view(), name='file_public_upload'),
    path('files/private/upload/', file_views.PrivateFileUploadView.as_view(), name='file_private_upload'),
    path('files/private/download/', file_views.private_file_download, name='file_private_download'),
    path('files/private/cookies/', file_views.private_prefix_cookies, name='file_private_cookies'),

    # Report Management
    path('reports/', views.GeneratedReportsView.as_view(), name='generated_reports'),
    path('reports/templates/', views.ReportTemplateListView.as_view(), name='report_template_list'),
    path('reports/generate/', RedirectView.as_view(pattern_name='core:comprehensive_reports', permanent=False), name='report_generation'),
    path('api/reports/create-template/', views.create_report_template_api, name='create_report_template_api'),
    path('api/reports/templates/<uuid:template_id>/', views.get_report_template_api, name='get_report_template_api'),
    path('api/reports/templates/<uuid:template_id>/update/', views.update_report_template_api, name='update_report_template_api'),
    path('api/reports/templates/<uuid:template_id>/delete/', views.delete_report_template_api, name='delete_report_template_api'),
    path('api/reports/templates/<uuid:template_id>/set-default/', views.set_default_report_template_api, name='set_default_report_template_api'),
    path('api/reports/card-defaults/', views.report_card_defaults_api, name='report_card_defaults_api'),
    path('api/reports/preflight/', views.preflight_report_api, name='preflight_report_api'),
    path('api/reports/cancel-generation/', views.cancel_report_generation_api, name='cancel_report_generation_api'),
    path('api/reports/bulk-delete/', views.bulk_delete_reports_api, name='bulk_delete_reports_api'),
    path('api/reports/bulk-download-zip/', views.bulk_download_reports_zip_api, name='bulk_download_reports_zip_api'),
    path('api/reports/zip-enqueue/', views.enqueue_reports_zip_download_api, name='enqueue_reports_zip_download_api'),
    path('api/reports/zip-status/<uuid:job_id>/', views.reports_zip_status_api, name='reports_zip_status_api'),
    path('api/reports/zip-download/<uuid:job_id>/', views.reports_zip_download_api, name='reports_zip_download_api'),
    path('reports/templates/<uuid:template_id>/preview/', views.report_template_preview, name='report_template_preview'),
    path('api/reports/generate/', views.generate_reports_api, name='generate_reports_api'),
    path('api/reports/generation-poll/', views.generation_poll_api, name='generation_poll_api'),
    path('api/reports/<uuid:report_id>/status/', views.report_status_api, name='report_status_api'),
    path('api/reports/<uuid:report_id>/download/', views.download_report_api, name='download_report_api'),
    
    # Marks Entry (the Gradebook workflow is the single source of truth).
    # The two legacy entry points below now redirect into the Gradebook.
    path('marks/', RedirectView.as_view(pattern_name='core:gradebook_management', permanent=False), name='marks_entry'),
    path('marks/exam-group/<uuid:exam_group_id>/', views.ExamGroupMarksEntryView.as_view(), name='exam_group_marks_entry'),
    path('marks/exam/<uuid:exam_id>/', views.SingleExamMarksEntryView.as_view(), name='single_exam_marks_entry'),
    path('marks/<uuid:exam_group_id>/<uuid:batch_id>/', views.legacy_exam_marks_detail_redirect, name='exam_marks_detail'),
    path('api/marks/save/', views.save_marks_api, name='save_marks_api'),
    path('api/marks/submit/', views.submit_exam_marks_api, name='submit_exam_marks_api'),
    path('api/teacher-comments/save/', views.save_teacher_comments_api, name='save_teacher_comments_api'),
    path('api/teacher-comments/<uuid:exam_group_id>/', views.get_teacher_comments_api, name='get_teacher_comments_api'),
    path('api/reports/generate-batch-reports/<uuid:exam_group_id>/<uuid:batch_id>/', views.generate_batch_reports_api, name='generate_batch_reports_api'),
    path('api/exam-group/<uuid:exam_group_id>/<uuid:batch_id>/activities/', views.batch_activities_api, name='batch_activities_api'),
    path('api/exam-group/<uuid:exam_group_id>/<uuid:batch_id>/activities/save/', views.save_batch_activities_api, name='save_batch_activities_api'),
    path('api/reports/validate-marks/<uuid:exam_group_id>/<uuid:batch_id>/', views.validate_batch_marks_api, name='validate_batch_marks_api'),
    
    # Gradebook Management
    path('gradebook/', views.GradebookIndexView.as_view(), name='gradebook_index'),
    path('gradebook/management/', views.GradebookManagementView.as_view(), name='gradebook_management'),
    path('gradebook/class/<uuid:course_id>/', views.ClassExamPlannerView.as_view(), name='class_exam_planner'),
    path('gradebook/create-exam/', views.CreateExamView.as_view(), name='create_exam'),
    path('gradebook/create-exam/<uuid:batch_id>/', views.CreateExamView.as_view(), name='create_exam_for_batch'),
    path('gradebook/edit-term-exam/<uuid:exam_group_id>/', views.EditTermExamView.as_view(), name='edit_term_exam'),
    path('api/gradebook/create-exam/', views.create_exam_api, name='create_exam_api'),
    path('api/gradebook/update-term-exam/<uuid:exam_group_id>/', views.update_term_exam_api, name='update_term_exam_api'),
    path('api/gradebook/batch-subjects/<uuid:batch_id>/', views.get_batch_subjects_api, name='get_batch_subjects_api'),

    # New Enhanced Grading System URLs
    path('gradebook/grading-settings/', views.GradingSettingsView.as_view(), name='grading_settings'),
    path('gradebook/skills-assessment/', views.SkillsAssessmentIndexView.as_view(), name='skills_assessment_index'),
    path('gradebook/skills-assessment/class/<uuid:batch_id>/', views.ClassSkillsAssessmentView.as_view(), name='class_skills_assessment'),
    path('gradebook/skills-assessment/new/<uuid:batch_id>/', views.NewSkillsAssessmentView.as_view(), name='new_skills_assessment'),
    path('gradebook/skills-assessment/individual/', views.IndividualSkillsAssessmentView.as_view(), name='individual_skills_assessment'),
    path('gradebook/skills-assessment/reports/<uuid:batch_id>/', views.SkillsAssessmentReportsView.as_view(), name='skills_assessment_reports'),
    path('gradebook/skills-assessment/progress-tracking/', views.SkillsProgressTrackingView.as_view(), name='skills_progress_tracking'),
    path('gradebook/skills-assessment/category/<str:category_code>/', views.SkillsCategoryView.as_view(), name='skills_category_view'),
    path('gradebook/skills-assessment/bulk/', views.BulkSkillsAssessmentView.as_view(), name='bulk_skills_assessment'),
    path('gradebook/enhanced-score-entry/', views.EnhancedScoreEntryView.as_view(), name='enhanced_score_entry'),
    path('gradebook/comprehensive-reports/', views.ComprehensiveReportsView.as_view(), name='comprehensive_reports'),

    # New Grading System APIs
    path('api/gradebook/grading-type/create/', views.create_grading_type_api, name='create_grading_type_api'),
    path('api/gradebook/grading-type/<uuid:grading_type_id>/', views.get_grading_type_api, name='get_grading_type_api'),
    path('api/gradebook/grading-type/<uuid:grading_type_id>/update/', views.update_grading_type_api, name='update_grading_type_api'),
    path('api/gradebook/grading-type/<uuid:grading_type_id>/delete/', views.delete_grading_type_api, name='delete_grading_type_api'),
    path('api/gradebook/grading-levels/', views.get_grading_levels_api, name='get_grading_levels_api'),
    path('api/gradebook/grading-levels/create/', views.create_grading_level_api, name='create_grading_level_api'),
    path('api/gradebook/coscholastic/create/', views.create_coscholastic_api, name='create_coscholastic_api'),
    path('api/gradebook/coscholastic/<uuid:assessment_id>/', views.get_coscholastic_api, name='get_coscholastic_api'),
    path('api/gradebook/coscholastic/<uuid:assessment_id>/update/', views.update_coscholastic_api, name='update_coscholastic_api'),
    path('api/gradebook/coscholastic/<uuid:assessment_id>/delete/', views.delete_coscholastic_api, name='delete_coscholastic_api'),
    path('api/gradebook/subject-settings/<uuid:setting_id>/update/', views.update_subject_grading_settings_api, name='update_subject_grading_settings_api'),
    path('api/gradebook/grade-levels/<uuid:batch_id>/', views.get_grade_levels_api, name='get_grade_levels_api'),
    path('api/gradebook/batch/<uuid:batch_id>/grading-scale/', views.batch_grading_scale_api, name='batch_grading_scale_api'),
    path('api/gradebook/batch/<uuid:batch_id>/grading-scale/add/', views.add_batch_grading_level_api, name='add_batch_grading_level_api'),
    path('api/gradebook/batch/<uuid:batch_id>/grading-scale/reset/', views.reset_batch_grading_scale_api, name='reset_batch_grading_scale_api'),
    path('api/gradebook/grading-level/<uuid:level_id>/update/', views.update_grading_level_api, name='update_grading_level_api'),
    path('api/gradebook/grading-level/<uuid:level_id>/delete/', views.delete_grading_level_api, name='delete_grading_level_api'),
    path('api/gradebook/subject-settings/', views.get_subject_settings_api, name='get_subject_settings_api'),
    path('api/gradebook/exam/<uuid:exam_id>/details/', views.get_exam_score_entry_details_api, name='get_exam_score_entry_details_api'),
    path('api/gradebook/exam/<uuid:exam_id>/save-scores/', views.save_exam_scores_api, name='save_exam_scores_api'),
    path('api/gradebook/students/', views.get_students_api, name='get_students_api'),
    path('api/gradebook/terms/', views.get_terms_api, name='get_terms_api'),
    path('api/gradebook/generate-reports/', views.generate_reports_api, name='generate_reports_api'),
    path('api/gradebook/download-reports/', views.download_reports_api, name='download_reports_api'),
    path('api/gradebook/skills-assessment/export/', views.export_skills_assessment_api, name='export_skills_assessment_api'),
    path('api/gradebook/skill-items/create/', views.create_skill_item_api, name='create_skill_item_api'),
    path('api/gradebook/skill-items/reorder/', views.reorder_skill_items_api, name='reorder_skill_items_api'),
    path('api/gradebook/skill-items/<uuid:item_id>/update/', views.update_skill_item_api, name='update_skill_item_api'),
    path('api/gradebook/skill-items/<uuid:item_id>/delete/', views.delete_skill_item_api, name='delete_skill_item_api'),
    path('api/gradebook/skills-assessment/save/', views.save_skills_assessment_api, name='save_skills_assessment_api'),
    path('api/gradebook/skills-assessment/load/', views.load_skills_assessment_api, name='load_skills_assessment_api'),

    # Grading Scale CRUD
    path('api/gradebook/grading-scale/create/', views.create_grading_scale_api, name='create_grading_scale_api'),
    path('api/gradebook/grading-scale/<uuid:scale_id>/', views.get_grading_scale_api, name='get_grading_scale_api'),
    path('api/gradebook/grading-scale/<uuid:scale_id>/update/', views.update_grading_scale_api, name='update_grading_scale_api'),
    path('api/gradebook/grading-scale/<uuid:scale_id>/delete/', views.delete_grading_scale_api, name='delete_grading_scale_api'),
    path('api/gradebook/grading-scale/<uuid:scale_id>/grade-values/create/', views.create_grade_value_api, name='create_grade_value_api'),
    path('api/gradebook/grading-scale/<uuid:scale_id>/grade-values/reorder/', views.reorder_grade_values_api, name='reorder_grade_values_api'),
    path('api/gradebook/grade-value/<uuid:value_id>/update/', views.update_grade_value_api, name='update_grade_value_api'),
    path('api/gradebook/grade-value/<uuid:value_id>/delete/', views.delete_grade_value_api, name='delete_grade_value_api'),

    # Enhanced Attendance API endpoints
    path('api/attendance/student/<uuid:student_id>/summary/', views.get_student_attendance_summary_api, name='student_attendance_summary_api'),
    path('api/attendance/batch/<uuid:batch_id>/report/', views.get_batch_attendance_report_api, name='batch_attendance_report_api'),
    path('api/attendance/summaries/update/', views.update_attendance_summaries_api, name='update_attendance_summaries_api'),
    path('api/attendance/export/', views.export_attendance_report_enhanced_api, name='export_attendance_enhanced_api'),

    # Library
    path('library/', views.LibraryIndexView.as_view(), name='library'),
    path('library/scan/', LibraryScanView.as_view(), name='library_scan'),

    # Hostel
    path('hostel/', views.HostelIndexView.as_view(), name='hostel'),

    # Transport
    path('transport/', transport_views.TransportDashboardView.as_view(), name='transport'),
    path('transport/', transport_views.TransportDashboardView.as_view(), name='transport_dashboard'),
    path('transport/settings/', transport_views.TransportSettingsView.as_view(), name='transport_settings'),
    path('transport/settings/update/', transport_views.transport_settings_update, name='transport_settings_update'),

    # Transport — full-page shells
    path('transport/stops/', transport_views.TransportEntityPageView.as_view(entity='stops'), name='transport_stops'),
    path('transport/vehicles/', transport_views.TransportEntityPageView.as_view(entity='vehicles'), name='transport_vehicles'),
    path('transport/staff/', transport_views.TransportEntityPageView.as_view(entity='staff'), name='transport_staff'),
    path('transport/routes/', transport_views.TransportEntityPageView.as_view(entity='routes'), name='transport_routes'),
    path('transport/assignments/', transport_views.TransportEntityPageView.as_view(entity='assignments'), name='transport_assignments'),

    # Transport — htmx list fragments
    path('transport/stops/list/', transport_views.TransportStopListView.as_view(), name='transport_stop_list'),
    path('transport/vehicles/list/', transport_views.TransportVehicleListView.as_view(), name='transport_vehicle_list'),
    path('transport/staff/list/', transport_views.TransportStaffListView.as_view(), name='transport_staff_list'),
    path('transport/routes/list/', transport_views.TransportRouteListView.as_view(), name='transport_route_list'),
    path('transport/assignments/list/', transport_views.TransportAssignmentListView.as_view(), name='transport_assignment_list'),

    # Transport — modal lookups (before the generic <entity>/<action> catch-all)
    path('transport/routes/<uuid:pk>/stop-options/', transport_views.transport_route_stops_options, name='transport_route_stop_options'),
    path('transport/students/search/', transport_views.transport_student_search, name='transport_student_search'),

    # Transport — htmx write endpoints (create/update/toggle/delete/charge/end)
    path('transport/<str:entity>/<str:action>/', transport_views.transport_entity_write, name='transport_write'),
    path('transport/<str:entity>/<str:action>/<uuid:pk>/', transport_views.transport_entity_write, name='transport_write_pk'),

    # Assignments
    path('assignments/', views.AssignmentIndexView.as_view(), name='assignments'),
    path('assignments/<uuid:assignment_id>/', views.AssignmentDetailPageView.as_view(), name='assignment_detail'),

    # News
    path('news/', views.NewsIndexView.as_view(), name='news'),

    # User Management
    path('users/', views.UserManagementView.as_view(), name='user_management'),

    # Roles & permissions (RBAC)
    path('settings/roles/', role_views.RoleListView.as_view(), name='role_list'),
    path('settings/roles/create/', role_views.role_create_api, name='role_create'),
    path('settings/roles/<uuid:pk>/', role_views.RoleDetailView.as_view(), name='role_detail'),
    path('settings/roles/<uuid:pk>/update/', role_views.role_update_api, name='role_update'),
    path('settings/roles/<uuid:pk>/permissions/', role_views.role_set_permissions_api, name='role_set_permissions'),
    path('settings/roles/<uuid:pk>/delete/', role_views.role_delete_api, name='role_delete'),

    # Activity catalogue (clubs/sports/other) for the teacher portal
    path('configuration/activities/', views.ActivityCatalogueView.as_view(), name='activity_catalogue'),

    # Communication
    path('communication/', views.CommunicationView.as_view(), name='communication'),
    path('api/communication/batch-guardians/', views.CommunicationBatchGuardiansView.as_view(), name='communication_batch_guardians'),
]