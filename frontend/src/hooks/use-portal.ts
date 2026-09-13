"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch, apiFetchBlob } from "@/lib/api";
import { API } from "@/lib/config";
import type {
  ActivitiesResponse,
  Announcement,
  AttendanceSummary,
  BookCategory,
  BookMovementEntry,
  Child,
  ChildFeesResponse,
  FamilyInvoice,
  Library,
  LibrarianDashboard,
  LibraryBook,
  MarkableExam,
  MarkSheetResponse,
  ParentDashboard,
  Receipt,
  RegisterResponse,
  SaveActivitiesPayload,
  SaveAttendancePayload,
  SaveMarksPayload,
  SaveSkillsCommentsPayload,
  SaveSkillsPayload,
  SaveTeacherCommentsPayload,
  SkillLevel,
  SkillsCatalog,
  SkillsCommentsResponse,
  StudentReportCard,
  TeacherClass,
  TeacherCommentsResponse,
  TeacherDashboard,
} from "@/lib/types";

// ── Parent ──────────────────────────────────────────────────────────────────

export function useParentDashboard() {
  return useQuery({
    queryKey: ["parent", "dashboard"],
    queryFn: () => apiFetch<ParentDashboard>(API.parentDashboard),
    staleTime: 2 * 60 * 1000,
  });
}

export function useChildren() {
  return useQuery({
    queryKey: ["parent", "children"],
    queryFn: () => apiFetch<Child[]>(API.parentChildren),
    staleTime: 10 * 60 * 1000, // child list changes very rarely
  });
}

export function useChildReportCards(childId: string | undefined) {
  return useQuery({
    queryKey: ["parent", "report-cards", childId],
    queryFn: () => apiFetch<StudentReportCard[]>(API.childReportCards(childId!)),
    enabled: !!childId,
  });
}

/** Downloads a report card PDF and triggers a browser save-as, using the
 *  authenticated fetch path (a plain <a href> can't carry the JWT header). */
export async function downloadReportCardPdf(
  childId: string,
  reportId: string,
  filename: string,
) {
  const blob = await apiFetchBlob(API.childReportCardPdf(childId, reportId));
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function useChildAttendance(childId: string | undefined) {
  return useQuery({
    queryKey: ["parent", "attendance", childId],
    queryFn: () => apiFetch<AttendanceSummary>(API.childAttendance(childId!)),
    enabled: !!childId,
  });
}

export function useChildFees(
  childId: string | undefined,
  academicYear?: string,
) {
  return useQuery({
    queryKey: ["parent", "fees", childId, academicYear ?? "default"],
    queryFn: () =>
      apiFetch<ChildFeesResponse>(API.childFees(childId!, academicYear)),
    enabled: !!childId,
  });
}

export function useParentInvoices() {
  return useQuery({
    queryKey: ["parent", "invoices"],
    queryFn: () => apiFetch<FamilyInvoice[]>(API.parentInvoices),
    staleTime: 2 * 60 * 1000,
  });
}

/** Downloads an invoice PDF and triggers a browser save-as, using the
 *  authenticated fetch path (a plain <a href> can't carry the JWT header). */
export async function downloadInvoicePdf(invoiceId: string, invoiceNumber: string) {
  const blob = await apiFetchBlob(API.parentInvoicePdf(invoiceId));
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `fee-note_${invoiceNumber}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function useParentReceipts() {
  return useQuery({
    queryKey: ["parent", "receipts"],
    queryFn: () => apiFetch<Receipt[]>(API.parentReceipts),
    staleTime: 2 * 60 * 1000,
  });
}

/** Downloads a payment receipt PDF and triggers a browser save-as, using the
 *  authenticated fetch path (a plain <a href> can't carry the JWT header). */
export async function downloadReceiptPdf(referenceNumber: string) {
  const blob = await apiFetchBlob(API.parentReceiptPdf(referenceNumber));
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `receipt_${referenceNumber}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function useAnnouncements() {
  return useQuery({
    queryKey: ["parent", "announcements"],
    queryFn: () => apiFetch<Announcement[]>(API.announcements),
    staleTime: 5 * 60 * 1000,
  });
}

// ── Teacher ─────────────────────────────────────────────────────────────────

export function useTeacherDashboard() {
  return useQuery({
    queryKey: ["teacher", "dashboard"],
    queryFn: () => apiFetch<TeacherDashboard>(API.teacherDashboard),
  });
}

export function useTeacherClasses() {
  return useQuery({
    queryKey: ["teacher", "classes"],
    queryFn: () => apiFetch<TeacherClass[]>(API.teacherClasses),
    staleTime: 10 * 60 * 1000, // class list is static within a term
  });
}

export function useRegister(batchId: string | undefined, date: string) {
  return useQuery({
    queryKey: ["teacher", "register", batchId, date],
    queryFn: () =>
      apiFetch<RegisterResponse>(`${API.register(batchId!)}?date=${date}`),
    enabled: !!batchId,
  });
}

export function useSaveAttendance(batchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SaveAttendancePayload) =>
      apiFetch<{ saved: number; date: string }>(API.register(batchId), {
        method: "POST",
        body: payload,
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["teacher", "register", batchId, variables.date],
      });
      queryClient.invalidateQueries({ queryKey: ["teacher", "dashboard"] });
    },
  });
}

