/**
 * React Query hooks for Students CRUD.
 *
 * Handles:
 * - Fetching student list (with pagination, filtering, sorting)
 * - Fetching individual student
 * - Creating new student
 * - Updating student
 * - Deleting student
 *
 * NOTE on shapes: the backend uses three different serializers depending on
 * action (see core/serializers/student_serializers.py):
 * - List  -> StudentListSerializer: a small, read-only subset of fields.
 * - Retrieve -> StudentDetailSerializer: (almost) every model field plus
 *   computed relations (guardians, batches, etc).
 * - Create/Update -> StudentSerializer: a specific writable field set.
 * These do not match each other, so we model them as distinct types instead
 * of one `Student` interface.
 *
 * NOTE on batches: Student has no direct batch/course FK - it's a M2M via
 * the BatchStudent join model. There is currently no write path on this
 * ViewSet to assign a student to a batch at create/update time (the only
 * related actions are BatchViewSet.students (read-only) and
 * BatchViewSet.transfer_student, which transfers a student already assigned
 * to a batch - not an initial assignment). Batch assignment is therefore
 * intentionally NOT exposed on the Student create/edit form; batch_name is
 * shown read-only where available.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export type StudentGender = 'male' | 'female' | 'other';

/**
 * Row shape returned by `GET /students/` (StudentListSerializer).
 */
export interface StudentListItem {
  id: string;
  admission_no: string;
  full_name: string;
  gender: StudentGender;
  age: number | null;
  batch_name: string | null;
  is_active: boolean;
  has_paid_fees: boolean;
}

/**
 * A guardian entry as returned by StudentDetailSerializer.guardians.
 */
export interface StudentGuardianSummary {
  id: string;
  name: string;
  relationship: string;
  phone: string | null;
  email: string | null;
  is_immediate_contact: boolean;
}

/**
 * A batch enrollment entry as returned by StudentDetailSerializer.batches.
 */
export interface StudentBatchSummary {
  id: string;
  name: string;
  roll_number: string | null;
  is_active: boolean;
  enrollment_date: string;
}

/**
 * Full shape returned by `GET /students/{id}/` (StudentDetailSerializer,
 * fields = '__all__' plus computed fields).
 */
export interface StudentDetail {
  id: string;
  admission_no: string;
  class_roll_no: string | null;
  admission_date: string;
  first_name: string;
  middle_name: string | null;
  last_name: string;
  full_name: string;
  date_of_birth: string;
  gender: StudentGender;
  age: number | null;
  blood_group: string | null;
  birth_place: string | null;
  nationality: string | null;
  nationality_name: string | null;
  language: string | null;
  religion: string | null;
  student_category: string | null;
  category_name: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  pin_code: string | null;
  country: string | null;
  country_name: string | null;
  phone1: string | null;
  phone2: string | null;
  email: string | null;
  is_sms_enabled: boolean;
  status_description: string | null;
  is_active: boolean;
  is_deleted: boolean;
  has_paid_fees: boolean;
  guardians: StudentGuardianSummary[];
  batches: StudentBatchSummary[];
  created_at: string;
  updated_at: string;
}

export interface StudentListParams {
  page?: number;
  page_size?: number;
  search?: string;
  is_active?: boolean;
  ordering?: string;
}

export interface StudentListResponse {
  count: number;
  next?: string;
  previous?: string;
  results: StudentListItem[];
}

/**
 * Writable fields accepted by StudentSerializer on create.
 * Required per extra_kwargs / non-nullable model fields: admission_no,
 * first_name, last_name, date_of_birth, gender, admission_date.
 */
export interface CreateStudentInput {
  admission_no: string;
  first_name: string;
  middle_name?: string;
  last_name: string;
  date_of_birth: string;
  gender: StudentGender;
  admission_date: string;
  blood_group?: string;
  nationality?: string;
  language?: string;
  religion?: string;
  student_category?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  pin_code?: string;
  country?: string;
  phone1?: string;
  phone2?: string;
  email?: string;
  is_sms_enabled?: boolean;
  is_active?: boolean;
  status_description?: string;
}

/**
 * Writable fields accepted by StudentSerializer on update (all optional -
 * PATCH semantics).
 */
export type UpdateStudentInput = Partial<CreateStudentInput>;

/**
 * Fetch paginated list of students.
 */
export function useStudentList(params: StudentListParams = {}, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['students', params],
    enabled: options.enabled,
    queryFn: async () => {
      const queryString = new URLSearchParams();
      if (params.page) queryString.append('page', params.page.toString());
      if (params.page_size) queryString.append('page_size', params.page_size.toString());
      if (params.search) queryString.append('search', params.search);
      if (params.is_active !== undefined) queryString.append('is_active', params.is_active.toString());
      if (params.ordering) queryString.append('ordering', params.ordering);

      const path = `/students/${queryString.toString() ? '?' + queryString.toString() : ''}`;
      return await apiClient.get<StudentListResponse>(path);
    },
  });
}

/**
 * Fetch single student by ID (full detail shape).
 */
export function useStudent(id: string) {
  return useQuery({
    queryKey: ['students', id],
    queryFn: async () => {
      return await apiClient.get<StudentDetail>(`/students/${id}/`);
    },
    enabled: !!id,
  });
}

