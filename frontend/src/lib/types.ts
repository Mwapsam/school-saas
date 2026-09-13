/** API response types — the contract between the portal and the Django backend. */

export type Role = "parent" | "teacher" | "librarian" | "hr" | "admin" | "student" | "unknown";

export interface ProfileSnapshot {
  id: string;
  first_name: string;
  last_name: string;
  job_title?: string | null;
  employee_number?: string | null;
  relation?: string | null;
  mobile_phone?: string | null;
  libraries?: { id: string; name: string }[];
}

export interface UserProfile {
  id: string;
  username: string;
  email: string | null;
  full_name: string;
  /** Highest-priority role — the default landing experience. */
  role: Role;
  /** Every role this one account holds, highest priority first. */
  roles: Role[];
  /** Snapshot for the primary role (kept for backwards compatibility). */
  profile: ProfileSnapshot | null;
  /** Per-role profile snapshots, keyed by role. */
  profiles?: Partial<Record<Role, ProfileSnapshot>>;
  /** Parent-portal Feature Access map (Configuration → Feature Access). */
  features?: Record<string, boolean>;
  /** HR codenames the account holds (`hr.*` / `reports.hr*`); drives which HR
   *  sections and actions are shown. Empty for non-HR users. */
  hr_permissions?: string[];
  /** True when the account is linked to an active employee — gates "My HR". */
  has_employee_profile?: boolean;
}

// ── HR portal ───────────────────────────────────────────────────────────────

export interface HRDashboard {
  cards: Record<string, number | null>;
  alerts: {
    contracts_expiring: HRAlertRow[];
    probation_reviews_due: HRAlertRow[];
    documents_missing: HRAlertRow[];
    documents_expiring: HRAlertRow[];
    pending_leave_approvals: HRAlertRow[];
    attendance_watchlist: HRAlertRow[];
    open_tasks: { id: string; title: string; category: string; status: string; due_date: string | null }[];
    appraisals_due?: HRAlertRow[];
    onboarding_outstanding?: HRAlertRow[];
    training_expiring?: HRAlertRow[];
    exit_clearance_outstanding?: HRAlertRow[];
  };
  generated_at: string;
}

// ── HR settings + leave balances ────────────────────────────────────────────

export interface HRLookup {
  id: string;
  name?: string;
  code?: string;
  prefix?: string;
  status?: boolean;
  priority?: number;
  is_paid?: boolean;
  default_annual_days?: number;
  employee_category_id?: string | null;
  max_hours_day?: number | null;
  max_hours_week?: number | null;
}

export interface HRWorkingDaySettings {
  working_days: number[];
  default_daily_hours: number;
  half_day_hours_threshold: number;
}

export interface LeaveBalanceEntry {
  leave_type: string;
  leave_type_id: string;
  allocated: number;
  used: number;
  remaining: number;
}

export interface EmployeeLeaveBalances {
  employee_id: string;
  employee_name: string;
  employee_number: string;
  department: string | null;
  balances: LeaveBalanceEntry[];
}

export interface LeaveCalendarEntry {
  id: string;
  employee_id: string;
  employee_name: string;
  department: string | null;
  leave_type: string;
  start_date: string;
  end_date: string;
}

// ── Payroll ────────────────────────────────────────────────────────────────

export interface PayslipRow {
  id: string;
  employee_id: string;
  employee_name: string;
  employee_number: string;
  payroll_group: string | null;
  period_start: string;
  period_end: string;
  gross_earnings: string | number;
  total_deductions: string | number;
  net_pay: string | number;
  status: "generated" | "approved" | "rejected" | "paid";
  version: number;
}

export interface PayslipLine {
  id: string;
  name: string;
  type: "earning" | "deduction";
  amount: string | number;
  order: number;
}

export interface PayslipDetail extends PayslipRow {
  basic_pay: string | number;
  rejection_reason: string | null;
  generated_at: string | null;
  approved_at: string | null;
  paid_at: string | null;
  line_items: PayslipLine[];
}

export interface PayrollCategory {
  id: string;
  name: string;
  code?: string | null;
  category_type: "earning" | "deduction";
  calculation_type: "fixed" | "percentage";
  default_amount?: string | number | null;
  default_percentage?: string | number | null;
  is_basic_pay?: boolean;
  taxable?: boolean;
  status?: boolean;
}

