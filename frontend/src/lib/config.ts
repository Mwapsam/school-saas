/**
 * Build-time configuration for the frontend. These values come from environment
 * variables set at build time and are baked into the Next.js bundle.
 *
 * All school-specific branding (name, logo, colors, contact info) is loaded
 * from the backend API at runtime via /api/school/config/ and is NOT set here.
 * This keeps the frontend decoupled from any specific school.
 *
 * See .env.example for configuration instructions.
 */
export const config = {
  /** Backend API base URL. Required for all deployments. */
  apiBaseUrl:
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",

  /**
   * Generic application name used as fallback before school config loads.
   * Once the app runs, the actual school name is fetched from the backend
   * and displayed in the UI. This is only shown briefly during initial load.
   * Defaults to a generic placeholder if not configured.
   */
  appName:
    process.env.NEXT_PUBLIC_APP_NAME ?? "School Portal",

  /**
   * Client application identifier. Sent as X-Client-App header to the backend.
   * Must be registered in the school's Configuration → Manage Clients section.
   * For multi-tenant deployments, use a generic identifier that is reusable
   * across all schools (e.g., "generic-school-portal-web"). The backend
   * validates this header per-school and can enable/disable or version-lock it.
   * Required for production deployments.
   */
  clientApp:
    process.env.NEXT_PUBLIC_CLIENT_APP ?? "generic-school-portal-web",

  /** Semantic version of this build, sent as X-Client-App-Version header. */
  clientAppVersion:
    process.env.NEXT_PUBLIC_CLIENT_APP_VERSION ?? "0.1.0",
} as const;

const withBaseUrl = (path: string) =>
  `${config.apiBaseUrl}${path}`;