export function useTeacherExams() {
  return useQuery({
    queryKey: ["teacher", "exams"],
    queryFn: () => apiFetch<MarkableExam[]>(API.teacherExams),
    staleTime: 5 * 60 * 1000,
  });
}

export function useMarkSheet(examId: string | undefined) {
  return useQuery({
    queryKey: ["teacher", "marksheet", examId],
    queryFn: () => apiFetch<MarkSheetResponse>(API.marksheet(examId!)),
    enabled: !!examId,
  });
}

export function useSaveMarks(examId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SaveMarksPayload) =>
      apiFetch<{ saved: number }>(API.marksheet(examId), {
        method: "POST",
        body: payload,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teacher", "marksheet", examId] });
      queryClient.invalidateQueries({ queryKey: ["teacher", "exams"] });
    },
  });
}

export function useSkillsCatalog(batchId: string | undefined) {
  return useQuery({
    queryKey: ["teacher", "skills-catalog", batchId],
    queryFn: () =>
      apiFetch<SkillsCatalog>(
        batchId ? `${API.skillsCatalog}?batch=${batchId}` : API.skillsCatalog,
      ),
    staleTime: 10 * 60 * 1000, // skills catalog is static per term
  });
}

export function useStudentSkills(
  studentId: string | undefined,
  term: string,
) {
  return useQuery({
    queryKey: ["teacher", "student-skills", studentId, term],
    queryFn: () =>
      apiFetch<{ levels: Record<string, SkillLevel> }>(
        `${API.studentSkills(studentId!)}?term=${encodeURIComponent(term)}`,
      ),
    enabled: !!studentId,
  });
}

export function useSaveSkills(studentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SaveSkillsPayload) =>
      apiFetch<{ saved: number }>(API.studentSkills(studentId), {
        method: "POST",
        body: payload,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["teacher", "student-skills", studentId],
      });
    },
  });
}

export function useActivities(batchId: string | undefined, examGroupId: string) {
  return useQuery({
    queryKey: ["teacher", "activities", batchId, examGroupId],
    queryFn: () =>
      apiFetch<ActivitiesResponse>(
        examGroupId
          ? `${API.activities(batchId!)}?exam_group=${examGroupId}`
          : API.activities(batchId!),
      ),
    enabled: !!batchId,
  });
}

export function useExamComments(examGroupId: string | undefined, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["teacher", "comments", examGroupId],
    queryFn: () => apiFetch<TeacherCommentsResponse>(API.teacherComments(examGroupId!)),
    enabled: options?.enabled ?? !!examGroupId,
    staleTime: 2 * 60 * 1000,
  });
}

export function useSaveExamComments(examGroupId: string, options?: { enabled?: boolean }) {
  // No onSuccess cache invalidation here: the comment form is the source of
  // truth for its own local state while the teacher is typing, and
  // refetching after every autosave would race with in-progress keystrokes
  // and clobber them (see marks/page.tsx comment seed effect).
  return useMutation({
    mutationFn: (payload: SaveTeacherCommentsPayload) =>
      apiFetch<{ success: boolean; saved_count: number }>(API.saveTeacherComments, {
        method: "POST",
        body: payload,
      }),
  });
}

export function useSkillsComments(batchId: string | undefined, term: string) {
  return useQuery({
    queryKey: ["teacher", "skills-comments", batchId, term],
    queryFn: () =>
      apiFetch<SkillsCommentsResponse>(
        `${API.skillsComments(batchId!)}?term=${encodeURIComponent(term)}`,
      ),
    enabled: !!batchId,
    staleTime: 2 * 60 * 1000,
  });
}

export function useSaveSkillsComments(batchId: string) {
  // See useSaveExamComments: no cache invalidation, to avoid a post-save
  // refetch racing with (and clobbering) in-progress typing.
  return useMutation({
    mutationFn: (payload: SaveSkillsCommentsPayload) =>
      apiFetch<{ saved: number }>(API.skillsComments(batchId), {
        method: "POST",
        body: payload,
      }),
  });
}

export function useSubmitSkills(batchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { term: string | null }) =>
      apiFetch<{ status: string }>(API.skillsSubmission(batchId), {
        method: "POST",
        body: payload,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["teacher", "skills-catalog", batchId],
      });
    },
  });
}

export function useSaveActivities(batchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SaveActivitiesPayload) =>
      apiFetch<{ saved: number; term: string }>(API.activities(batchId), {
        method: "POST",
        body: payload,
      }),
    onSuccess: (_d, vars) => {
      queryClient.invalidateQueries({
        queryKey: ["teacher", "activities", batchId, vars.exam_group],
      });
    },
  });
}

// ── Librarian ───────────────────────────────────────────────────────────────

export function useLibrarianDashboard() {
  return useQuery({
    queryKey: ["librarian", "dashboard"],
    queryFn: () => apiFetch<LibrarianDashboard>(API.librarianDashboard),
    staleTime: 5 * 60 * 1000,
  });
}