export interface PayrollGroupComponent {
  id: string;
  payroll_category_id: string;
  category_name: string;
  category_type: "earning" | "deduction";
  override_amount?: string | number | null;
  override_percentage?: string | number | null;
  is_active: boolean;
  order: number;
}

export interface PayrollGroup {
  id: string;
  name: string;
  description?: string | null;
  status?: boolean;
  components: PayrollGroupComponent[];
}

export interface EmployeePayrollProfile {
  payroll_group_id: string | null;
  basic_pay_amount: string | number;
  bank_name?: string | null;
  bank_account_number?: string | null;
  bank_branch?: string | null;
  effective_date?: string | null;
  status?: boolean;
}

export interface EmployeePayroll {
  profile: EmployeePayrollProfile | null;
  payslips: PayslipRow[];
}

export interface HRAlertRow {
  id: string;
  name: string;
  employee_number: string;
  department?: string | null;
  [key: string]: unknown;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface HREmployeeRow {
  id: string;
  employee_number: string;
  full_name: string;
  first_name: string;
  last_name: string;
  email: string | null;
  mobile_phone: string | null;
  job_title: string | null;
  department: string | null;
  position: string | null;
  is_teaching_staff: boolean;
  employment_status: string;
  status: boolean;
  joining_date: string | null;
  gender_label: string;
}

export interface HREmployeeDetail extends HREmployeeRow {
  middle_name: string | null;
  date_of_birth: string | null;
  national_id: string | null;
  marital_status: string | null;
  blood_group: string | null;
  category: string | null;
  grade: string | null;
  reporting_manager_name: string | null;
  home_address_line1: string | null;
  home_address_line2: string | null;
  home_city: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  emergency_contact_relation: string | null;
  next_of_kin_name: string | null;
  next_of_kin_phone: string | null;
  next_of_kin_relation: string | null;
  qualification: string | null;
  experience_year: number | null;
  experience_month: number | null;
  photo_url: string | null;
}

export interface HRContract {
  id: string;
  employee_id: string;
  employee_name: string;
  employee_number: string;
  contract_type: string;
  contract_type_label: string;
  start_date: string;
  end_date: string | null;
  probation_end_date: string | null;
  salary_review_date: string | null;
  renewal_status: string;
  notes: string | null;
  days_remaining: number | null;
  supersedes_id: string | null;
  created_at: string;
}

export interface HRDocument {
  id: string;
  employee_id: string;
  document_type: string;
  original_filename: string;
  note: string;
  issued_date: string | null;
  expiry_date: string | null;
  uploaded_at: string;
  status: "valid" | "expiring" | "expired";
  file_url: string | null;
}

export interface HRQualification {
  id: string;
  employee_id: string;
  qualification_type: string;
  name: string;
  institution: string;
  year_obtained: number | null;
  is_highest: boolean;
  document_id: string | null;
}

export interface HRHistoryEvent {
  id: string;
  employee_id: string;
  event_type: string;
  event_type_label: string;
  effective_date: string;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  note: string;
  created_at: string;
}

export interface HRLeave {
  id: string;
  employee_id: string;
  employee_name: string;
  employee_number: string;
  leave_type_name: string;
  start_date: string;
  end_date: string;
  days: number;
  reason: string;
  status: string;
  supervisor_status: string;
  supervisor_remark: string | null;
  hr_status: string;
  hr_remark: string | null;
  document: string | null;
}

export interface HRAttendanceRow {
  id: string;
  employee_id: string;
  employee_name: string;
  date: string;
  status: string;
  status_label: string;
  clock_in: string | null;
  clock_out: string | null;
  hours_worked: string | null;
  late_minutes: number;
  remarks: string | null;
}

export interface HRTask {
  id: string;
  title: string;
  description: string;
  category: string;
  status: "pending" | "in_progress" | "completed";
  due_date: string | null;
  employee_id: string | null;
  employee_name: string | null;
  source: string;
  created_at: string;
  completed_at: string | null;
}

export interface HRVacancy {
  id: string;
  title: string;
  department_id: string | null;
  department_name: string | null;
  number_of_positions: number;
  job_description: string;
  employment_type: string;
  employment_type_label: string;
  is_teaching_role: boolean;
  date_advertised: string | null;
  closing_date: string | null;
  status: string;
  status_label: string;
  applicant_count: number;
  created_at: string;
}

export type ApplicantStage =
  | "applied" | "shortlisted" | "interview" | "reference_check"
  | "offered" | "hired" | "unsuccessful";

export interface HRApplicant {
  id: string;
  vacancy_id: string;
  vacancy_title: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  qualifications_summary: string;
  stage: ApplicantStage;
  stage_label: string;
  stage_changed_at: string | null;
  interview_date: string | null;
  interview_panel: string;
  interview_score: string | null;
  interview_comments: string;
  reference_check_notes: string;
  decision_notes: string;
  converted_employee_id: string | null;
  cv_url: string | null;
  created_at: string;
}

export interface HROnboardingItem {
  id: string;
  label: string;
  order: number;
  is_done: boolean;
  done_at: string | null;
  note: string;
}

export interface HROnboarding {
  id: string;
  employee_id: string;
  employee_name: string;
  employee_number: string;
  department: string | null;
  started_at: string;
  completed_at: string | null;
  progress: { total: number; done: number; percent: number };
  items: HROnboardingItem[];
}

export interface HRPerformanceCriterion {
  id: string;
  name: string;
  order: number;
  rating: number | null;
  comment: string;
}

export interface HRPerformanceReview {
  id: string;
  employee_id: string;
  employee_name: string;
  employee_number: string;
  reviewer_id: string | null;
  reviewer_name: string | null;
  review_period: string;
  review_date: string;
  status: string;
  status_label: string;
  is_teacher_review: boolean;
  overall_rating: number | null;
  objectives: string;
  strengths: string;
  improvement_areas: string;
  development_actions: string;
  reviewer_comments: string;
  employee_comments: string;
  next_review_date: string | null;
  completed_at: string | null;
  created_at: string;
  criteria: HRPerformanceCriterion[];
}

export interface HRTraining {
  id: string;
  employee_id: string;
  employee_name: string;
  employee_number: string;
  name: string;
  category: string;
  category_label: string;
  provider: string;
  training_date: string | null;
  cost: string | null;
  expiry_date: string | null;
  status: string;
  is_mandatory: boolean;
  notes: string;
  compliance_status: string;
  certificate_url: string | null;
  created_at: string;
}

export interface HRTrainingCompliance {
  mandatory_gaps: { id: string; name: string; employee_number: string; missing: string[] }[];
  expiring: HRTraining[];
}

export interface HRExitClearanceItem {
  id: string;
  label: string;
  order: number;
  is_done: boolean;
  done_at: string | null;
  note: string;
}

export interface HRExit {
  id: string;
  employee_id: string;
  employee_name: string;
  employee_number: string;
  department: string | null;
  exit_type: string;
  exit_type_label: string;
  notice_date: string | null;
  last_working_date: string | null;
  reason: string;
  exit_interview_notes: string;
  final_payment_status: string;
  outstanding_leave_days: string | null;
  handover_status: string;
  status: string;
  status_label: string;
  completed_at: string | null;
  created_at: string;
  progress: { total: number; done: number; percent: number };
  clearance_items: HRExitClearanceItem[];
}

export interface HRDisciplinaryCase {
  id: string;
  employee_id: string;
  employee_name: string;
  employee_number: string;
  department: string | null;
  case_type: string;
  case_type_label: string;
  severity: string;
  severity_label: string;
  title: string;
  description: string;
  incident_date: string | null;
  status: string;
  status_label: string;
  investigation_notes: string;
  hearing_date: string | null;
  outcome: string;
  outcome_label: string;
  outcome_notes: string;
  action_date: string | null;
  warning_expiry_date: string | null;
  appeal_notes: string;
  created_at: string;
  closed_at: string | null;
}

export interface HRGrievance {
  id: string;
  raised_by_id: string;
  raised_by_name: string;
  against_id: string | null;
  against_name: string | null;
  category: string;
  category_label: string;
  title: string;
  description: string;
  date_raised: string | null;
  status: string;
  status_label: string;
  review_notes: string;
  resolution_notes: string;
  resolved_at: string | null;
  created_at: string;
}

export interface HRAnalytics {
  generated_at: string;
  headcount: { active: number; teaching: number; non_teaching: number };
  turnover: {
    exits_12m: number;
    joiners_12m: number;
    avg_headcount: number;
    turnover_rate: number;
  };
  trend: { month: string; joined: number; left: number }[];
  tenure: { band: string; count: number }[];
  contract_mix: { contract_type: string; count: number }[];
  leave_days: { type: string; days: number }[];
  attendance_rate: number | null;
  by_department: { department: string; headcount: number; exits_12m: number }[];
}

export interface HRPolicy {
  id: string;
  title: string;
  category: string;
  category_label: string;
  description: string;
  version: string;
  effective_date: string | null;
  requires_acknowledgement: boolean;
  is_active: boolean;
  file_url: string | null;
  ack_summary: { acknowledged: number; eligible: number; percent: number } | null;
  created_at: string;
}

export interface HRPolicyAckRow {
  employee_id: string;
  name: string;
  employee_number: string;
  department: string | null;
  acknowledged_at: string | null;
}

export interface MyPolicies {
  outstanding: HRPolicy[];
  acknowledged: {
    policy_id: string;
    title: string;
    version: string;
    acknowledged_at: string;
  }[];
}

export interface HRAuditEntry {
  id: string;
  actor_label: string;
  action: string;
  target_type: string;
  target_id: string | null;
  field: string;
  old_value: string;
  new_value: string;
  created_at: string;
}

export interface HRReportResult {
  title: string;
  columns: [string, string][];
  rows: Record<string, string | number>[];
}

export interface LoginResponse {
  access: string;
  refresh: string;
  role: Role;
  roles: Role[];
  user: UserProfile;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

export interface BatchSummary {
  id: string;
  name: string;
  course: string | null;
  academic_year: string | null;
  is_class_teacher: boolean;
  has_markable_exams: boolean;
  has_skills_assessment: boolean;
}

export interface Guardian {
  name: string;
  relation: string;
  phone: string | null;
  email: string | null;
}

export interface Child {
  id: string;
  full_name: string;
  admission_no: string;
  gender: string;
  photo_url: string | null;
  current_batch: {
    id: string;
    name: string;
    course: string | null;
    academic_year: string | null;
  } | null;
  guardians: Guardian[];
}

export interface SubjectResult {
  subject: string;
  exam_name: string;
  marks: number | null;
  maximum_marks: number | null;
  percentage: number | null;
  grade: string | null;
  is_absent: boolean;
  remarks: string | null;
}

export interface ResultGroup {
  exam_group_id: string;
  name: string;
  exam_type: string;
  exam_date: string;
  batch_name: string | null;
  subjects: SubjectResult[];
}

export interface StudentReportCard {
  id: string;
  exam_group_id: string;
  name: string;
  term: string | null;
  generated_at: string | null;
}

export interface AttendanceSummary {
  total_days: number;
  present_days: number;
  half_days: number;
  absent_days: number;
  attendance_rate: number | null;
}

export interface ParentDashboard {
  children: {
    child: Child;
    attendance: AttendanceSummary;
    latest_result: ResultGroup | null;
    published_result_count: number;
    results_locked: boolean;
    outstanding_balance: string | number | null;
  }[];
}

export interface FeeStatementLine {
  date: string | null;
  type: string;
  description: string;
  fee_category: string;
  debit: string | number;
  credit: string | number;
}

export interface FeeStatement {
  student_id: string;
  student_name: string;
  admission_no: string;
  academic_year: string;
  line_items: FeeStatementLine[];
  total_charged: string | number;
  total_paid: string | number;
  total_discounts: string | number;
  total_refunds: string | number;
  current_outstanding: string | number;
}

export interface ChildFeesResponse {
  student: Child;
  academic_years: { id: string; name: string }[];
  selected_year: { id: string; name: string } | null;
  statement: FeeStatement | null;
}

export interface FamilyInvoice {
  id: string;
  invoice_number: string;
  status: "open" | "paid" | "void";
  academic_year: string | null;
  subtotal: string | number;
  total_amount: string | number;
  amount_paid: string | number;
  balance_due: string | number;
  due_date: string | null;
  generated_at: string;
}

export interface Receipt {
  reference_number: string;
  student_id: string;
  student_name: string;
  total_amount: string | number;
  paid_on: string;
}

export interface Announcement {
  id: string;
  title: string;
  content: string;
  author: string;
  created_at: string;
  document_url?: string | null;
}

export interface TeacherClass {
  id: string;
  name: string;
  course: string | null;
  academic_year: string | null;
  student_count: number;
  is_class_teacher: boolean;
  has_markable_exams: boolean;
  has_skills_assessment: boolean;
}

export interface TeacherDashboard {
  class_count: number;
  student_count: number;
  classes_marked_today: number;
  classes: TeacherClass[];
}

export type AttendanceStatus =
  | "present"
  | "absent"
  | "late"
  | "half_day"
  | "unmarked";

export interface RegisterEntry {
  student_id: string;
  full_name: string;
  admission_no: string;
  roll_number: string | null;
  status: AttendanceStatus;
  reason: string | null;
}

export interface RegisterResponse {
  batch: { id: string; name: string };
  date: string;
  entries: RegisterEntry[];
}

export interface SaveAttendancePayload {
  date: string;
  entries: {
    student_id: string;
    status: Exclude<AttendanceStatus, "unmarked">;
    reason?: string | null;
  }[];
}

export type AssessmentSlot =
  | "EXAM"
  | "TEST"
  | "CLASSWORK"
  | "ATTAINMENT"
  | "EFFORT";

export interface MarkableExam {
  id: string;
  subject: string;
  exam_name: string;
  exam_group: string;
  batch: { id: string; name: string };
  exam_date: string;
  maximum_marks: number | null;
  is_grade_only: boolean;
  assessment_slot: AssessmentSlot;
  assessment_slot_display: string;
  student_count: number;
  scored_count: number;
  result_published: boolean;
  is_class_teacher: boolean;
}

export interface GradeOption {
  id: string;
  name: string;
  min_percentage: number | null;
}

export interface MarkSheetMeta {
  id: string;
  subject: string;
  exam_name: string;
  exam_group: string;
  exam_group_id: string;
  batch: { id: string; name: string };
  maximum_marks: number | null;
  minimum_marks: number | null;
  assessment_slot: AssessmentSlot;
  assessment_slot_display: string;
  is_grade_only: boolean;
  available_grades: GradeOption[];
  result_published: boolean;
  status: MarkStatus;
  is_class_teacher: boolean;
}

export interface TeacherCommentEntry {
  student_id: string;
  comment: string;
  // True only when the teacher actively edited this field down to blank
  // since it was last loaded — lets the backend tell an intentional clear
  // apart from a field that was simply never populated. See
  // TeacherCommentService.save_comments.
  cleared?: boolean;
}

export interface TeacherCommentsResponse {
  success: boolean;
  signature_image: string;
  comments: TeacherCommentEntry[];
}

export interface SaveTeacherCommentsPayload {
  exam_group_id: string;
  comments: TeacherCommentEntry[];
  signature_image: string;
}

export type MarkStatus = "draft" | "submitted" | "published";

// ── Skills assessment (Beginners / Reception) ────────────────────────────────

export type SkillLevel = "NOT_YET" | "BEGINNING" | "SATISFACTORY" | "GOOD";

export interface SkillItem {
  id: string;
  description: string;
}

export interface SkillCategory {
  code: string;
  name: string;
  items: SkillItem[];
}

export interface SkillsCatalog {
  categories: SkillCategory[];
  terms: string[];
  active_term: string | null;
  academic_year: string | null;
  status: "draft" | "submitted";
  submitted_at: string | null;
  students: { id: string; full_name: string; admission_no: string }[];
}

export interface SaveSkillsPayload {
  term?: string | null;
  levels: Record<string, SkillLevel>;
}

export interface SkillsCommentsResponse {
  batch_id: string;
  term: string | null;
  signature_image: string;
  comments: { student_id: string; comment: string }[];
}

export interface SaveSkillsCommentsPayload {
  term?: string | null;
  comments: { student_id: string; comment: string; cleared?: boolean }[];
  signature_image: string;
}

export interface MarkSheetEntry {
  student_id: string;
  full_name: string;
  admission_no: string;
  roll_number: string | null;
  marks: number | null;
  grade_value_id: string | null;
  is_absent: boolean;
  remarks: string | null;
}

export interface MarkSheetResponse {
  exam: MarkSheetMeta;
  entries: MarkSheetEntry[];
}

export interface SaveMarksPayload {
  submit?: boolean;
  entries: {
    student_id: string;
    marks?: number | null;
    grade_value_id?: string | null;
    is_absent?: boolean;
    remarks?: string | null;
  }[];
}

// ── Term activities (Homework / Project / Clubs / Sports / Other) ────────────

export interface ActivityRating {
  submission: string;
  presentation: string;
  effort: string;
}

export interface ActivityRow {
  student_id: string;
  full_name: string;
  admission_no: string;
  homework: ActivityRating;
  project: ActivityRating;
  clubs: string;
  sports: string;
  other: string;
}

export interface ActivityOptions {
  clubs: string[];
  sports: string[];
  other: string[];
}

export interface ActivitiesResponse {
  exam_groups: { id: string; name: string; term: string }[];
  grades: string[];
  activity_options: ActivityOptions;
  homework_enabled?: boolean;
  activities_enabled?: boolean;
  term?: string;
  academic_year?: string | null;
  students?: ActivityRow[];
}

export interface SaveActivitiesPayload {
  exam_group: string;
  students: {
    student_id: string;
    homework: ActivityRating;
    project: ActivityRating;
    clubs: string;
    sports: string;
    other: string;
  }[];
}

// ── Admission (public) ────────────────────────────────────────────────────────

export interface AdmissionCourse {
  id: string;
  course_name: string;
}

export interface AdmissionFormData {
  // Step 1 — Grade
  course_applied: string;
  // Step 2 — Student
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  nationality: string;
  preferred_name: string;
  home_language: string;
  authorized_pickup_persons: string;
  expected_start_date: string;
  // Step 3 — Guardian
  guardian1_first_name: string;
  guardian1_last_name: string;
  guardian1_relation: string;
  guardian1_mobile: string;
  guardian1_email: string;
  guardian1_house_plot_no: string;
  guardian1_road_name: string;
  guardian1_area_location: string;
  guardian1_flat_block_name: string;
  guardian2_house_plot_no: string;
  guardian2_road_name: string;
  guardian2_area_location: string;
  guardian2_flat_block_name: string;
  emergency_contact_name: string;
  emergency_contact_relation: string;
  emergency_contact_mobile: string;
  emergency_contact_address: string;
  declaration_signature_name: string;
  // Contact
  address: string;
  email: string;
  phone: string;
}

export interface AdmissionSubmitResponse {
  application_number: string;
  status: string;
}

export interface AdmissionStatusResponse {
  application_number: string;
  student_name: string;
  course_applied: string;
  status: string;
  application_date: string;
  remarks: string;
}

// ── Enquiry (public) ────────────────────────────────────────────────────────

export interface EnquiryFormData {
  course: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  email: string;
  phone: string;
  guardian_first_name: string;
  guardian_last_name: string;
  guardian_relation: string;
  guardian_phone: string;
  guardian_email: string;
  source_of_info: string;
  remarks: string;
}

export interface EnquirySubmitResponse {
  enquiry_number: string;
}

// ── Librarian Portal ────────────────────────────────────────────────────────

export interface Library {
  id: string;
  name: string;
  code: string;
  description?: string | null;
  is_active: boolean;
}

export interface BookCategory {
  id: string;
  name: string;
}

export interface LibraryBook {
  id: string;
  title: string;
  author: string | null;
  isbn: string | null;
  book_number: string | null;
  category_name: string | null;
  library_name: string;
  total_copies: number;
  available_copies: number;
  book_type: string;
  school_level: string;
  barcode: string | null;
  price: string | null;
}

export interface BookMovementEntry {
  id: string;
  book_title: string;
  book_number: string | null;
  borrower_name: string;
  borrower_type: string;
  issue_date: string;
  due_date: string;
  return_date: string | null;
  is_returned: boolean;
  is_overdue: boolean;
}

export interface LibrarianDashboard {
  libraries: Library[];
  stats: {
    [library_id: string]: {
      total_books: number;
      available_books: number;
      issued_books: number;
      overdue_books: number;
    };
  };
}
