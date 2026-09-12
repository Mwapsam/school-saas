/**
 * React Query hooks for Finance CRUD.
 *
 * Covers:
 * - Invoices (list, fetch, create, update, delete, mark_paid, send, pdf)
 * - Fees (student fees, balance queries)
 * - Transactions (record payments/refunds)
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

export interface Invoice {
  id: string;
  student_id: string;
  student_name: string;
  invoice_number: string;
  amount: number;
  due_date: string;
  status: 'draft' | 'sent' | 'paid' | 'overdue';
  is_paid: boolean;
  paid_date?: string;
  notes?: string;
  line_items?: InvoiceLineItem[];
  total_amount?: number;
  created_at: string;
  updated_at: string;
}

export interface InvoiceLineItem {
  id: string;
  description: string;
  amount: number;
  quantity?: number;
}

export interface StudentFee {
  id: string;
  student_id: string;
  student_name: string;
  total_fees: number;
  fees_paid: number;
  balance: number;
  fee_count: number;
  created_at: string;
  updated_at: string;
}

export interface Transaction {
  id: string;
  invoice_id?: string;
  amount: number;
  type: 'payment' | 'refund' | 'credit';
  date: string;
  reference: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface InvoiceListParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  student?: string;
  ordering?: string;
}

export interface InvoiceListResponse {
  count: number;
  next?: string;
  previous?: string;
  results: Invoice[];
}

export interface CreateInvoiceInput {
  student_id: string;
  invoice_number: string;
  amount: number;
  due_date: string;
  notes?: string;
}

export interface UpdateInvoiceInput {
  amount?: number;
  due_date?: string;
  status?: string;
  notes?: string;
}

// Invoices
export function useInvoiceList(params: InvoiceListParams = {}, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['invoices', params],
    enabled: options.enabled,
    queryFn: async () => {
      const queryString = new URLSearchParams();
      if (params.page) queryString.append('page', params.page.toString());
      if (params.page_size) queryString.append('page_size', params.page_size.toString());
      if (params.search) queryString.append('search', params.search);
      if (params.status) queryString.append('status', params.status);
      if (params.student) queryString.append('student', params.student);
      if (params.ordering) queryString.append('ordering', params.ordering);

      const path = `/invoices/${queryString.toString() ? '?' + queryString.toString() : ''}`;
      return await apiClient.get<InvoiceListResponse>(path);
    },
  });
}

export function useInvoice(id: string) {
  return useQuery({
    queryKey: ['invoices', id],
    queryFn: async () => {
      return await apiClient.get<Invoice>(`/invoices/${id}/`);
    },
    enabled: !!id,
  });
}

export function useCreateInvoice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateInvoiceInput) => {
      return await apiClient.post<Invoice>('/invoices/', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['student-fees'] });
    },
  });
}

export function useUpdateInvoice(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: UpdateInvoiceInput) => {
      return await apiClient.patch<Invoice>(`/invoices/${id}/`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['invoices', id] });
      queryClient.invalidateQueries({ queryKey: ['student-fees'] });
    },
  });
}

/**
 * Delete invoice. Call `.mutate(id)` / `.mutateAsync(id)` with the target id —
 * this hook itself must be called once at component top level (Rules of Hooks).
 */
export function useDeleteInvoice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return await apiClient.delete(`/invoices/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['student-fees'] });
    },
  });
}

export function useMarkInvoicePaid(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      return await apiClient.post<Invoice>(`/invoices/${id}/mark_paid/`, {});
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      queryClient.invalidateQueries({ queryKey: ['invoices', id] });
      queryClient.invalidateQueries({ queryKey: ['student-fees'] });
    },
  });
}

// Student Fees
export function useStudentFeeList(params: InvoiceListParams = {}) {
  return useQuery({
    queryKey: ['student-fees', params],
    queryFn: async () => {
      const queryString = new URLSearchParams();
      if (params.page) queryString.append('page', params.page.toString());
      if (params.page_size) queryString.append('page_size', params.page_size.toString());
      if (params.search) queryString.append('search', params.search);
      if (params.ordering) queryString.append('ordering', params.ordering);

      const path = `/student-fees/${queryString.toString() ? '?' + queryString.toString() : ''}`;
      return await apiClient.get<{ results: StudentFee[] }>(path);
    },
  });
}

export function useStudentFee(id: string) {
  return useQuery({
    queryKey: ['student-fees', id],
    queryFn: async () => {
      return await apiClient.get<StudentFee>(`/student-fees/${id}/`);
    },
    enabled: !!id,
  });
}

// Transactions
export function useTransactionList(params: InvoiceListParams = {}) {
  return useQuery({
    queryKey: ['transactions', params],
    queryFn: async () => {
      const queryString = new URLSearchParams();
      if (params.page) queryString.append('page', params.page.toString());
      if (params.page_size) queryString.append('page_size', params.page_size.toString());
      if (params.search) queryString.append('search', params.search);
      if (params.ordering) queryString.append('ordering', params.ordering);

      const path = `/transactions/${queryString.toString() ? '?' + queryString.toString() : ''}`;
      return await apiClient.get<{ results: Transaction[] }>(path);
    },
  });
}
