import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface Employee {
  id: string;
  employee_id: string;
  full_name: string;
  email: string;
  phone?: string;
  department?: string;
  position?: string;
  hire_date: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LeaveRequest {
  id: string;
  employee_id: string;
  employee_name: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  updated_at: string;
}

export interface AttendanceRecord {
  id: string;
  employee_id: string;
  employee_name: string;
  date: string;
  status: 'present' | 'absent' | 'late';
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface EmployeeListParams {
  page?: number;
  page_size?: number;
  search?: string;
  department?: string;
  ordering?: string;
}

export interface ListResponse<T> {
  count: number;
  next?: string;
  previous?: string;
  results: T[];
}

// Employees
export function useEmployeeList(params: EmployeeListParams = {}) {
  return useQuery({
    queryKey: ['employees', params],
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (params.page) qs.append('page', params.page.toString());
      if (params.page_size) qs.append('page_size', params.page_size.toString());
      if (params.search) qs.append('search', params.search);
      if (params.department) qs.append('department', params.department);
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
    mutationFn: async (data: any) => await apiClient.post<Employee>('/employees/', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['employees'] }),
  });
}

export function useUpdateEmployee(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: any) => await apiClient.patch<Employee>(`/employees/${id}/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      queryClient.invalidateQueries({ queryKey: ['employees', id] });
    },
  });
}

export function useDeleteEmployee(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => await apiClient.delete(`/employees/${id}/`),
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
