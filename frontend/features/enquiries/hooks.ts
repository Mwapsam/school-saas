import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface ApplicantEnquiry {
  id: string;
  enquiry_number: string;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  email?: string | null;
  phone?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  guardian_first_name?: string | null;
  guardian_last_name?: string | null;
  guardian_relation?: string | null;
  guardian_email?: string | null;
  guardian_phone?: string | null;
  guardian_address_line1?: string | null;
  guardian_address_line2?: string | null;
  guardian_occupation?: string | null;
  guardian_income?: string | null;
  guardian_education?: string | null;
  enquired_date: string;
  course: { id: string; name: string; code: string } | null;
  course_name?: string | null;
  academic_year: { id: string; name: string; start_date: string; end_date: string } | null;
  academic_year_name?: string | null;
  stage: { id: string; name: string; is_default: boolean; priority: number; color: string } | null;
  stage_name?: string | null;
  stage_color?: string | null;
  counselor: { id: string; first_name: string; last_name: string; email: string; full_name: string } | null;
  counselor_name?: string | null;
  source_of_info?: string | null;
  is_processed: boolean;
  is_rejected: boolean;
  is_viewed: boolean;
  is_email_enabled: boolean;
  remarks?: string | null;
  additional_data?: Record<string, any>;
  stage_logs?: EnquiryStageLog[];
  follow_ups?: EnquiryFollowUp[];
  created_at: string;
  updated_at: string;
}

export interface EnquiryStageLog {
  id: string;
  enquiry: string;
  stage: { id: string; name: string; is_default: boolean; priority: number; color: string };
  stage_name: string;
  changed_by?: { id: string; first_name: string; last_name: string; email: string; full_name: string } | null;
  changed_by_name?: string | null;
  notes?: EnquiryStageLogNote[];
  created_at: string;
  updated_at: string;
}

export interface EnquiryStageLogNote {
  id: string;
  stage_log: string;
  notes: string;
  follow_up_date?: string | null;
  created_by?: { id: string; first_name: string; last_name: string; email: string; full_name: string } | null;
  created_by_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EnquiryFollowUp {
  id: string;
  enquiry: string;
  follow_up_type: 'call' | 'email' | 'meeting' | 'visit' | 'other';
  follow_up_type_display: string;
  scheduled_date: string;
  status: 'planned' | 'completed' | 'cancelled' | 'rescheduled';
  status_display: string;
  assigned_to?: { id: string; first_name: string; last_name: string; email: string; full_name: string } | null;
  assigned_to_name?: string | null;
  notes?: string | null;
  completion_notes?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ListResponse<T> {
  count: number;
  results: T[];
  next?: string | null;
  previous?: string | null;
}

export interface CreateEnquiryInput {
  first_name?: string;
  last_name?: string;
  date_of_birth?: string | null;
  email?: string | null;
  phone?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  guardian_first_name?: string | null;
  guardian_last_name?: string | null;
  guardian_relation?: string | null;
  guardian_email?: string | null;
  guardian_phone?: string | null;
  guardian_address_line1?: string | null;
  guardian_address_line2?: string | null;
  guardian_occupation?: string | null;
  guardian_income?: string | null;
  guardian_education?: string | null;
  enquired_date?: string;
  course?: string | null;
  academic_year?: string | null;
  counselor?: string | null;
  source_of_info?: string | null;
  remarks?: string | null;
  additional_data?: Record<string, any>;
}

export interface UpdateEnquiryInput extends Partial<CreateEnquiryInput> {
  stage?: string | null;
  is_processed?: boolean;
  is_rejected?: boolean;
  is_viewed?: boolean;
  is_email_enabled?: boolean;
}

export function useEnquiryList(params: any = {}, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['enquiries', params],
    enabled: options.enabled,
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (params.page) qs.append('page', params.page.toString());
      if (params.page_size) qs.append('page_size', params.page_size.toString());
      if (params.search) qs.append('search', params.search);
      if (params.stage) qs.append('stage', params.stage);
      return await apiClient.get<ListResponse<ApplicantEnquiry>>(
        `/enquiries/${qs.toString() ? '?' + qs.toString() : ''}`
      );
    },
  });
}

export function useEnquiry(id: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['enquiries', id],
    enabled: options.enabled !== false && !!id,
    queryFn: async () => {
      return await apiClient.get<ApplicantEnquiry>(`/enquiries/${id}/`);
    },
  });
}

export function useCreateEnquiry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateEnquiryInput) =>
      await apiClient.post<ApplicantEnquiry>('/enquiries/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['enquiries'] });
    },
  });
}

export function useUpdateEnquiry(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: UpdateEnquiryInput) =>
      await apiClient.patch<ApplicantEnquiry>(`/enquiries/${id}/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['enquiries'] });
      queryClient.invalidateQueries({ queryKey: ['enquiries', id] });
    },
  });
}

export function useConvertToApplication(enquiryId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      await apiClient.post(`/enquiries/${enquiryId}/convert-to-application/`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['enquiries'] });
      queryClient.invalidateQueries({ queryKey: ['enquiries', enquiryId] });
    },
  });
}