/**
 * Create new student.
 */
export function useCreateStudent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateStudentInput) => {
      return await apiClient.post<StudentDetail>('/students/', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['students'] });
    },
  });
}

/**
 * Update existing student.
 */
export function useUpdateStudent(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: UpdateStudentInput) => {
      return await apiClient.patch<StudentDetail>(`/students/${id}/`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['students'] });
      queryClient.invalidateQueries({ queryKey: ['students', id] });
    },
  });
}

/**
 * Delete student. Call `.mutate(id)` / `.mutateAsync(id)` with the target id —
 * this hook itself must be called once at component top level (Rules of Hooks).
 */
export function useDeleteStudent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return await apiClient.delete(`/students/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['students'] });
    },
  });
}

/**
 * Fee balance response shape
 */
export interface FeeBalanceResponse {
  student_id: string;
  balance: number;
  currency?: string;
  as_of_date?: string;
}

/**
 * Get student fee balance
 */
export function useStudentFeeBalance(studentId: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['students', studentId, 'fee-balance'],
    queryFn: async () => {
      return await apiClient.get<FeeBalanceResponse>(`/students/${studentId}/fee-balance/`);
    },
    enabled: !!studentId && options.enabled !== false,
  });
}

/**
 * Term summary in attendance response
 */
export interface TermSummary {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
}

/**
 * Attendance summary response shape
 */
export interface AttendanceSummaryResponse {
  student_id: string;
  total_days: number;
  present_days: number;
  absent_days: number;
  attendance_percentage: number;
  available_terms?: TermSummary[];
  current_term_id?: string;
}

/**
 * Get student attendance summary
 */
export function useStudentAttendanceSummary(studentId: string, termId?: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['students', studentId, 'attendance-summary', termId],
    queryFn: async () => {
      const path = termId
        ? `/students/${studentId}/attendance-summary/?term_id=${termId}`
        : `/students/${studentId}/attendance-summary/`;
      return await apiClient.get<AttendanceSummaryResponse>(path);
    },
    enabled: !!studentId && options.enabled !== false,
  });
}

/**
 * Student document shape
 */
export interface StudentDocument {
  id: string;
  category: string;
  category_name: string;
  original_filename: string;
  note: string;
  uploaded_by_id: string | null;
  uploaded_at: string;
  file_url: string | null;
  file_size_mb: number | null;
}

/**
 * Documents list response
 */
export interface DocumentsResponse {
  results: StudentDocument[];
  count: number;
}

/**
 * Get student documents
 */
export function useStudentDocuments(studentId: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['students', studentId, 'documents'],
    queryFn: async () => {
      return await apiClient.get<DocumentsResponse>(`/students/${studentId}/documents/`);
    },
    enabled: !!studentId && options.enabled !== false,
  });
}

/**
 * Upload a student document
 */
export function useUploadDocument(studentId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { categoryId: string; file: File; note?: string }) => {
      const formData = new FormData();
      formData.append('category_id', data.categoryId);
      formData.append('file', data.file);
      if (data.note) formData.append('note', data.note);

      return await apiClient.post<StudentDocument>(
        `/students/${studentId}/upload-document/`,
        formData,
        {
          headers: { 'Content-Type': 'multipart/form-data' },
        }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['students', studentId, 'documents'] });
    },
  });
}

/**
 * Delete a student document
 */
export function useDeleteDocument(studentId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (docId: string) => {
      return await apiClient.delete(`/students/${studentId}/delete-document/?doc_id=${docId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['students', studentId, 'documents'] });
    },
  });
}

/**
 * Guardian summary shape
 */
export interface GuardianSummary {
  id: string;
  name: string;
  relation: string;
  phone: string | null;
  email: string | null;
  is_immediate_contact: boolean;
}

/**
 * Guardians list response
 */
export interface GuardiansResponse {
  results: GuardianSummary[];
  count: number;
}

/**
 * Get student guardians
 */
export function useStudentGuardians(studentId: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['students', studentId, 'guardians'],
    queryFn: async () => {
      return await apiClient.get<GuardiansResponse>(`/students/${studentId}/guardians/`);
    },
    enabled: !!studentId && options.enabled !== false,
  });
}

/**
 * Attach guardian request shape
 */
export interface AttachGuardianInput {
  guardian_id?: string;
  first_name?: string;
  last_name?: string;
  mobile_phone?: string;
  office_phone?: string;
  email?: string;
  occupation?: string;
  relation: string;
  is_immediate_contact?: boolean;
}

/**
 * Attach guardian response
 */
export interface AttachGuardianResponse {
  success: boolean;
  message: string;
  guardian_id?: string;
  credentials_sent?: boolean;
}

/**
 * Attach a guardian to student
 */
export function useAttachGuardian(studentId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: AttachGuardianInput) => {
      return await apiClient.post<AttachGuardianResponse>(
        `/students/${studentId}/guardians/`,
        data
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['students', studentId, 'guardians'] });
    },
  });
}

/**
 * Generate a student report
 */
export function useGenerateReport(studentId: string, reportType: 'academic' | 'attendance' | 'fees' | 'profile') {
  return useMutation({
    mutationFn: async () => {
      return await apiClient.get(`/students/${studentId}/generate-report/?type=${reportType}`);
    },
  });
}
