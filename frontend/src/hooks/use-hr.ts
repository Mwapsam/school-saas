"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch, apiUpload } from "@/lib/api";
import { API } from "@/lib/config";
import { useAuth } from "@/hooks/use-auth";
import type {
  HRApplicant,
  HRAttendanceRow,
  HRContract,
  HRDashboard,
  HRDisciplinaryCase,
  HRGrievance,
  HRDocument,
  HREmployeeDetail,
  HRHistoryEvent,
  HRLeave,
  HRExit,
  HROnboarding,
  HRPerformanceReview,
  HRReportResult,
  HRTraining,
  HRTrainingCompliance,
  HRTask,
  HRVacancy,
  Paginated,
} from "@/lib/types";

const STALE = 60 * 1000;

/** True when the signed-in HR user holds `codename` (or any `hr.*` when they
 *  have the wildcard via hr-manager). */
export function useHRCan(codename: string): boolean {
  const { user } = useAuth();
  return (user?.hr_permissions ?? []).includes(codename);
}

export function useHRDashboard() {
  return useQuery({
    queryKey: ["hr", "dashboard"],
    queryFn: () => apiFetch<HRDashboard>(API.hrDashboard),
    staleTime: STALE,
  });
}

export function useHREmployees(params: Record<string, string>) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "employees", qs],
    queryFn: () =>
      apiFetch<Paginated<import("@/lib/types").HREmployeeRow>>(
        `${API.hrEmployees}${qs ? `?${qs}` : ""}`,
      ),
    staleTime: STALE,
  });
}

export function useCreateEmployee() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<HREmployeeDetail>(API.hrEmployees, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "employees"] }),
  });
}

export function useHREmployee(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "employee", id],
    queryFn: () => apiFetch<HREmployeeDetail>(API.hrEmployee(id!)),
    enabled: !!id,
    staleTime: STALE,
  });
}

export function useHREmployeeContracts(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "employee", id, "contracts"],
    queryFn: () => apiFetch<HRContract[]>(API.hrEmployeeContracts(id!)),
    enabled: !!id,
  });
}

export function useHREmployeeDocuments(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "employee", id, "documents"],
    queryFn: () => apiFetch<HRDocument[]>(API.hrEmployeeDocuments(id!)),
    enabled: !!id,
  });
}

export function useHREmployeeQualifications(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "employee", id, "qualifications"],
    queryFn: () =>
      apiFetch<import("@/lib/types").HRQualification[]>(API.hrEmployeeQualifications(id!)),
    enabled: !!id,
  });
}

export function useAddQualification(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch(API.hrEmployeeQualifications(id), { method: "POST", body }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["hr", "employee", id, "qualifications"] }),
  });
}

export function useUploadDocument(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (form: FormData) =>
      apiUpload<HRDocument>(API.hrEmployeeDocuments(id), form),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["hr", "employee", id, "documents"] }),
  });
}

export function useDeleteDocument(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (docId: string) =>
      apiFetch(API.hrDocument(docId), { method: "DELETE" }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["hr", "employee", employeeId, "documents"] }),
  });
}

export function useContractDecision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: string }) =>
      apiFetch<HRContract>(API.hrContractDecision(id), { method: "POST", body: { decision } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "contracts"] }),
  });
}

export function useHREmployeeHistory(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "employee", id, "history"],
    queryFn: () => apiFetch<HRHistoryEvent[]>(API.hrEmployeeHistory(id!)),
    enabled: !!id,
  });
}

export function useHREmployeeAttendance(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "employee", id, "attendance"],
    queryFn: () =>
      apiFetch<{ summary: Record<string, number | null>; records: HRAttendanceRow[] }>(
        API.hrEmployeeAttendance(id!),
      ),
    enabled: !!id,
  });
}

export function useUpdateEmployee(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<HREmployeeDetail>) =>
      apiFetch<HREmployeeDetail>(API.hrEmployee(id), { method: "PATCH", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "employee", id] });
      qc.invalidateQueries({ queryKey: ["hr", "employees"] });
    },
  });
}

