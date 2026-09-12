import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface TransportRoute {
  id: string;
  name: string;
  code: string;
  route_type: 'morning' | 'afternoon' | 'custom';
  vehicle_name: string;
  student_count: number;
  created_at: string;
}

export interface ListResponse<T> {
  count: number;
  results: T[];
}

export function useTransportRoute(id: string) {
  return useQuery({
    queryKey: ['routes', id],
    queryFn: async () => {
      return await apiClient.get<TransportRoute>(`/routes/${id}/`);
    },
    enabled: !!id,
  });
}

export function useTransportRouteList(params: any = {}, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['routes', params],
    enabled: options.enabled,
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (params.page) qs.append('page', params.page.toString());
      if (params.page_size) qs.append('page_size', params.page_size.toString());
      if (params.search) qs.append('search', params.search);
      return await apiClient.get<ListResponse<TransportRoute>>(`/routes/${qs.toString() ? '?' + qs.toString() : ''}`);
    },
  });
}
