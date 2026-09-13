import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface ApplicantForAssignment {
  id: string;
  application_number: string;
  first_name: string;
  last_name: string;
  full_name: string;
  date_of_birth?: string;
  email?: string;
  phone?: string;
  mobile?: string;
  status: string;
  status_display: string;
  academic_year?: { id: string; name: string };
  course_applied?: { id: string; course_name: string; code: string };
  application_date: string;
}

export interface BatchOption {
  id: string;
  name: string;
  section_name?: string;
  grade_name?: string;
}

export interface ListResponse<T> {
  count: number;
  page: number;
  page_size: number;
  results: T[];
}

export interface AdmissionStats {
  total_applications: number;
  approved_applications: number;
  admitted_applications: number;
  rejected_applications: number;
  pending_review: number;
  students_admitted_total: number;
  batches_available: number;
}

export interface DiagnosticsResult {
  school_code: string;
  school_name: string;
  ready_for_admissions: boolean;
  missing_requirements: string[];
  warnings: string[];
  data_counts: Record<string, number>;
}

export function useApplicationsForAssignment(
  params: { page?: number; page_size?: number; status?: string; search?: string } = {},
  options: { enabled?: boolean } = {}
) {
  return useQuery({
    queryKey: ['applications-for-assignment', params],
    enabled: options.enabled !== false,
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (params.page) qs.append('page', params.page.toString());
      if (params.page_size) qs.append('page_size', params.page_size.toString());
      if (params.status) qs.append('status', params.status);
      if (params.search) qs.append('search', params.search);
      return await apiClient.get<ListResponse<ApplicantForAssignment>>(
        `/admission-batch-assignment/applications/${qs.toString() ? '?' + qs.toString() : ''}`
      );
    },
  });
}

export function useAvailableBatches() {
  return useQuery({
    queryKey: ['available-batches'],
    queryFn: async () => {
      const response = await apiClient.get<BatchOption[]>(
        '/admission-batch-assignment/batches/'
      );
      return Array.isArray(response) ? response : response.results || [];
    },
  });
}

export function useAdmissionStats() {
  return useQuery({
    queryKey: ['admission-stats'],
    queryFn: async () =>
      await apiClient.get<AdmissionStats>('/admission-batch-assignment/stats/'),
  });
}

export function useAssignSingle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { application_id: string; batch_id: string; roll_number?: string }) =>
      await apiClient.post('/admission-batch-assignment/assign_single/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications-for-assignment'] });
      queryClient.invalidateQueries({ queryKey: ['admission-stats'] });
    },
  });
}

export function useAssignBulk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      assignments: Array<{ application_id: string; batch_id: string; roll_number?: string }>;
    }) => await apiClient.post('/admission-batch-assignment/assign_bulk/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications-for-assignment'] });
      queryClient.invalidateQueries({ queryKey: ['admission-stats'] });
    },
  });
}

export function useDiagnostics() {
  return useQuery({
    queryKey: ['admission-diagnostics'],
    queryFn: async () =>
      await apiClient.get<DiagnosticsResult>('/admission-diagnostics/status/'),
  });
}

export function useApproveApplication(applicationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      await apiClient.post(`/admission-admin/${applicationId}/approve/`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications-for-assignment'] });
      queryClient.invalidateQueries({ queryKey: ['admission-stats'] });
    },
  });
}

export function useRejectApplication(applicationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { reason: string }) =>
      await apiClient.post(`/admission-admin/${applicationId}/reject/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications-for-assignment'] });
      queryClient.invalidateQueries({ queryKey: ['admission-stats'] });
    },
  });
}

export function useBulkStatusUpdate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      application_ids: string[];
      status: 'under_review' | 'approved' | 'rejected' | 'waitlisted';
      reason?: string;
    }) => await apiClient.post('/admission-admin/bulk_status_update/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications-for-assignment'] });
      queryClient.invalidateQueries({ queryKey: ['admission-stats'] });
    },
  });
}

// Application Detail Page Hooks
export interface ExtendedApplicationDetail {
  id: string;
  application_number: string;
  status: string;
  first_name: string;
  middle_name?: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  email?: string;
  mobile?: string;
  phone?: string;
  nationality?: string;
  religion?: string;
  birth_place?: string;
  mother_tongue?: string;
  academic_year?: { id: string; name: string };
  course_applied?: { id: string; course_name: string };
  address_line1?: string;
  address_line2?: string;
  city?: string;
  country?: string;
  guardian1_first_name?: string;
  guardian1_last_name?: string;
  guardian1_relation?: string;
  guardian1_mobile?: string;
  guardian1_email?: string;
  guardian1_occupation?: string;
  guardian2_first_name?: string;
  guardian2_last_name?: string;
  guardian2_relation?: string;
  guardian2_mobile?: string;
  guardian2_email?: string;
  guardian2_occupation?: string;
  previous_school_name?: string;
  previous_school_address?: string;
  has_medical_problems?: boolean;
  recent_hospitalization?: boolean;
  has_allergies?: boolean;
  medical_details?: string;
  religious_observances?: string;
  background_information?: string;
  application_date: string;
  reviewed_at?: string;
  reviewed_by?: string;
  remarks?: string;
  admitted_student?: { id: string };
  [key: string]: any;
}

export function useAdmissionApplicationDetail(applicationId: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['admission-application-detail', applicationId],
    enabled: !!applicationId && options.enabled !== false,
    queryFn: async () =>
      await apiClient.get<ExtendedApplicationDetail>(`/admission-admin/${applicationId}/`),
  });
}

export function useAdmitStudent(applicationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      batch_id: string;
      admission_number?: string;
      admission_date?: string;
      remarks?: string;
    }) => await apiClient.post(`/admission-admin/${applicationId}/admit/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admission-application-detail', applicationId] });
      queryClient.invalidateQueries({ queryKey: ['applications-for-assignment'] });
      queryClient.invalidateQueries({ queryKey: ['admission-stats'] });
    },
  });
}