export function useCreateContract(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<HRContract>(API.hrEmployeeContracts(employeeId), { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "employee", employeeId, "contracts"] });
      qc.invalidateQueries({ queryKey: ["hr", "contracts"] });
    },
  });
}

export function useContracts(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "contracts", qs],
    queryFn: () =>
      apiFetch<Paginated<HRContract>>(`${API.hrContracts}${qs ? `?${qs}` : ""}`),
    staleTime: STALE,
  });
}

export function useRenewContract() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<HRContract>(API.hrContractRenew(id), { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "contracts"] }),
  });
}

export function useHRLeave(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "leave", qs],
    queryFn: () =>
      apiFetch<Paginated<HRLeave>>(`${API.hrLeave}${qs ? `?${qs}` : ""}`),
    staleTime: STALE,
  });
}

export function useLeaveReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      stage,
      approve,
      remark,
    }: {
      id: string;
      stage: "supervisor" | "hr";
      approve: boolean;
      remark?: string;
    }) =>
      apiFetch<HRLeave>(
        stage === "supervisor"
          ? API.hrLeaveSupervisorReview(id)
          : API.hrLeaveHRReview(id),
        { method: "POST", body: { approve, remark } },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "leave"] });
      qc.invalidateQueries({ queryKey: ["hr", "dashboard"] });
    },
  });
}

export function useHRAttendance(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "attendance", qs],
    queryFn: () =>
      apiFetch<Paginated<HRAttendanceRow>>(`${API.hrAttendance}${qs ? `?${qs}` : ""}`),
    staleTime: STALE,
  });
}

export function useMarkAttendance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      employee_id: string;
      date: string;
      status: string;
      remarks?: string;
    }) => apiFetch<HRAttendanceRow>(API.hrAttendance, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "attendance"] }),
  });
}

export function useAttendanceAnalytics() {
  return useQuery({
    queryKey: ["hr", "attendance", "analytics"],
    queryFn: () =>
      apiFetch<{
        watchlist: {
          id: string;
          name: string;
          late_count: number;
          absent_count: number;
        }[];
        no_record_today: { id: string; name: string; employee_number: string }[];
      }>(API.hrAttendanceAnalytics),
    staleTime: STALE,
  });
}

export function useHRTasks(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "tasks", qs],
    queryFn: () =>
      apiFetch<Paginated<HRTask>>(`${API.hrTasks}${qs ? `?${qs}` : ""}`),
    staleTime: STALE,
  });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<HRTask>(API.hrTasks, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "tasks"] }),
  });
}

export function useUpdateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<HRTask>(API.hrTask(id), { method: "PATCH", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "tasks"] });
      qc.invalidateQueries({ queryKey: ["hr", "dashboard"] });
    },
  });
}

export function useHRReportIndex() {
  return useQuery({
    queryKey: ["hr", "reports"],
    queryFn: () =>
      apiFetch<{ reports: { slug: string; title: string }[] }>(API.hrReports),
    staleTime: 10 * 60 * 1000,
  });
}

export function useHRReport(slug: string | undefined, params: Record<string, string> = {}) {
  const qs = new URLSearchParams(params).toString();
  return useQuery({
    queryKey: ["hr", "report", slug, qs],
    queryFn: () =>
      apiFetch<HRReportResult>(API.hrReport(slug!, qs ? `?${qs}` : "")),
    enabled: !!slug,
  });
}

// ── Employee Exit ──────────────────────────────────────────────────────────

export function useExitList(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "exit", qs],
    queryFn: () => apiFetch<Paginated<HRExit>>(`${API.hrExitList}${qs ? `?${qs}` : ""}`),
    staleTime: STALE,
  });
}

export function useEmployeeExit(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "employee", id, "exit"],
    queryFn: () => apiFetch<HRExit>(API.hrEmployeeExit(id!)),
    enabled: !!id,
    retry: false,
  });
}

