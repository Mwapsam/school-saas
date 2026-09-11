import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface AdmissionApplication {
  id: string;
  application_number: string;
  student_name: string;
  email: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  updated_at: string;
}

export interface ListResponse<T> {
  count: number;
  results: T[];
}

export function useAdmissionApplicationList(params: any = {}) {
  return useQuery({
    queryKey: ['admissions', params],
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
    mutationFn: async (data: any) => await apiClient.post('/admission-applications/', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admissions'] }),
  });
}
