/**
 * React Query hooks for Finance CRUD.
 *
 * Covers:
 * - Invoices (list, fetch — read-only; see hooks.ts InvoiceViewSet note below)
 * - Fees (student fees, balance queries)
 * - Transactions (record payments/refunds)
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

/**
 * FamilyInvoice is a guardian-level consolidated invoice for an academic
 * year — it aggregates every child's fee charges into one invoice. It is
 * entirely system-generated (InvoiceService upserts it whenever a charge
 * exists and recomputes totals/status after every charge or payment), so
 * the backend ViewSet is read-only: there is no create/update/delete or
 * mark-paid action to call.
 */
export interface Invoice {
  id: string;
  invoice_number: string;
  guardian: string;
  guardian_name: string;
  academic_year: string;
  academic_year_label: string;
  status: 'open' | 'paid' | 'void';
  subtotal: number;
  total_amount: number;
  amount_paid: number;
  balance_due: number;
  due_date: string | null;
  generated_at: string;
  last_updated_at: string;
  lines: InvoiceLine[];
}

export interface InvoiceLine {
  id: string;
  student: string;
  student_name: string;
  description: string;
  amount: number;
}

export interface StudentFee {
  id: string;
  student: string;
  student_name: string;
  fee_category: string;
  fee_category_name: string;
  academic_year: string | null;
  balance: number;
  transaction_date: string | null;
  is_paid: boolean;
  tax_amount: number;
  discount_amount: number;
  invoice_number: string | null;
  created_at: string;
  updated_at: string;
}

export interface Transaction {
  id: string;
  title: string;
  transaction_date: string;
  category: string;
  category_name: string;
  student: string | null;
  student_name: string | null;
  employee: string | null;
  employee_name: string | null;
  academic_year: string | null;
  description?: string;
  amount: number;
  payment_method: 'cash' | 'card' | 'bank_transfer' | 'mobile_money' | 'cheque' | 'online' | 'other';
  reference_number?: string;
  created_at: string;
  updated_at: string;
}

export interface InvoiceListParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  guardian?: string;
  ordering?: string;
}

export interface InvoiceListResponse {
  count: number;
  next?: string;
  previous?: string;
  results: Invoice[];
}

// Invoices — read-only (list + detail). FamilyInvoice has no legitimate
// manual create/update/delete/mark-paid action; see the Invoice interface
// doc comment above.
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
      if (params.guardian) queryString.append('guardian', params.guardian);
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

/** Same-origin PDF download URL for an invoice, routed through a dedicated
 * Next.js route handler (not the shared BFF proxy, which always returns
 * JSON and can't pass through a binary PDF response) — see
 * app/api/finance/invoice-pdf/route.ts and the CSV equivalent,
 * getStudentLedgerCsvExportUrl. */
export function getInvoicePdfUrl(id: string): string {
  return `/api/finance/invoice-pdf?id=${id}`;
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
  academic_year?: string | null;
  academic_year_label?: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeeCategoryListParams {
  page?: number;
  page_size?: number;
  search?: string;
  academic_year?: string;
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
  academic_year?: string | null;
}

export interface UpdateFeeCategoryInput {
  name?: string;
  description?: string;
  academic_year?: string | null;
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
      if (params.academic_year) queryString.append('academic_year', params.academic_year);
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
  discount_mode: 'percentage' | 'amount';
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
  discount_mode: 'percentage' | 'amount';
  discount_value: number;
  is_active?: boolean;
}

export interface UpdateFeeDiscountInput {
  fee_category?: string;
  name?: string;
  discount_type?: 'batch' | 'individual';
  discount_mode?: 'percentage' | 'amount';
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

// ───────────────────────────────────────────────────────────────────────────
// Reports — Day Book
// ───────────────────────────────────────────────────────────────────────────

export interface DayBookModeTotals {
  in: number;
  out: number;
}

export interface DayBookDayRow {
  date: string;
  opening_balance: number;
  total_in: number;
  total_out: number;
  closing_balance: number;
  by_mode: Record<string, DayBookModeTotals>;
}

export interface DayBookReport {
  date_from: string;
  date_to: string;
  days: DayBookDayRow[];
  total_in: number;
  total_out: number;
  closing_balance: number;
}

export function useDayBookReport(fromDate: string, toDate: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['day-book', fromDate, toDate],
    enabled: options.enabled,
    queryFn: async () => {
      const queryString = new URLSearchParams();
      if (fromDate) queryString.append('from_date', fromDate);
      if (toDate) queryString.append('to_date', toDate);
      const path = `/finance/day-book/${queryString.toString() ? '?' + queryString.toString() : ''}`;
      return await apiClient.get<DayBookReport>(path);
    },
  });
}