export function useStartExit(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<HRExit>(API.hrEmployeeExit(employeeId), { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "employee", employeeId] });
      qc.invalidateQueries({ queryKey: ["hr", "exit"] });
    },
  });
}

export function useUpdateExit(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<HRExit>(API.hrExit(id), { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "employee", employeeId, "exit"] }),
  });
}

export function useToggleExitItem(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, is_done }: { id: string; is_done: boolean }) =>
      apiFetch(API.hrExitItem(id), { method: "PATCH", body: { is_done } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "employee", employeeId, "exit"] }),
  });
}

export function useCompleteExit(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<HRExit>(API.hrExitComplete(id), { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "employee", employeeId] });
      qc.invalidateQueries({ queryKey: ["hr", "exit"] });
      qc.invalidateQueries({ queryKey: ["hr", "dashboard"] });
    },
  });
}

// ── Training ───────────────────────────────────────────────────────────────

export function useTrainingList(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "training", qs],
    queryFn: () =>
      apiFetch<Paginated<HRTraining>>(`${API.hrTraining}${qs ? `?${qs}` : ""}`),
    staleTime: STALE,
  });
}

export function useTrainingCompliance() {
  return useQuery({
    queryKey: ["hr", "training", "compliance"],
    queryFn: () => apiFetch<HRTrainingCompliance>(API.hrTrainingCompliance),
    staleTime: STALE,
  });
}

export function useEmployeeTraining(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "employee", id, "training"],
    queryFn: () => apiFetch<HRTraining[]>(API.hrEmployeeTraining(id!)),
    enabled: !!id,
  });
}

export function useCreateTraining() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<HRTraining>(API.hrTraining, { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "training"] });
      qc.invalidateQueries({ queryKey: ["hr", "dashboard"] });
    },
  });
}

export function useUpdateTraining() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<HRTraining>(API.hrTrainingRecord(id), { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "training"] }),
  });
}

export function useDeleteTraining() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(API.hrTrainingRecord(id), { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "training"] }),
  });
}

// ── Performance ────────────────────────────────────────────────────────────

export function usePerformanceReviews(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "reviews", qs],
    queryFn: () =>
      apiFetch<Paginated<HRPerformanceReview>>(`${API.hrReviews}${qs ? `?${qs}` : ""}`),
    staleTime: STALE,
  });
}

export function usePerformanceReview(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "review", id],
    queryFn: () => apiFetch<HRPerformanceReview>(API.hrReview(id!)),
    enabled: !!id,
  });
}

export function useEmployeeReviews(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "employee", id, "reviews"],
    queryFn: () => apiFetch<HRPerformanceReview[]>(API.hrEmployeePerformance(id!)),
    enabled: !!id,
  });
}

export function useCreateReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<HRPerformanceReview>(API.hrReviews, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "reviews"] }),
  });
}

export function useUpdateReview(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<HRPerformanceReview>(API.hrReview(id), { method: "PATCH", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "review", id] });
      qc.invalidateQueries({ queryKey: ["hr", "reviews"] });
    },
  });
}

export function useCompleteReview(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<HRPerformanceReview>(API.hrReviewComplete(id), { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "review", id] });
      qc.invalidateQueries({ queryKey: ["hr", "reviews"] });
      qc.invalidateQueries({ queryKey: ["hr", "dashboard"] });
    },
  });
}

// ── Onboarding ─────────────────────────────────────────────────────────────

export function useOnboardingList() {
  return useQuery({
    queryKey: ["hr", "onboarding"],
    queryFn: () => apiFetch<Paginated<HROnboarding>>(API.hrOnboardingList),
    staleTime: STALE,
  });
}

export function useEmployeeOnboarding(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "employee", id, "onboarding"],
    queryFn: () => apiFetch<HROnboarding>(API.hrEmployeeOnboarding(id!)),
    enabled: !!id,
  });
}

