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
