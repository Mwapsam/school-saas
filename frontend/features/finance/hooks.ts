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

// Fee Categories
export interface FeeCategory {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FeeCategoryListParams {
  page?: number;
  page_size?: number;
  search?: string;
  is_active?: boolean;
  ordering?: string;
}

export interface FeeCategoryListResponse {
  count: number;
  next?: string;
  previous?: string;
  results: FeeCategory[];
}

export interface CreateFeeCategoryInput {
  name: string;
  description?: string;
  is_active?: boolean;
}

export interface UpdateFeeCategoryInput {
  name?: string;
  description?: string;
  is_active?: boolean;
}

export function useFeeCategoryList(params: FeeCategoryListParams = {}, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['fee-categories', params],
    enabled: options.enabled,
    queryFn: async () => {
      const queryString = new URLSearchParams();
      if (params.page) queryString.append('page', params.page.toString());
      if (params.page_size) queryString.append('page_size', params.page_size.toString());
      if (params.search) queryString.append('search', params.search);
      if (params.is_active !== undefined) queryString.append('is_active', params.is_active.toString());
      if (params.ordering) queryString.append('ordering', params.ordering);

      const path = `/fee-categories/${queryString.toString() ? '?' + queryString.toString() : ''}`;
      return await apiClient.get<FeeCategoryListResponse>(path);
    },
  });
}

export function useFeeCategory(id: string) {
  return useQuery({
    queryKey: ['fee-categories', id],
    queryFn: async () => {
      return await apiClient.get<FeeCategory>(`/fee-categories/${id}/`);
    },
    enabled: !!id,
  });
}

export function useCreateFeeCategory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateFeeCategoryInput) => {
      return await apiClient.post<FeeCategory>('/fee-categories/', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fee-categories'] });
    },
  });
}

export function useUpdateFeeCategory(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: UpdateFeeCategoryInput) => {
      return await apiClient.patch<FeeCategory>(`/fee-categories/${id}/`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fee-categories'] });
      queryClient.invalidateQueries({ queryKey: ['fee-categories', id] });
    },
  });
}

/**
 * Delete fee category. Call `.mutate(id)` / `.mutateAsync(id)` with the target id —
 * this hook itself must be called once at component top level (Rules of Hooks).
 */
export function useDeleteFeeCategory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return await apiClient.delete(`/fee-categories/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fee-categories'] });
    },
  });
}

// Fee Discounts
export interface FeeDiscount {
  id: string;
  fee_category: string;
  fee_category_name: string;
  name: string;
  discount_type: 'batch' | 'individual';
  discount_value: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FeeDiscountListParams {
  page?: number;
  page_size?: number;
  search?: string;
  fee_category?: string;
  discount_type?: string;
  is_active?: boolean;
  ordering?: string;
}

export interface FeeDiscountListResponse {
  count: number;
  next?: string;
  previous?: string;
  results: FeeDiscount[];
}

export interface CreateFeeDiscountInput {
  fee_category: string;
  name: string;
  discount_type: 'batch' | 'individual';
  discount_value: number;
  is_active?: boolean;
}

export interface UpdateFeeDiscountInput {
  fee_category?: string;
  name?: string;
  discount_type?: 'batch' | 'individual';
  discount_value?: number;
  is_active?: boolean;
}

export function useFeeDiscountList(params: FeeDiscountListParams = {}, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['fee-discounts', params],
    enabled: options.enabled,
    queryFn: async () => {
      const queryString = new URLSearchParams();
      if (params.page) queryString.append('page', params.page.toString());
      if (params.page_size) queryString.append('page_size', params.page_size.toString());
      if (params.search) queryString.append('search', params.search);
      if (params.fee_category) queryString.append('fee_category', params.fee_category);
      if (params.discount_type) queryString.append('discount_type', params.discount_type);
      if (params.is_active !== undefined) queryString.append('is_active', params.is_active.toString());
      if (params.ordering) queryString.append('ordering', params.ordering);

      const path = `/fee-discounts/${queryString.toString() ? '?' + queryString.toString() : ''}`;
      return await apiClient.get<FeeDiscountListResponse>(path);
    },
  });
}

export function useFeeDiscount(id: string) {
  return useQuery({
    queryKey: ['fee-discounts', id],
    queryFn: async () => {
      return await apiClient.get<FeeDiscount>(`/fee-discounts/${id}/`);
    },
    enabled: !!id,
  });
}

export function useCreateFeeDiscount() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateFeeDiscountInput) => {
      return await apiClient.post<FeeDiscount>('/fee-discounts/', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fee-discounts'] });
    },
  });
}

export function useUpdateFeeDiscount(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: UpdateFeeDiscountInput) => {
      return await apiClient.patch<FeeDiscount>(`/fee-discounts/${id}/`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fee-discounts'] });
      queryClient.invalidateQueries({ queryKey: ['fee-discounts', id] });
    },
  });
}

/**
 * Delete fee discount. Call `.mutate(id)` / `.mutateAsync(id)` with the target id —
 * this hook itself must be called once at component top level (Rules of Hooks).
 */
export function useDeleteFeeDiscount() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return await apiClient.delete(`/fee-discounts/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fee-discounts'] });
    },
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