export function useToggleOnboardingItem(employeeId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, is_done, note }: { id: string; is_done: boolean; note?: string }) =>
      apiFetch(API.hrOnboardingItem(id), { method: "PATCH", body: { is_done, note } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "employee", employeeId, "onboarding"] });
      qc.invalidateQueries({ queryKey: ["hr", "onboarding"] });
      qc.invalidateQueries({ queryKey: ["hr", "dashboard"] });
    },
  });
}

export function useAddOnboardingItem(employeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (label: string) =>
      apiFetch(API.hrEmployeeOnboarding(employeeId), { method: "POST", body: { label } }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["hr", "employee", employeeId, "onboarding"] }),
  });
}

// ── Recruitment / ATS ──────────────────────────────────────────────────────

export function useVacancies(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "vacancies", qs],
    queryFn: () =>
      apiFetch<Paginated<HRVacancy>>(`${API.hrVacancies}${qs ? `?${qs}` : ""}`),
    staleTime: STALE,
  });
}

export function useVacancy(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "vacancy", id],
    queryFn: () => apiFetch<HRVacancy>(API.hrVacancy(id!)),
    enabled: !!id,
  });
}

export function useCreateVacancy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<HRVacancy>(API.hrVacancies, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "vacancies"] }),
  });
}

export function useUpdateVacancy(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<HRVacancy>(API.hrVacancy(id), { method: "PATCH", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "vacancy", id] });
      qc.invalidateQueries({ queryKey: ["hr", "vacancies"] });
    },
  });
}

export function useApplicants(vacancyId: string | undefined) {
  return useQuery({
    queryKey: ["hr", "applicants", vacancyId],
    queryFn: () => apiFetch<HRApplicant[]>(API.hrVacancyApplicants(vacancyId!)),
    enabled: !!vacancyId,
  });
}

export function useCreateApplicant(vacancyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<HRApplicant>(API.hrVacancyApplicants(vacancyId), { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "applicants", vacancyId] });
      qc.invalidateQueries({ queryKey: ["hr", "vacancy", vacancyId] });
    },
  });
}

export function useAdvanceApplicant(vacancyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<HRApplicant>(API.hrApplicantAdvance(id), { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "applicants", vacancyId] }),
  });
}

export function useConvertApplicant(vacancyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<{ employee_id: string; employee_number: string }>(
        API.hrApplicantConvert(id), { method: "POST", body },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "applicants", vacancyId] });
      qc.invalidateQueries({ queryKey: ["hr", "employees"] });
    },
  });
}

// ── My HR (self-service) ────────────────────────────────────────────────────

export function useMyHRProfile() {
  return useQuery({
    queryKey: ["my-hr", "profile"],
    queryFn: () => apiFetch<HREmployeeDetail>(API.hrMeProfile),
    staleTime: STALE,
  });
}

export function useUpdateMyHRProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<HREmployeeDetail>) =>
      apiFetch<HREmployeeDetail>(API.hrMeProfile, { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-hr", "profile"] }),
  });
}

export function useMyLeave() {
  return useQuery({
    queryKey: ["my-hr", "leave"],
    queryFn: () => apiFetch<HRLeave[]>(API.hrMeLeave),
    staleTime: STALE,
  });
}

export function useApplyForLeave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      leave_type_id?: string | null;
      start_date: string;
      end_date: string;
      reason: string;
    }) => apiFetch<HRLeave>(API.hrMeLeave, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-hr", "leave"] }),
  });
}

export function useMyAttendance() {
  return useQuery({
    queryKey: ["my-hr", "attendance"],
    queryFn: () => apiFetch<HRAttendanceRow[]>(API.hrMeAttendance),
    staleTime: STALE,
  });
}

export function useMyDocuments() {
  return useQuery({
    queryKey: ["my-hr", "documents"],
    queryFn: () => apiFetch<HRDocument[]>(API.hrMeDocuments),
    staleTime: STALE,
  });
}

