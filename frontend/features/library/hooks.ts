import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface LibraryBook {
  id: string;
  title: string;
  author: string;
  isbn: string;
  category_name: string;
  total_copies: number;
  available_copies: number;
  created_at: string;
}

export interface ListResponse<T> {
  count: number;
  results: T[];
}

export function useLibraryBookList(params: any = {}) {
  return useQuery({
    queryKey: ['library-books', params],
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (params.page) qs.append('page', params.page.toString());
      if (params.page_size) qs.append('page_size', params.page_size.toString());
      if (params.search) qs.append('search', params.search);
      return await apiClient.get<ListResponse<LibraryBook>>(`/library-books/${qs.toString() ? '?' + qs.toString() : ''}`);
    },
  });
}