export function useLibrarianLibraries() {
  return useQuery({
    queryKey: ["librarian", "libraries"],
    queryFn: () => apiFetch<Library[]>(API.librarianLibraries),
    staleTime: 10 * 60 * 1000,
  });
}

export function useLibrarianBooks(libraryId?: string, query?: string) {
  return useQuery({
    queryKey: ["librarian", "books", libraryId, query],
    queryFn: () => {
      const params = new URLSearchParams();
      if (libraryId) params.append("library_id", libraryId);
      if (query) params.append("q", query);
      const url = `${API.librarianBooks}${params.toString() ? `?${params}` : ""}`;
      return apiFetch<LibraryBook[]>(url);
    },
    staleTime: 2 * 60 * 1000,
  });
}

export function useLibrarianCategories() {
  return useQuery({
    queryKey: ["librarian", "categories"],
    queryFn: () => apiFetch<BookCategory[]>(API.librarianCategories),
    staleTime: 10 * 60 * 1000,
  });
}

export interface LibrarianBatch {
  id: string;
  name: string;
  course: string | null;
  academic_year: string | null;
}

export interface LibrarianBatchStudent {
  id: string;
  full_name: string;
  admission_no: string;
}

export function useLibrarianBatches() {
  return useQuery({
    queryKey: ["librarian", "batches"],
    queryFn: () => apiFetch<LibrarianBatch[]>(API.librarianBatches),
    staleTime: 10 * 60 * 1000,
  });
}

export function useLibrarianBatchStudents(batchId?: string) {
  return useQuery({
    queryKey: ["librarian", "batch-students", batchId],
    queryFn: () =>
      apiFetch<LibrarianBatchStudent[]>(
        API.librarianBatchStudents(batchId as string),
      ),
    enabled: !!batchId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useLibrarianCreateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      apiFetch<BookCategory>(API.librarianCategories, {
        method: "POST",
        body: { name },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["librarian", "categories"] });
    },
  });
}

export interface CreateBookPayload {
  library_id: string;
  title: string;
  author?: string;
  isbn?: string;
  book_number?: string;
  category_id?: string;
  total_copies?: number;
  price?: string;
  book_type?: string;
  school_level?: string;
}

export function useLibrarianCreateBook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateBookPayload) =>
      apiFetch<LibraryBook>(API.librarianBooks, {
        method: "POST",
        body: payload,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["librarian", "books"] });
      queryClient.invalidateQueries({ queryKey: ["librarian", "dashboard"] });
    },
  });
}

export function useLibrarianUpdateBook(bookId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<CreateBookPayload>) =>
      apiFetch<LibraryBook>(API.librarianBookDetail(bookId), {
        method: "PUT",
        body: payload,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["librarian", "books"] });
    },
  });
}

export function useLibrarianIssued(libraryId?: string, overdueOnly?: boolean) {
  return useQuery({
    queryKey: ["librarian", "issued", libraryId, overdueOnly],
    queryFn: () => {
      const params = new URLSearchParams();
      if (libraryId) params.append("library_id", libraryId);
      if (overdueOnly) params.append("overdue_only", "true");
      const url = `${API.librarianIssued}${params.toString() ? `?${params}` : ""}`;
      return apiFetch<BookMovementEntry[]>(url);
    },
    staleTime: 1 * 60 * 1000,
  });
}

export function useLibrarianOverdue(libraryId?: string) {
  return useQuery({
    queryKey: ["librarian", "overdue", libraryId],
    queryFn: () => {
      const params = new URLSearchParams();
      if (libraryId) params.append("library_id", libraryId);
      const url = `${API.librarianOverdue}${params.toString() ? `?${params}` : ""}`;
      return apiFetch<BookMovementEntry[]>(url);
    },
    staleTime: 1 * 60 * 1000,
  });
}

export function useLibrarianScanLookup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (barcode: string) =>
      apiFetch<LibraryBook>(API.librarianScanLookup, {
        method: "POST",
        body: { barcode },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["librarian", "books"] });
    },
  });
}

export function useLibrarianScanIssue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      book_id?: string;
      barcode?: string;
      /** Prefer student_id / employee_id; borrower_id kept for compatibility. */
      student_id?: string;
      employee_id?: string;
      borrower_id?: string;
      due_days?: number;
    }) =>
      apiFetch<BookMovementEntry>(API.librarianScanIssue, {
        method: "POST",
        body: payload,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["librarian", "issued"] });
      queryClient.invalidateQueries({ queryKey: ["librarian", "dashboard"] });
    },
  });
}

export function useLibrarianScanReturn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { book_id?: string; barcode?: string }) =>
      apiFetch<BookMovementEntry>(API.librarianScanReturn, {
        method: "POST",
        body: payload,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["librarian", "issued"] });
      queryClient.invalidateQueries({ queryKey: ["librarian", "overdue"] });
      queryClient.invalidateQueries({ queryKey: ["librarian", "dashboard"] });
    },
  });
}