export function useMyContracts() {
  return useQuery({
    queryKey: ["my-hr", "contracts"],
    queryFn: () => apiFetch<HRContract[]>(API.hrMeContracts),
    staleTime: STALE,
  });
}

// ── Employee Relations (disciplinary & grievance) ──────────────────────────

export function useDisciplinaryList(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "disciplinary", qs],
    queryFn: () =>
      apiFetch<Paginated<HRDisciplinaryCase>>(`${API.hrDisciplinary}${qs ? `?${qs}` : ""}`),
    staleTime: STALE,
  });
}

export function useDisciplinaryCase(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "disciplinary", "case", id],
    queryFn: () => apiFetch<HRDisciplinaryCase>(API.hrDisciplinaryCase(id!)),
    enabled: !!id,
  });
}

export function useEmployeeDisciplinary(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "employee", id, "disciplinary"],
    queryFn: () =>
      apiFetch<Paginated<HRDisciplinaryCase>>(API.hrEmployeeDisciplinary(id!)),
    enabled: !!id,
  });
}

export function useCreateDisciplinary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<HRDisciplinaryCase>(API.hrDisciplinary, { method: "POST", body }),
    onSuccess: (row) => {
      qc.invalidateQueries({ queryKey: ["hr", "disciplinary"] });
      if (row?.employee_id)
        qc.invalidateQueries({ queryKey: ["hr", "employee", row.employee_id] });
    },
  });
}

export function useUpdateDisciplinary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<HRDisciplinaryCase>(API.hrDisciplinaryCase(id), { method: "PATCH", body }),
    onSuccess: (row) => {
      qc.invalidateQueries({ queryKey: ["hr", "disciplinary"] });
      if (row?.employee_id)
        qc.invalidateQueries({ queryKey: ["hr", "employee", row.employee_id] });
    },
  });
}

export function useGrievanceList(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "grievance", qs],
    queryFn: () =>
      apiFetch<Paginated<HRGrievance>>(`${API.hrGrievances}${qs ? `?${qs}` : ""}`),
    staleTime: STALE,
  });
}

export function useGrievance(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "grievance", "one", id],
    queryFn: () => apiFetch<HRGrievance>(API.hrGrievance(id!)),
    enabled: !!id,
  });
}

export function useCreateGrievance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<HRGrievance>(API.hrGrievances, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "grievance"] }),
  });
}

export function useUpdateGrievance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<HRGrievance>(API.hrGrievance(id), { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "grievance"] }),
  });
}

// ── Analytics & audit trail (Phase 3) ─────────────────────────────────────

export function useHRAnalytics(months = 12) {
  return useQuery({
    queryKey: ["hr", "analytics", months],
    queryFn: () =>
      apiFetch<import("@/lib/types").HRAnalytics>(`${API.hrAnalytics}?months=${months}`),
    staleTime: STALE,
  });
}

export function useAuditLog(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "audit", qs],
    queryFn: () =>
      apiFetch<Paginated<import("@/lib/types").HRAuditEntry>>(
        `${API.hrAudit}${qs ? `?${qs}` : ""}`,
      ),
    staleTime: STALE,
  });
}

// ── Policy library (Phase 3) ──────────────────────────────────────────────

export function usePolicies(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "policies", qs],
    queryFn: () =>
      apiFetch<Paginated<import("@/lib/types").HRPolicy>>(
        `${API.hrPolicies}${qs ? `?${qs}` : ""}`,
      ),
    staleTime: STALE,
  });
}

export function usePolicyAcks(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "policy", id, "acks"],
    queryFn: () =>
      apiFetch<{ policy_id: string; title: string; rows: import("@/lib/types").HRPolicyAckRow[] }>(
        API.hrPolicyAcks(id!),
      ),
    enabled: !!id,
  });
}

export function useCreatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (form: FormData) =>
      apiUpload<import("@/lib/types").HRPolicy>(API.hrPolicies, form),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "policies"] }),
  });
}

