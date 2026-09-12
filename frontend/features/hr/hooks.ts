import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface Employee {
  id: string;
  employee_number: string;
  first_name: string;
  middle_name?: string | null;
  last_name: string;
  full_name: string;
  email?: string | null;
  mobile_phone?: string | null;
  gender?: boolean | null;
  gender_display?: 'M' | 'F' | null;
  job_title?: string | null;
  is_teaching_staff: boolean;
  employee_category?: string | null;
  category_name?: string | null;
  employee_position?: string | null;
  position_name?: string | null;
  employee_department?: string | null;
  department_name?: string | null;
  reporting_manager?: string | null;
  employee_grade?: string | null;
  joining_date: string;
  date_of_birth?: string | null;
  national_id?: string | null;
  status: boolean;
  employment_status: 'active' | 'probation' | 'on_leave' | 'suspended' | 'notice_period' | 'exited';
  created_at: string;
  updated_at: string;
}

export interface LeaveRequest {
  id: string;
  employee: string;
  employee_name: string;
  leave_type: string | null;
  leave_type_name: string | null;
  start_date: string;
  end_date: string;
  reason: string;
  status: 'pending' | 'approved' | 'rejected';
  is_approved: boolean;
  approved_by: string | null;
  manager_remark: string | null;
  supervisor_status: 'pending' | 'approved' | 'rejected';
  supervisor_remark: string | null;
  hr_status: 'pending' | 'approved' | 'rejected';
  hr_remark: string | null;
  created_at: string;
  updated_at: string;
}

export interface AttendanceRecord {
  id: string;
  employee: string;
  employee_name?: string;
  date: string;
  status: 'present' | 'absent' | 'late' | 'on_leave' | 'half_day' | 'official_duty' | 'training' | 'holiday';
  marked_by?: string | null;
  remarks?: string | null;
  clock_in?: string | null;
  clock_out?: string | null;
  hours_worked?: string | null;
  late_minutes?: number;
  created_at: string;
  updated_at: string;
}

export interface EmployeeListParams {
  page?: number;
  page_size?: number;
  search?: string;
  employee_department?: string;
  ordering?: string;
}

export interface CreateEmployeeInput {
  employee_number: string;
  first_name: string;
  last_name: string;
  middle_name?: string;
  email?: string;
  mobile_phone?: string;
  employee_department?: string;
  employee_position?: string;
  joining_date: string;
  gender?: boolean;
}

export interface UpdateEmployeeInput {
  first_name?: string;
  last_name?: string;
  middle_name?: string;
  email?: string;
  mobile_phone?: string;
  employee_department?: string;
  employee_position?: string;
  status?: boolean;
  employment_status?: Employee['employment_status'];
}

export interface ListResponse<T> {
  count: number;
  next?: string;
  previous?: string;
  results: T[];
}

// Employees
export function useEmployeeList(params: EmployeeListParams = {}, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['employees', params],
    enabled: options.enabled,
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (params.page) qs.append('page', params.page.toString());
      if (params.page_size) qs.append('page_size', params.page_size.toString());
      if (params.search) qs.append('search', params.search);
      if (params.employee_department) qs.append('employee_department', params.employee_department);
      if (params.ordering) qs.append('ordering', params.ordering);
      return await apiClient.get<ListResponse<Employee>>(`/employees/${qs.toString() ? '?' + qs.toString() : ''}`);
    },
  });
}

export function useEmployee(id: string) {
  return useQuery({
    queryKey: ['employees', id],
    queryFn: async () => await apiClient.get<Employee>(`/employees/${id}/`),
    enabled: !!id,
  });
}

export function useCreateEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateEmployeeInput) => await apiClient.post<Employee>('/employees/', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['employees'] }),
  });
}

export function useUpdateEmployee(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: UpdateEmployeeInput) => await apiClient.patch<Employee>(`/employees/${id}/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      queryClient.invalidateQueries({ queryKey: ['employees', id] });
    },
  });
}

/**
 * Delete employee. Call `.mutate(id)` / `.mutateAsync(id)` with the target id —
 * this hook itself must be called once at component top level (Rules of Hooks).
 */
export function useDeleteEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => await apiClient.delete(`/employees/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['employees'] }),
  });
}

// Leave Requests
export function useLeaveRequestList(params: EmployeeListParams = {}) {
  return useQuery({
    queryKey: ['leave-requests', params],
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (params.page) qs.append('page', params.page.toString());
      if (params.page_size) qs.append('page_size', params.page_size.toString());
      if (params.search) qs.append('search', params.search);
      if (params.ordering) qs.append('ordering', params.ordering);
      return await apiClient.get<ListResponse<LeaveRequest>>(`/leave-requests/${qs.toString() ? '?' + qs.toString() : ''}`);
    },
  });
}

export function useLeaveRequest(id: string) {
  return useQuery({
    queryKey: ['leave-requests', id],
    queryFn: async () => await apiClient.get<LeaveRequest>(`/leave-requests/${id}/`),
    enabled: !!id,
  });
}

export function useCreateLeaveRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: any) => await apiClient.post<LeaveRequest>('/leave-requests/', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['leave-requests'] }),
  });
}

// Attendance
export function useAttendanceList(params: EmployeeListParams = {}) {
  return useQuery({
    queryKey: ['attendance', params],
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (params.page) qs.append('page', params.page.toString());
      if (params.page_size) qs.append('page_size', params.page_size.toString());
      if (params.search) qs.append('search', params.search);
      if (params.ordering) qs.append('ordering', params.ordering);
      return await apiClient.get<ListResponse<AttendanceRecord>>(`/attendance/${qs.toString() ? '?' + qs.toString() : ''}`);
    },
  });
}

export function useCreateAttendance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: any) => await apiClient.post<AttendanceRecord>('/attendance/', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['attendance'] }),
  });
}
