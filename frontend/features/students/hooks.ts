/**
 * React Query hooks for Students CRUD.
 *
 * Handles:
 * - Fetching student list (with pagination, filtering, sorting)
 * - Fetching individual student
 * - Creating new student
 * - Updating student
 * - Deleting student
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface Student {
  id: string;
  admission_number: string;
  full_name: string;
  date_of_birth: string;
  gender: 'M' | 'F' | 'O';
  email?: string;
  phone?: string;
  batch_id?: string;
  batch_name?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface StudentListParams {
  page?: number;
  page_size?: number;
  search?: string;
  batch?: string;
  is_active?: boolean;
  ordering?: string;
}

export interface StudentListResponse {
  count: number;
  next?: string;
  previous?: string;
  results: Student[];
}

export interface CreateStudentInput {
  admission_number: string;
  full_name: string;
  date_of_birth: string;
  gender: 'M' | 'F' | 'O';
  email?: string;
  phone?: string;
  batch_id?: string;
}

export interface UpdateStudentInput {
  full_name?: string;
  email?: string;
  phone?: string;
  batch_id?: string;
  is_active?: boolean;
}

/**
 * Fetch paginated list of students.
 */
export function useStudentList(params: StudentListParams = {}) {
  return useQuery({
    queryKey: ['students', params],
    queryFn: async () => {
      const queryString = new URLSearchParams();
      if (params.page) queryString.append('page', params.page.toString());
      if (params.page_size) queryString.append('page_size', params.page_size.toString());
      if (params.search) queryString.append('search', params.search);
      if (params.batch) queryString.append('batch', params.batch);
      if (params.is_active !== undefined) queryString.append('is_active', params.is_active.toString());
      if (params.ordering) queryString.append('ordering', params.ordering);

      const path = `/students/${queryString.toString() ? '?' + queryString.toString() : ''}`;
      return await apiClient.get<StudentListResponse>(path);
    },
  });
}

/**
 * Fetch single student by ID.
 */
export function useStudent(id: string) {
  return useQuery({
    queryKey: ['students', id],
    queryFn: async () => {
      return await apiClient.get<Student>(`/students/${id}/`);
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
      return await apiClient.post<Student>('/students/', data);
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
      return await apiClient.patch<Student>(`/students/${id}/`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['students'] });
      queryClient.invalidateQueries({ queryKey: ['students', id] });
    },
  });
}

/**
 * Delete student.
 */
export function useDeleteStudent(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      return await apiClient.delete(`/students/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['students'] });
    },
  });
}
