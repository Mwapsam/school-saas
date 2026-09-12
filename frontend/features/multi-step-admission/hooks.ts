import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface ExtendedAdmissionApplication {
  id: string;
  application_number: string;
  academic_year?: { id: string; name: string; start_date: string; end_date: string; is_active: boolean } | null;
  course_applied?: { id: string; course_name: string; code: string } | null;
  current_step: number;
  status: string;
  terms_agreement: boolean;
  preferred_start_date?: string | null;

  first_name: string;
  middle_name?: string | null;
  last_name: string;
  date_of_birth?: string | null;
  gender?: 'male' | 'female' | 'other' | null;
  nationality?: string | null;
  student_photo?: string | null;
  student_category?: { id: string; name: string } | null;
  religion?: string | null;
  birth_place?: string | null;
  mother_tongue?: string | null;
  preferred_name?: string | null;
  home_language?: string | null;
  authorized_pickup_persons?: string | null;

  address?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  country?: { id: string; name: string; code: string } | null;
  phone?: string | null;
  mobile?: string | null;
  email?: string | null;

  guardian1_first_name?: string | null;
  guardian1_last_name?: string | null;
  guardian1_relation?: string | null;
  guardian1_occupation?: string | null;
  guardian1_office_address_line1?: string | null;
  guardian1_office_city?: string | null;
  guardian1_office_phone1?: string | null;
  guardian1_mobile?: string | null;
  guardian1_email?: string | null;
  guardian1_house_plot_no?: string | null;
  guardian1_road_name?: string | null;
  guardian1_area_location?: string | null;
  guardian1_flat_block_name?: string | null;

  guardian2_first_name?: string | null;
  guardian2_last_name?: string | null;
  guardian2_relation?: string | null;
  guardian2_occupation?: string | null;
  guardian2_office_address_line1?: string | null;
  guardian2_office_city?: string | null;
  guardian2_office_phone1?: string | null;
  guardian2_mobile?: string | null;
  guardian2_email?: string | null;
  guardian2_house_plot_no?: string | null;
  guardian2_road_name?: string | null;
  guardian2_area_location?: string | null;
  guardian2_flat_block_name?: string | null;

  emergency_contact_name?: string | null;
  emergency_contact_relation?: string | null;
  emergency_contact_mobile?: string | null;
  emergency_contact_address?: string | null;

  previous_school_name?: string | null;
  previous_school_address?: string | null;
  previous_school_phone?: string | null;
  previous_school_email?: string | null;
  expected_start_date?: string | null;
  has_medical_problems?: boolean | null;
  recent_hospitalization?: boolean | null;
  has_allergies?: boolean | null;
  medical_details?: string | null;
  religious_observances?: string | null;
  background_information?: string | null;
  declaration_agreement: boolean;
  declaration_date?: string | null;
  declaration_signature_name?: string | null;
  fee_acknowledgment: boolean;

  remarks?: string | null;
  application_date: string;
  reviewed_by?: { id: string; first_name: string; last_name: string; email: string } | null;
  reviewed_at?: string | null;
  admitted_student?: { id: string; name: string } | null;

  full_name?: string;
  is_step1_complete: boolean;
  is_step2_complete: boolean;
  is_step3_complete: boolean;
  is_step4_complete: boolean;
  is_step5_complete: boolean;
  is_step6_complete: boolean;
  is_step7_complete: boolean;
  is_complete: boolean;
  can_submit: boolean;
  next_step?: number | null;

  created_at: string;
  updated_at: string;
}

export interface AdmissionDocument {
  id: string;
  application_id: string;
  document_type: string;
  document_type_display: string;
  file: string;
  original_filename: string;
  file_size: number;
  file_size_mb: number;
  uploaded_at: string;
  is_verified: boolean;
  is_required: boolean;
  verification_notes?: string;
}

export interface AdmissionProgress {
  current_step: number;
  status: string;
  step1_complete: boolean;
  step2_complete: boolean;
  step3_complete: boolean;
  step4_complete: boolean;
  step5_complete: boolean;
  step6_complete: boolean;
  step7_complete: boolean;
  is_complete: boolean;
  can_submit: boolean;
  next_step?: number | null;
  documents_uploaded: number;
  required_documents_uploaded: number;
}

export interface AcademicYearOption {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
  admission_start_date?: string;
  admission_end_date?: string;
}

export interface CourseOption {
  id: string;
  course_name: string;
  code: string;
  section_name?: string;
}

export interface CountryOption {
  id: string;
  name: string;
  code: string;
}

