import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface HostelRoom {
  id: string;
  hostel_name: string;
  room_number: string;
  capacity: number;
  current_occupancy: number;
  created_at: string;
}

export interface ListResponse<T> {
  count: number;
  results: T[];
}

export function useHostelRoom(id: string) {
  return useQuery({
    queryKey: ['hostel-rooms', id],
    queryFn: async () => {
      return await apiClient.get<HostelRoom>(`/hostel-rooms/${id}/`);
    },
    enabled: !!id,
  });
}

export function useHostelRoomList(params: any = {}, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['hostel-rooms', params],
    enabled: options.enabled,
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (params.page) qs.append('page', params.page.toString());
      if (params.page_size) qs.append('page_size', params.page_size.toString());
      if (params.search) qs.append('search', params.search);
      return await apiClient.get<ListResponse<HostelRoom>>(`/hostel-rooms/${qs.toString() ? '?' + qs.toString() : ''}`);
    },
  });
}