export function useUpdatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<import("@/lib/types").HRPolicy>(API.hrPolicy(id), { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "policies"] }),
  });
}

export function useDeletePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch(API.hrPolicy(id), { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "policies"] }),
  });
}

// ── My HR: policies & reviews ─────────────────────────────────────────────

export function useMyPolicies() {
  return useQuery({
    queryKey: ["my-hr", "policies"],
    queryFn: () => apiFetch<import("@/lib/types").MyPolicies>(API.hrMePolicies),
    staleTime: STALE,
  });
}

export function useAcknowledgePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(API.hrMePolicyAcknowledge(id), { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-hr", "policies"] }),
  });
}

export function useMyReviews() {
  return useQuery({
    queryKey: ["my-hr", "reviews"],
    queryFn: () => apiFetch<HRPerformanceReview[]>(API.hrMeReviews),
    staleTime: STALE,
  });
}

export function useUpdateMyReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      apiFetch<HRPerformanceReview>(API.hrMeReview(id), { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-hr", "reviews"] }),
  });
}

// ── Payroll ─────────────────────────────────────────────────────────────

export function useHRPayslips(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "payslips", qs],
    queryFn: () =>
      apiFetch<Paginated<import("@/lib/types").PayslipRow>>(
        `${API.hrPayslips}${qs ? `?${qs}` : ""}`,
      ),
    staleTime: STALE,
  });
}

export function useHRPayslip(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "payslip", id],
    queryFn: () => apiFetch<import("@/lib/types").PayslipDetail>(API.hrPayslip(id!)),
    enabled: !!id,
  });
}

export function useGeneratePayslips() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch(API.hrPayslipGenerate, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "payslips"] }),
  });
}

export function usePayslipAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action, body }: { id: string; action: string; body?: Record<string, unknown> }) =>
      apiFetch(API.hrPayslipAction(id, action), { method: "POST", body: body ?? {} }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "payslips"] });
      qc.invalidateQueries({ queryKey: ["hr", "payslip"] });
    },
  });
}

export function usePayrollCategories() {
  return useQuery({
    queryKey: ["hr", "payroll", "categories"],
    queryFn: () =>
      apiFetch<import("@/lib/types").PayrollCategory[]>(API.hrPayrollCategories),
    staleTime: STALE,
  });
}

export function useSavePayrollCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Record<string, unknown> }) =>
      apiFetch(id ? API.hrPayrollCategory(id) : API.hrPayrollCategories, {
        method: id ? "PATCH" : "POST",
        body,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "payroll", "categories"] }),
  });
}

export function usePayrollGroups() {
  return useQuery({
    queryKey: ["hr", "payroll", "groups"],
    queryFn: () =>
      apiFetch<import("@/lib/types").PayrollGroup[]>(API.hrPayrollGroups),
    staleTime: STALE,
  });
}

export function useSavePayrollGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Record<string, unknown> }) =>
      apiFetch(id ? API.hrPayrollGroup(id) : API.hrPayrollGroups, {
        method: id ? "PATCH" : "POST",
        body,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "payroll", "groups"] }),
  });
}

export function usePayrollGroupComponents() {
  const qc = useQueryClient();
  return {
    add: useMutation({
      mutationFn: ({ groupId, body }: { groupId: string; body: Record<string, unknown> }) =>
        apiFetch(API.hrPayrollGroupComponents(groupId), { method: "POST", body }),
      onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "payroll", "groups"] }),
    }),
    remove: useMutation({
      mutationFn: ({ groupId, componentId }: { groupId: string; componentId: string }) =>
        apiFetch(API.hrPayrollGroupComponent(groupId, componentId), { method: "DELETE" }),
      onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "payroll", "groups"] }),
    }),
  };
}