export const API = {
  // Auth
  login: withBaseUrl("/api/portal/auth/login/"),
  refresh: withBaseUrl("/api/portal/auth/refresh/"),
  me: withBaseUrl("/api/portal/auth/me/"),
  passwordChange: withBaseUrl("/api/portal/auth/password-change/"),
  passwordResetRequest: withBaseUrl("/api/portal/auth/password-reset/request/"),
  passwordResetConfirm: withBaseUrl("/api/portal/auth/password-reset/confirm/"),

  // Parent
  parentDashboard: withBaseUrl("/api/portal/parent/dashboard/"),
  parentChildren: withBaseUrl("/api/portal/parent/children/"),
  announcements: withBaseUrl("/api/portal/parent/announcements/"),

  childResults: (id: string) =>
    withBaseUrl(`/api/portal/parent/children/${id}/results/`),

  childReportCards: (id: string) =>
    withBaseUrl(`/api/portal/parent/children/${id}/reports/`),

  childReportCardPdf: (childId: string, reportId: string) =>
    withBaseUrl(`/api/portal/parent/children/${childId}/reports/${reportId}/pdf/`),

  childAttendance: (id: string) =>
    withBaseUrl(`/api/portal/parent/children/${id}/attendance/`),

  childFees: (id: string, academicYear?: string) =>
    withBaseUrl(
      `/api/portal/parent/children/${id}/fees/${
        academicYear
          ? `?academic_year=${academicYear}`
          : ""
      }`
    ),

  parentInvoices: withBaseUrl("/api/portal/parent/invoices/"),

  parentInvoicePdf: (id: string) =>
    withBaseUrl(`/api/portal/parent/invoices/${id}/pdf/`),

  parentReceipts: withBaseUrl("/api/portal/parent/receipts/"),

  parentReceiptPdf: (referenceNumber: string) =>
    withBaseUrl(`/api/portal/parent/receipts/${referenceNumber}/pdf/`),

  // Teacher
  teacherDashboard: withBaseUrl("/api/portal/teacher/dashboard/"),

  teacherClasses: withBaseUrl("/api/portal/teacher/classes/"),

  register: (batchId: string) =>
    withBaseUrl(
      `/api/portal/teacher/classes/${batchId}/register/`
    ),

  teacherExams: withBaseUrl("/api/portal/teacher/exams/"),

  marksheet: (examId: string) =>
    withBaseUrl(
      `/api/portal/teacher/exams/${examId}/marksheet/`
    ),

  // Shared with the staff exam-group page — same endpoints, not a portal-only copy.
  saveTeacherComments: withBaseUrl("/api/teacher-comments/save/"),

  teacherComments: (examGroupId: string) =>
    withBaseUrl(`/api/teacher-comments/${examGroupId}/`),

  skillsCatalog: withBaseUrl("/api/portal/teacher/skills/"),

  studentSkills: (studentId: string) =>
    withBaseUrl(
      `/api/portal/teacher/skills/students/${studentId}/`
    ),

  activities: (batchId: string) =>
    withBaseUrl(
      `/api/portal/teacher/classes/${batchId}/activities/`
    ),

  skillsComments: (batchId: string) =>
    withBaseUrl(
      `/api/portal/teacher/classes/${batchId}/skills-comments/`
    ),

  skillsSubmission: (batchId: string) =>
    withBaseUrl(
      `/api/portal/teacher/classes/${batchId}/skills-submission/`
    ),

  // Librarian
  librarianDashboard: withBaseUrl("/api/portal/librarian/dashboard/"),

  librarianLibraries: withBaseUrl("/api/portal/librarian/libraries/"),

  librarianBooks: withBaseUrl("/api/portal/librarian/books/"),

  librarianBookDetail: (bookId: string) =>
    withBaseUrl(`/api/portal/librarian/books/${bookId}/`),

  librarianBookHistory: (bookId: string) =>
    withBaseUrl(`/api/portal/librarian/books/${bookId}/history/`),

  librarianCategories: withBaseUrl("/api/portal/librarian/categories/"),
  librarianBatches: withBaseUrl("/api/portal/librarian/batches/"),
  librarianBatchStudents: (batchId: string) =>
    withBaseUrl(`/api/portal/librarian/batches/${batchId}/students/`),

  librarianScanLookup: withBaseUrl("/api/portal/librarian/scan/lookup/"),

  librarianScanIssue: withBaseUrl("/api/portal/librarian/scan/issue/"),

  librarianScanReturn: withBaseUrl("/api/portal/librarian/scan/return/"),

  librarianIssued: withBaseUrl("/api/portal/librarian/issued/"),

  librarianOverdue: withBaseUrl("/api/portal/librarian/overdue/"),

  // HR
  hrDashboard: withBaseUrl("/api/portal/hr/dashboard/"),
  hrEmployees: withBaseUrl("/api/portal/hr/employees/"),
  hrEmployee: (id: string) => withBaseUrl(`/api/portal/hr/employees/${id}/`),
  hrEmployeeQualifications: (id: string) => withBaseUrl(`/api/portal/hr/employees/${id}/qualifications/`),
  hrEmployeeHistory: (id: string) => withBaseUrl(`/api/portal/hr/employees/${id}/history/`),
  hrEmployeeContracts: (id: string) => withBaseUrl(`/api/portal/hr/employees/${id}/contract/`),
  hrEmployeeDocuments: (id: string) => withBaseUrl(`/api/portal/hr/employees/${id}/documents/`),
  hrEmployeeAttendance: (id: string) => withBaseUrl(`/api/portal/hr/employees/${id}/attendance/`),
  hrDocument: (id: string) => withBaseUrl(`/api/portal/hr/documents/${id}/`),
  hrContracts: withBaseUrl("/api/portal/hr/contracts/"),
  hrContractRenew: (id: string) => withBaseUrl(`/api/portal/hr/contracts/${id}/renew/`),
  hrContractDecision: (id: string) => withBaseUrl(`/api/portal/hr/contracts/${id}/decision/`),
  hrLeave: withBaseUrl("/api/portal/hr/leave/"),
  hrLeaveCalendar: withBaseUrl("/api/portal/hr/leave/calendar/"),
  hrLeaveSupervisorReview: (id: string) => withBaseUrl(`/api/portal/hr/leave/${id}/supervisor-review/`),
  hrLeaveHRReview: (id: string) => withBaseUrl(`/api/portal/hr/leave/${id}/hr-review/`),
  hrAttendance: withBaseUrl("/api/portal/hr/attendance/"),
  hrAttendanceAnalytics: withBaseUrl("/api/portal/hr/attendance/analytics/"),
  hrTasks: withBaseUrl("/api/portal/hr/tasks/"),
  hrTask: (id: string) => withBaseUrl(`/api/portal/hr/tasks/${id}/`),
  hrAudit: withBaseUrl("/api/portal/hr/audit/"),
  hrAnalytics: withBaseUrl("/api/portal/hr/analytics/"),
  hrPolicies: withBaseUrl("/api/portal/hr/policies/"),
  hrPolicy: (id: string) => withBaseUrl(`/api/portal/hr/policies/${id}/`),
  hrPolicyAcks: (id: string) => withBaseUrl(`/api/portal/hr/policies/${id}/acknowledgements/`),
  hrMePolicies: withBaseUrl("/api/portal/hr/me/policies/"),
  hrMePolicyAcknowledge: (id: string) =>
    withBaseUrl(`/api/portal/hr/me/policies/${id}/acknowledge/`),
  hrMeReviews: withBaseUrl("/api/portal/hr/me/reviews/"),
  hrMeReview: (id: string) => withBaseUrl(`/api/portal/hr/me/reviews/${id}/`),
  hrDisciplinary: withBaseUrl("/api/portal/hr/disciplinary/"),
  hrDisciplinaryCase: (id: string) => withBaseUrl(`/api/portal/hr/disciplinary/${id}/`),
  hrEmployeeDisciplinary: (id: string) => withBaseUrl(`/api/portal/hr/employees/${id}/disciplinary/`),
  hrGrievances: withBaseUrl("/api/portal/hr/grievances/"),
  hrGrievance: (id: string) => withBaseUrl(`/api/portal/hr/grievances/${id}/`),
  hrExitList: withBaseUrl("/api/portal/hr/exit/"),
  hrEmployeeExit: (id: string) => withBaseUrl(`/api/portal/hr/employees/${id}/exit/`),
  hrExit: (id: string) => withBaseUrl(`/api/portal/hr/exit/${id}/`),
  hrExitComplete: (id: string) => withBaseUrl(`/api/portal/hr/exit/${id}/complete/`),
  hrExitItem: (id: string) => withBaseUrl(`/api/portal/hr/exit/items/${id}/`),
  hrTraining: withBaseUrl("/api/portal/hr/training/"),
  hrTrainingRecord: (id: string) => withBaseUrl(`/api/portal/hr/training/${id}/`),
  hrTrainingCompliance: withBaseUrl("/api/portal/hr/training/compliance/"),
  hrEmployeeTraining: (id: string) => withBaseUrl(`/api/portal/hr/employees/${id}/training/`),
  hrReviews: withBaseUrl("/api/portal/hr/performance/reviews/"),
  hrReview: (id: string) => withBaseUrl(`/api/portal/hr/performance/reviews/${id}/`),
  hrReviewComplete: (id: string) => withBaseUrl(`/api/portal/hr/performance/reviews/${id}/complete/`),
  hrEmployeePerformance: (id: string) => withBaseUrl(`/api/portal/hr/employees/${id}/performance/`),
  hrOnboardingList: withBaseUrl("/api/portal/hr/onboarding/"),
  hrEmployeeOnboarding: (id: string) => withBaseUrl(`/api/portal/hr/employees/${id}/onboarding/`),
  hrOnboardingItem: (id: string) => withBaseUrl(`/api/portal/hr/onboarding/items/${id}/`),
  hrVacancies: withBaseUrl("/api/portal/hr/recruitment/vacancies/"),
  hrVacancy: (id: string) => withBaseUrl(`/api/portal/hr/recruitment/vacancies/${id}/`),
  hrVacancyApplicants: (id: string) => withBaseUrl(`/api/portal/hr/recruitment/vacancies/${id}/applicants/`),
  hrApplicant: (id: string) => withBaseUrl(`/api/portal/hr/recruitment/applicants/${id}/`),
  hrApplicantAdvance: (id: string) => withBaseUrl(`/api/portal/hr/recruitment/applicants/${id}/advance/`),
  hrApplicantConvert: (id: string) => withBaseUrl(`/api/portal/hr/recruitment/applicants/${id}/convert/`),
  hrReports: withBaseUrl("/api/portal/hr/reports/"),
  hrReport: (slug: string, qs = "") => withBaseUrl(`/api/portal/hr/reports/${slug}/${qs}`),
  hrMeProfile: withBaseUrl("/api/portal/hr/me/profile/"),
  hrMeAttendance: withBaseUrl("/api/portal/hr/me/attendance/"),
  hrMeLeave: withBaseUrl("/api/portal/hr/me/leave/"),
  hrMeLeaveBalance: withBaseUrl("/api/portal/hr/me/leave/balance/"),
  hrMeContracts: withBaseUrl("/api/portal/hr/me/contracts/"),
  hrMeDocuments: withBaseUrl("/api/portal/hr/me/documents/"),

  // HR settings + leave balances
  hrLeaveBalances: withBaseUrl("/api/portal/hr/leave/balances/"),
  hrSettingsLookup: (key: string) =>
    withBaseUrl(`/api/portal/hr/settings/lookups/${key}/`),
  hrSettingsLookupItem: (key: string, id: string) =>
    withBaseUrl(`/api/portal/hr/settings/lookups/${key}/${id}/`),
  hrSettingsWorkingDays: withBaseUrl("/api/portal/hr/settings/working-days/"),
  hrSettingsDocumentTypes: withBaseUrl("/api/portal/hr/settings/document-types/"),

  // Payroll
  hrPayslips: withBaseUrl("/api/portal/hr/payroll/payslips/"),
  hrPayslip: (id: string) => withBaseUrl(`/api/portal/hr/payroll/payslips/${id}/`),
  hrPayslipGenerate: withBaseUrl("/api/portal/hr/payroll/payslips/generate/"),
  hrPayslipAction: (id: string, action: string) =>
    withBaseUrl(`/api/portal/hr/payroll/payslips/${id}/${action}/`),
  hrPayrollCategories: withBaseUrl("/api/portal/hr/payroll/categories/"),
  hrPayrollCategory: (id: string) =>
    withBaseUrl(`/api/portal/hr/payroll/categories/${id}/`),
  hrPayrollGroups: withBaseUrl("/api/portal/hr/payroll/groups/"),
  hrPayrollGroup: (id: string) => withBaseUrl(`/api/portal/hr/payroll/groups/${id}/`),
  hrPayrollGroupComponents: (id: string) =>
    withBaseUrl(`/api/portal/hr/payroll/groups/${id}/components/`),
  hrPayrollGroupComponent: (id: string, componentId: string) =>
    withBaseUrl(`/api/portal/hr/payroll/groups/${id}/components/${componentId}/`),
  hrPayrollSettings: withBaseUrl("/api/portal/hr/payroll/settings/"),
  hrEmployeePayroll: (id: string) =>
    withBaseUrl(`/api/portal/hr/employees/${id}/payroll/`),
  hrMePayslips: withBaseUrl("/api/portal/hr/me/payslips/"),
  hrMePayslip: (id: string) => withBaseUrl(`/api/portal/hr/me/payslips/${id}/`),

  // Admission
  admissionCourses: withBaseUrl(
    "/api/portal/admission/courses/"
  ),

  admissionApply: withBaseUrl(
    "/api/portal/admission/apply/"
  ),

  admissionStatus: withBaseUrl(
    "/api/portal/admission/status/"
  ),

  // Enquiry
  enquirySubmit: withBaseUrl(
    "/api/portal/enquiry/submit/"
  ),
} as const;