// ───────────────────────────────────────────────────────────────────────────
// Reports — Particular-wise Student Transaction Report (student ledger)
// ───────────────────────────────────────────────────────────────────────────

export interface StudentLedgerRow {
  student_id: string;
  student_name: string;
  batch_name: string;
  expected_amount: number;
  paid_amount: number;
  balance_amount: number;
  pta_expected: number;
  pta_paid: number;
  pta_balance: number;
  tuition_expected: number;
  tuition_paid: number;
  tuition_balance: number;
}

export interface StudentLedgerGrandTotals {
  grand_expected: number;
  grand_paid: number;
  grand_balance: number;
  grand_pta_expected: number;
  grand_pta_paid: number;
  grand_pta_balance: number;
  grand_tuition_expected: number;
  grand_tuition_paid: number;
  grand_tuition_balance: number;
}

export interface StudentLedgerReport {
  academic_year: string;
  academic_year_name: string;
  rows: StudentLedgerRow[];
  grand_totals: StudentLedgerGrandTotals;
}

export interface StudentLedgerReportParams {
  academic_year?: string;
  student_status?: 'active' | 'all';
  class?: string;
  batch?: string;
  fee_account?: string;
  from_date?: string;
  to_date?: string;
  with_expected?: boolean;
}

function buildStudentLedgerQueryString(params: StudentLedgerReportParams): string {
  const queryString = new URLSearchParams();
  if (params.academic_year) queryString.append('academic_year', params.academic_year);
  if (params.student_status) queryString.append('student_status', params.student_status);
  if (params.class) queryString.append('class', params.class);
  if (params.batch) queryString.append('batch', params.batch);
  if (params.fee_account) queryString.append('fee_account', params.fee_account);
  if (params.from_date) queryString.append('from_date', params.from_date);
  if (params.to_date) queryString.append('to_date', params.to_date);
  if (params.with_expected) queryString.append('with_expected', 'true');
  return queryString.toString();
}

export function useStudentLedgerReport(params: StudentLedgerReportParams = {}, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['student-ledger', params],
    enabled: options.enabled,
    queryFn: async () => {
      const qs = buildStudentLedgerQueryString(params);
      const path = `/finance/student-ledger/${qs ? '?' + qs : ''}`;
      return await apiClient.get<StudentLedgerReport>(path);
    },
  });
}

/** Builds the same-origin CSV export URL for the student ledger report,
 * routed through a dedicated Next.js route handler (not the shared BFF
 * proxy, which always returns JSON) so the browser gets a real CSV download. */
export function getStudentLedgerCsvExportUrl(params: StudentLedgerReportParams = {}): string {
  const qs = buildStudentLedgerQueryString(params);
  return `/api/finance/student-ledger-export${qs ? '?' + qs : ''}`;
}

// ───────────────────────────────────────────────────────────────────────────
// Lightweight course/batch option lists (for report filters)
// ───────────────────────────────────────────────────────────────────────────

export interface CourseOption {
  id: string;
  course_name: string;
}

export interface BatchOption {
  id: string;
  name: string;
  course?: string;
}

export function useCourseOptions() {
  return useQuery({
    queryKey: ['course-options'],
    queryFn: async () => {
      return await apiClient.get<{ results: CourseOption[] }>('/courses/?page_size=200');
    },
  });
}

export function useBatchOptions() {
  return useQuery({
    queryKey: ['batch-options'],
    queryFn: async () => {
      return await apiClient.get<{ results: BatchOption[] }>('/batches/?page_size=200');
    },
  });
}
