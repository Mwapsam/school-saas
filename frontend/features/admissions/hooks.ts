import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface AdmissionApplication {
  id: string;
  application_number: string;
  first_name: string;
  middle_name?: string | null;
  last_name: string;
  date_of_birth: string;
  gender: 'male' | 'female' | 'other';
  course_applied: string;
  course_name: string;
  guardian_name: string;
  guardian_phone: string;
  guardian_email?: string | null;
  address: string;
  application_date: string;
  status: string;
  remarks?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ListResponse<T> {
  count: number;
  results: T[];
}

export interface CreateAdmissionApplicationInput {
  first_name: string;
  middle_name?: string;
  last_name: string;
  date_of_birth: string;
  gender: 'male' | 'female' | 'other';
  course_applied: string;
  guardian_name: string;
  guardian_phone: string;
  guardian_email?: string;
  address: string;
  remarks?: string;
}

export interface CourseOption {
  id: string;
  course_name: string;
}

export function useCourseOptions() {
  return useQuery({
    queryKey: ['admissions-course-options'],
    queryFn: async () => {
      return await apiClient.get<{ results: CourseOption[] }>('/courses/?page_size=200');
    },
  });
}

export function useAdmissionApplicationList(params: any = {}, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['admissions', params],
    enabled: options.enabled,
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (params.page) qs.append('page', params.page.toString());
      if (params.page_size) qs.append('page_size', params.page_size.toString());
      if (params.search) qs.append('search', params.search);
      return await apiClient.get<ListResponse<AdmissionApplication>>(`/admission-applications/${qs.toString() ? '?' + qs.toString() : ''}`);
    },
  });
}

export function useCreateAdmissionApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateAdmissionApplicationInput) =>
      await apiClient.post<AdmissionApplication>('/admission-applications/', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admissions'] }),
  });
}