export function useEmployeePayroll(id: string | undefined) {
  return useQuery({
    queryKey: ["hr", "employee", id, "payroll"],
    queryFn: () => apiFetch<import("@/lib/types").EmployeePayroll>(API.hrEmployeePayroll(id!)),
    enabled: !!id,
  });
}

export function useSaveEmployeePayroll(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch(API.hrEmployeePayroll(id), { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hr", "employee", id, "payroll"] }),
  });
}

export function useMyPayslips() {
  return useQuery({
    queryKey: ["my-hr", "payslips"],
    queryFn: () => apiFetch<import("@/lib/types").PayslipRow[]>(API.hrMePayslips),
    staleTime: STALE,
  });
}

export function useMyPayslip(id: string | undefined) {
  return useQuery({
    queryKey: ["my-hr", "payslip", id],
    queryFn: () => apiFetch<import("@/lib/types").PayslipDetail>(API.hrMePayslip(id!)),
    enabled: !!id,
  });
}

export function useMyLeaveBalance() {
  return useQuery({
    queryKey: ["my-hr", "leave-balance"],
    queryFn: () =>
      apiFetch<import("@/lib/types").LeaveBalanceEntry[]>(API.hrMeLeaveBalance),
    staleTime: STALE,
  });
}

// ── HR: leave calendar & balances ────────────────────────────────────────

export function useLeaveCalendar(params: Record<string, string>) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "leave-calendar", qs],
    queryFn: async () => {
      const res = await apiFetch<{
        from: string;
        to: string;
        entries: import("@/lib/types").LeaveCalendarEntry[];
      }>(`${API.hrLeaveCalendar}${qs ? `?${qs}` : ""}`);
      return res.entries;
    },
    staleTime: STALE,
  });
}

export function useLeaveBalances(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v != null),
  ).toString();
  return useQuery({
    queryKey: ["hr", "leave-balances", qs],
    queryFn: () =>
      apiFetch<import("@/lib/types").EmployeeLeaveBalances[]>(
        `${API.hrLeaveBalances}${qs ? `?${qs}` : ""}`,
      ),
    staleTime: STALE,
  });
}

// ── HR settings ─────────────────────────────────────────────────────────

export function useHRLookup(key: string) {
  return useQuery({
    queryKey: ["hr", "settings", "lookup", key],
    queryFn: () =>
      apiFetch<import("@/lib/types").HRLookup[]>(API.hrSettingsLookup(key)),
    staleTime: STALE,
  });
}

export function useSaveHRLookup(key: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Record<string, unknown> }) =>
      apiFetch<import("@/lib/types").HRLookup>(
        id ? API.hrSettingsLookupItem(key, id) : API.hrSettingsLookup(key),
        { method: id ? "PATCH" : "POST", body },
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["hr", "settings", "lookup", key] }),
  });
}

export function useDeleteHRLookup(key: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(API.hrSettingsLookupItem(key, id), { method: "DELETE" }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["hr", "settings", "lookup", key] }),
  });
}

export function useHRWorkingDays() {
  return useQuery({
    queryKey: ["hr", "settings", "working-days"],
    queryFn: () =>
      apiFetch<import("@/lib/types").HRWorkingDaySettings>(API.hrSettingsWorkingDays),
    staleTime: STALE,
  });
}

export function useSaveHRWorkingDays() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch(API.hrSettingsWorkingDays, { method: "PATCH", body }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["hr", "settings", "working-days"] }),
  });
}

export function useHRDocumentTypes() {
  return useQuery({
    queryKey: ["hr", "settings", "document-types"],
    queryFn: () =>
      apiFetch<{ required_document_types: string[] }>(API.hrSettingsDocumentTypes),
    staleTime: STALE,
  });
}

export function useSaveHRDocumentTypes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (required_document_types: string[]) =>
      apiFetch(API.hrSettingsDocumentTypes, {
        method: "PUT",
        body: { required_document_types },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "settings", "document-types"] });
      qc.invalidateQueries({ queryKey: ["hr", "dashboard"] });
    },
  });
}