export interface StudentCategoryOption {
  id: string;
  name: string;
}

export interface AdmissionTermsOption {
  id: string;
  title: string;
  terms_content: string;
  admission_fee?: number;
  fee_currency?: string;
  order: number;
}

export interface AdditionalFieldOption {
  id: string;
  name: string;
  input_type: string;
  is_mandatory: boolean;
  options: string[];
}

export interface ListResponse<T> {
  count: number;
  results: T[];
  next?: string | null;
  previous?: string | null;
}

export function useStartApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      await apiClient.post<ExtendedAdmissionApplication>('/admission-multistep/start_application/', {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['multi-step-applications'] });
    },
  });
}

export function useGetApplication(id: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['multi-step-application', id],
    enabled: options.enabled !== false && !!id,
    queryFn: async () =>
      await apiClient.get<ExtendedAdmissionApplication>(`/admission-multistep/${id}/`),
  });
}

export function useUpdateApplicationStep(id: string, step: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: any) =>
      await apiClient.post<ExtendedAdmissionApplication>(
        `/admission-multistep/${id}/step${step}/`,
        data
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['multi-step-application', id] });
      queryClient.invalidateQueries({ queryKey: ['multi-step-applications'] });
    },
  });
}

export function useGetProgress(id: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['multi-step-progress', id],
    enabled: options.enabled !== false && !!id,
    queryFn: async () =>
      await apiClient.get<AdmissionProgress>(`/admission-multistep/${id}/progress/`),
  });
}

export function useSubmitApplication(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { confirm_submission: boolean }) =>
      await apiClient.post<ExtendedAdmissionApplication>(
        `/admission-multistep/${id}/submit/`,
        data
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['multi-step-application', id] });
      queryClient.invalidateQueries({ queryKey: ['multi-step-applications'] });
    },
  });
}

export function useUploadDocument(applicationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: FormData) => {
      data.append('application_id', applicationId);
      return await apiClient.post<AdmissionDocument>('/admission-documents/', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['multi-step-application', applicationId] });
      queryClient.invalidateQueries({ queryKey: ['admission-documents'] });
    },
  });
}

export function useGetDocuments(applicationId: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['admission-documents', applicationId],
    enabled: options.enabled !== false && !!applicationId,
    queryFn: async () => {
      const qs = new URLSearchParams({ application_id: applicationId });
      return await apiClient.get<ListResponse<AdmissionDocument>>(
        `/admission-documents/?${qs.toString()}`
      );
    },
  });
}

export function useGetRequiredDocuments() {
  return useQuery({
    queryKey: ['required-documents'],
    queryFn: async () =>
      await apiClient.get<Array<{ type: string; display_name: string; required: boolean }>>(
        '/admission-documents/required_documents/'
      ),
  });
}

export function useGetAcademicYears() {
  return useQuery({
    queryKey: ['academic-years'],
    queryFn: async () => {
      const response = await apiClient.get<AcademicYearOption[]>('/admission-lookups/academic_years/');
      return Array.isArray(response) ? response : response.results || [];
    },
  });
}

export function useGetCourses() {
  return useQuery({
    queryKey: ['courses'],
    queryFn: async () => {
      const response = await apiClient.get<CourseOption[]>('/admission-lookups/courses/');
      return Array.isArray(response) ? response : response.results || [];
    },
  });
}

export function useGetCountries() {
  return useQuery({
    queryKey: ['countries'],
    queryFn: async () => {
      const response = await apiClient.get<CountryOption[]>('/admission-lookups/countries/');
      return Array.isArray(response) ? response : response.results || [];
    },
  });
}

export function useGetStudentCategories() {
  return useQuery({
    queryKey: ['student-categories'],
    queryFn: async () => {
      const response = await apiClient.get<StudentCategoryOption[]>('/admission-lookups/student_categories/');
      return Array.isArray(response) ? response : response.results || [];
    },
  });
}

export function useGetAdmissionTerms() {
  return useQuery({
    queryKey: ['admission-terms'],
    queryFn: async () => {
      const response = await apiClient.get<AdmissionTermsOption[]>('/admission-lookups/terms/');
      return Array.isArray(response) ? response : response.results || [];
    },
  });
}

export function useGetAdditionalFields() {
  return useQuery({
    queryKey: ['admission-additional-fields'],
    queryFn: async () => {
      const response = await apiClient.get<AdditionalFieldOption[]>('/admission-lookups/additional_fields/');
      return Array.isArray(response) ? response : response.results || [];
    },
  });
}