export function useDeleteApplication(applicationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => await apiClient.delete(`/admission-admin/${applicationId}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admission-application-detail', applicationId] });
      queryClient.invalidateQueries({ queryKey: ['applications-for-assignment'] });
      queryClient.invalidateQueries({ queryKey: ['admission-stats'] });
    },
  });
}

export function useDuplicateApplication(applicationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => await apiClient.post(`/admission-admin/${applicationId}/duplicate/`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications-for-assignment'] });
    },
  });
}

export function useAssignToClass(applicationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      batch_id: string;
      roll_number?: string;
      remarks?: string;
    }) => await apiClient.post(`/admission-admin/${applicationId}/assign_batch/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admission-application-detail', applicationId] });
      queryClient.invalidateQueries({ queryKey: ['applications-for-assignment'] });
    },
  });
}

export function useGenerateAdmissionNumber(batchId: string) {
  return useQuery({
    queryKey: ['generate-admission-number', batchId],
    enabled: !!batchId,
    queryFn: async () => {
      const response = await apiClient.get<{ admission_number: string; batch_id: string; batch_name: string }>(
        `/admission-admin/generate_admission_number/?batch_id=${batchId}`
      );
      return response;
    },
  });
}

export function useValidateAdmissionNumber() {
  return useMutation({
    mutationFn: async (admissionNumber: string) =>
      await apiClient.post<{ admission_number: string; is_unique: boolean; is_available: boolean }>(
        '/admission-admin/validate_admission_number/',
        { admission_number: admissionNumber }
      ),
  });
}

export function useActiveBatches(courseId?: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['active-batches', courseId],
    enabled: options.enabled !== false,
    queryFn: async () => {
      const url = courseId
        ? `/admission-admin/active_batches/?course_id=${courseId}`
        : '/admission-admin/active_batches/';
      const response = await apiClient.get<{ results: BatchOption[] }>(url);
      return response.results || [];
    },
  });
}

export function useExportApplicationPdf(applicationId: string) {
  return useMutation({
    mutationFn: async () => await apiClient.get(`/admission-admin/${applicationId}/export_pdf/`),
  });
}

// Report Hooks
export interface AdmissionReportData {
  statistics: {
    total_applications: number;
    approved_applications: number;
    admitted_applications: number;
    pending_review: number;
    [key: string]: number;
  };
  approval_rate: number;
  status_breakdown: Array<{ label: string; count: number; percentage: number }>;
  course_breakdown: Array<{ course: string; count: number }>;
  academic_years: Array<{ id: string; name: string }>;
}

export function useAdmissionReport(filters: {
  status?: string;
  academic_year?: string;
  date_from?: string;
  date_to?: string;
} = {}) {
  return useQuery({
    queryKey: ['admission-report', filters],
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (filters.status) qs.append('status', filters.status);
      if (filters.academic_year) qs.append('academic_year', filters.academic_year);
      if (filters.date_from) qs.append('date_from', filters.date_from);
      if (filters.date_to) qs.append('date_to', filters.date_to);
      return await apiClient.get<AdmissionReportData>(
        `/admission-reports/summary/${qs.toString() ? '?' + qs.toString() : ''}`
      );
    },
  });
}

// Batch Assignment Detail Hook
export interface BatchAssignmentDetail extends ApplicantForAssignment {
  documents?: any[];
  available_batches?: BatchOption[];
}

export function useBatchAssignmentDetail(applicationId: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['batch-assignment-detail', applicationId],
    enabled: !!applicationId && options.enabled !== false,
    queryFn: async () =>
      await apiClient.get<BatchAssignmentDetail>(
        `/admission-batch-assignment/application_detail/?application_id=${applicationId}`
      ),
  });
}

// Status Check Hook
export interface AdmissionStatusResult {
  application_number: string;
  status: string;
  status_display: string;
  applicant_name: string;
  application_date: string;
  remarks?: string;
}

export function useAdmissionStatusCheck(applicationNumber: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['admission-status-check', applicationNumber],
    enabled: !!applicationNumber && options.enabled !== false,
    queryFn: async () =>
      await apiClient.get<AdmissionStatusResult>(
        `/public/admission/status/${applicationNumber}/`
      ),
  });
}

// Diagnostics Data Initialization Hooks
export function useInitializeBasicData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => await apiClient.post('/admission-diagnostics/initialize_data/', {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admission-diagnostics'] });
    },
  });
}

export function useEnsureBasicData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => await apiClient.post('/admission-diagnostics/ensure_basic_data/', {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admission-diagnostics'] });
    },
  });
}
