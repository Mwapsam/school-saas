"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import {
  useHREmployee, useHREmployeeContracts, useHREmployeeDocuments,
  useHREmployeeHistory, useHREmployeeAttendance, useHREmployeeQualifications,
  useCreateContract, useUploadDocument, useDeleteDocument, useAddQualification,
  useEmployeeOnboarding, useToggleOnboardingItem, useEmployeeReviews,
  useEmployeeTraining, useEmployeeExit, useStartExit, useUpdateExit,
  useToggleExitItem, useCompleteExit, useHRCan,
  useEmployeePayroll, useSaveEmployeePayroll, usePayrollGroups,
  useEmployeeDisciplinary,
} from "@/hooks/use-hr";
import { Textarea } from "@/components/ui/textarea";
import Link from "next/link";
import { Checkbox } from "@/components/ui/checkbox";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-sm">{value || "—"}</p>
    </div>
  );
}

const CONTRACT_TYPES = [
  ["permanent", "Permanent"], ["fixed_term", "Fixed Term"], ["probation", "Probation"],
  ["temporary", "Temporary"], ["casual", "Casual"], ["consultant", "Consultant / Contract"],
  ["intern", "Internship"],
] as const;

export default function HREmployeeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: emp, isLoading, isError, refetch } = useHREmployee(id);

  if (isError) {
    return (
      <>
        <PageHeader title="Employee" />
        <ErrorState onRetry={() => refetch()} />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={isLoading ? "Loading…" : emp?.full_name ?? "Employee"}
        description={emp ? `${emp.employee_number} · ${emp.department ?? "No department"}` : undefined}
        actions={emp ? (
          <Badge variant="secondary">{emp.employment_status.replace("_", " ")}</Badge>
        ) : undefined}
      />

      {isLoading || !emp ? (
        <Skeleton className="h-96" />
      ) : (
        <Tabs defaultValue="personal">
          <TabsList className="flex-wrap">
            <TabsTrigger value="personal">Personal</TabsTrigger>
            <TabsTrigger value="employment">Employment</TabsTrigger>
            <TabsTrigger value="contract">Contract</TabsTrigger>
            <TabsTrigger value="onboarding">Onboarding</TabsTrigger>
            <TabsTrigger value="qualifications">Qualifications</TabsTrigger>
            <TabsTrigger value="documents">Documents</TabsTrigger>
            <TabsTrigger value="performance">Performance</TabsTrigger>
            <TabsTrigger value="training">Training</TabsTrigger>
            <TabsTrigger value="attendance">Attendance</TabsTrigger>
            <TabsTrigger value="disciplinary">Disciplinary</TabsTrigger>
            <TabsTrigger value="payroll">Payroll</TabsTrigger>
            <TabsTrigger value="exit">Exit</TabsTrigger>
            <TabsTrigger value="history">History</TabsTrigger>
          </TabsList>

          <TabsContent value="personal">
            <Card><CardContent className="grid gap-6 p-6 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="Full name" value={emp.full_name} />
              <Field label="Employee number" value={emp.employee_number} />
              <Field label="NRC / Passport" value={emp.national_id} />
              <Field label="Date of birth" value={emp.date_of_birth} />
              <Field label="Gender" value={emp.gender_label} />
              <Field label="Mobile" value={emp.mobile_phone} />
              <Field label="Email" value={emp.email} />
              <Field label="Marital status" value={emp.marital_status} />
              <Field label="Blood group" value={emp.blood_group} />
              <Field label="Address" value={[emp.home_address_line1, emp.home_city].filter(Boolean).join(", ")} />
              <Field label="Emergency contact" value={emp.emergency_contact_name && `${emp.emergency_contact_name} (${emp.emergency_contact_phone ?? "—"})`} />
              <Field label="Next of kin" value={emp.next_of_kin_name && `${emp.next_of_kin_name} (${emp.next_of_kin_relation ?? "—"})`} />
            </CardContent></Card>
          </TabsContent>

          <TabsContent value="employment">
            <Card><CardContent className="grid gap-6 p-6 sm:grid-cols-2 lg:grid-cols-3">
              <Field label="Job title" value={emp.job_title} />
              <Field label="Department" value={emp.department} />
              <Field label="Position" value={emp.position} />
              <Field label="Category" value={emp.category} />
              <Field label="Grade" value={emp.grade} />
              <Field label="Reporting manager" value={emp.reporting_manager_name} />
              <Field label="Date joined" value={emp.joining_date} />
              <Field label="Staff type" value={emp.is_teaching_staff ? "Teaching" : "Non-teaching"} />
              <Field label="Employment status" value={emp.employment_status.replace("_", " ")} />
              <Field label="Experience" value={emp.experience_year != null ? `${emp.experience_year}y ${emp.experience_month ?? 0}m` : null} />
              <Field label="Highest qualification" value={emp.qualification} />
            </CardContent></Card>
          </TabsContent>

          <TabsContent value="contract"><ContractTab id={id} /></TabsContent>
          <TabsContent value="onboarding"><OnboardingTab id={id} /></TabsContent>
          <TabsContent value="qualifications"><QualificationsTab id={id} /></TabsContent>
          <TabsContent value="documents"><DocumentsTab id={id} /></TabsContent>
          <TabsContent value="performance"><PerformanceTab id={id} /></TabsContent>
          <TabsContent value="training"><TrainingTab id={id} /></TabsContent>
          <TabsContent value="attendance"><AttendanceTab id={id} /></TabsContent>
          <TabsContent value="disciplinary"><DisciplinaryTab id={id} /></TabsContent>
          <TabsContent value="payroll"><PayrollTab id={id} /></TabsContent>
          <TabsContent value="exit"><ExitTab id={id} /></TabsContent>
          <TabsContent value="history"><HistoryTab id={id} /></TabsContent>
        </Tabs>
      )}
    </>
  );
}

function ContractTab({ id }: { id: string }) {
  const { data, isLoading } = useHREmployeeContracts(id);
  const create = useCreateContract(id);
  const canManage = useHRCan("hr.contract.manage");
  const [f, setF] = React.useState({ contract_type: "fixed_term", start_date: "", end_date: "", probation_end_date: "" });

  return (
    <div className="space-y-6">
      {isLoading ? (
        <Skeleton className="h-40" />
      ) : !data?.length ? (
        <p className="text-sm text-muted-foreground">No contracts recorded.</p>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Type</TableHead><TableHead>Start</TableHead><TableHead>End</TableHead>
              <TableHead>Days left</TableHead><TableHead>Status</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {data.map((c) => (
                <TableRow key={c.id}>
                  <TableCell>{c.contract_type_label}</TableCell>
                  <TableCell>{c.start_date}</TableCell>
                  <TableCell>{c.end_date ?? "Open-ended"}</TableCell>
                  <TableCell>{c.days_remaining ?? "—"}</TableCell>
                  <TableCell><Badge variant="outline">{c.renewal_status.replace("_", " ")}</Badge></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {canManage ? (
        <Card><CardContent className="p-4">
          <p className="mb-3 text-sm font-medium">Add contract</p>
          <form
            className="grid gap-3 sm:grid-cols-4"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate(
                {
                  contract_type: f.contract_type,
                  start_date: f.start_date,
                  end_date: f.end_date || null,
                  probation_end_date: f.probation_end_date || null,
                },
                {
                  onSuccess: () => { setF({ contract_type: "fixed_term", start_date: "", end_date: "", probation_end_date: "" }); toast.success("Contract added"); },
                  onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
                },
              );
            }}
          >
            <div className="space-y-1">
              <Label>Type</Label>
              <Select value={f.contract_type} onValueChange={(v) => setF((p) => ({ ...p, contract_type: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CONTRACT_TYPES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Start</Label>
              <Input type="date" required value={f.start_date} onChange={(e) => setF((p) => ({ ...p, start_date: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <Label>End</Label>
              <Input type="date" value={f.end_date} onChange={(e) => setF((p) => ({ ...p, end_date: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <Label>Probation end</Label>
              <Input type="date" value={f.probation_end_date} onChange={(e) => setF((p) => ({ ...p, probation_end_date: e.target.value }))} />
            </div>
            <div className="sm:col-span-4">
              <Button type="submit" size="sm" disabled={create.isPending}>Add contract</Button>
            </div>
          </form>
        </CardContent></Card>
      ) : null}
    </div>
  );
}

const EXIT_TYPES = [
  ["resignation", "Resignation"], ["termination", "Termination"],
  ["retirement", "Retirement"], ["end_of_contract", "End of Contract"],
  ["redundancy", "Redundancy"], ["death", "Death in Service"], ["other", "Other"],
] as const;

function ExitTab({ id }: { id: string }) {
  const { data, isLoading, error } = useEmployeeExit(id);
  const start = useStartExit(id);
  const update = useUpdateExit(id);
  const toggle = useToggleExitItem(id);
  const complete = useCompleteExit(id);
  const canManage = useHRCan("hr.exit.manage");

  const [s, setS] = React.useState({ exit_type: "resignation", notice_date: "", last_working_date: "", reason: "" });

  if (isLoading) return <Skeleton className="h-64" />;

  // 404 => no exit record yet
  if (error || !data) {
    if (!canManage) return <p className="p-6 text-sm text-muted-foreground">No exit record.</p>;
    return (
      <Card><CardContent className="p-6">
        <p className="mb-3 text-sm font-medium">Start offboarding</p>
        <form
          className="grid gap-3 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            start.mutate(
              { ...s, notice_date: s.notice_date || null, last_working_date: s.last_working_date || null },
              {
                onSuccess: () => toast.success("Exit started"),
                onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
              },
            );
          }}
        >
          <div className="space-y-1">
            <Label>Exit type</Label>
            <Select value={s.exit_type} onValueChange={(v) => setS((p) => ({ ...p, exit_type: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {EXIT_TYPES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Notice date</Label>
            <Input type="date" value={s.notice_date} onChange={(e) => setS((p) => ({ ...p, notice_date: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Last working date</Label>
            <Input type="date" value={s.last_working_date} onChange={(e) => setS((p) => ({ ...p, last_working_date: e.target.value }))} />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label>Reason</Label>
            <Textarea value={s.reason} onChange={(e) => setS((p) => ({ ...p, reason: e.target.value }))} />
          </div>
          <div className="sm:col-span-2">
            <Button type="submit" disabled={start.isPending}>Start exit</Button>
          </div>
        </form>
      </CardContent></Card>
    );
  }

  const locked = data.status === "completed" || !canManage;

  return (
    <div className="space-y-6">
      <Card><CardContent className="grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Exit type" value={data.exit_type_label} />
        <Field label="Notice date" value={data.notice_date} />
        <Field label="Last working date" value={data.last_working_date} />
        <Field label="Handover" value={data.handover_status.replace("_", " ")} />
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Final payment</p>
          <Select
            value={data.final_payment_status}
            disabled={locked}
            onValueChange={(v) => update.mutate({ id: data.id, body: { final_payment_status: v } })}
          >
            <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="processing">Processing</SelectItem>
              <SelectItem value="paid">Paid</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Field label="Status" value={<Badge variant="outline">{data.status_label}</Badge>} />
      </CardContent></Card>

      <Card><CardContent className="p-6">
        <div className="mb-4 flex items-center gap-3">
          <div className="h-2 w-48 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary" style={{ width: `${data.progress.percent}%` }} />
          </div>
          <span className="text-sm font-medium">
            {data.progress.done}/{data.progress.total} clearance items
          </span>
        </div>
        <ul className="space-y-2">
          {data.clearance_items.map((it) => (
            <li key={it.id} className="flex items-center gap-3 text-sm">
              <Checkbox
                checked={it.is_done}
                disabled={locked || toggle.isPending}
                onCheckedChange={(v) => toggle.mutate({ id: it.id, is_done: Boolean(v) })}
              />
              <span className={it.is_done ? "text-muted-foreground line-through" : ""}>{it.label}</span>
            </li>
          ))}
        </ul>
        {!locked ? (
          <Button
            className="mt-4"
            disabled={complete.isPending || data.progress.done < data.progress.total}
            onClick={() =>
              complete.mutate(data.id, {
                onSuccess: () => toast.success("Exit finalised — employee marked as former"),
                onError: (e: unknown) => toast.error((e as Error).message ?? "Failed"),
              })
            }
          >
            Finalise exit
          </Button>
        ) : null}
      </CardContent></Card>
    </div>
  );
}

function TrainingTab({ id }: { id: string }) {
  const { data, isLoading } = useEmployeeTraining(id);
  if (isLoading) return <Skeleton className="h-40" />;
  if (!data?.length) return <p className="p-6 text-sm text-muted-foreground">No training records.</p>;
  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader><TableRow>
          <TableHead>Training</TableHead><TableHead>Category</TableHead>
          <TableHead>Date</TableHead><TableHead>Expiry</TableHead><TableHead>Status</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {data.map((t) => (
            <TableRow key={t.id}>
              <TableCell>
                {t.name}
                {t.is_mandatory ? <Badge variant="outline" className="ml-2">Mandatory</Badge> : null}
              </TableCell>
              <TableCell>{t.category_label}</TableCell>
              <TableCell>{t.training_date ?? "—"}</TableCell>
              <TableCell>{t.expiry_date ?? "—"}</TableCell>
              <TableCell>
                <Badge variant={t.compliance_status === "expired" ? "destructive" : t.compliance_status === "expiring" ? "secondary" : "outline"}>
                  {t.compliance_status}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function PerformanceTab({ id }: { id: string }) {
  const { data, isLoading } = useEmployeeReviews(id);
  if (isLoading) return <Skeleton className="h-40" />;
  if (!data?.length) return <p className="p-6 text-sm text-muted-foreground">No performance reviews yet.</p>;
  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader><TableRow>
          <TableHead>Period</TableHead><TableHead>Date</TableHead>
          <TableHead>Reviewer</TableHead><TableHead>Rating</TableHead><TableHead>Status</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {data.map((r) => (
            <TableRow key={r.id}>
              <TableCell>
                <Link href={`/hr/performance/${r.id}`} className="font-medium hover:underline">
                  {r.review_period}
                </Link>
              </TableCell>
              <TableCell>{r.review_date}</TableCell>
              <TableCell>{r.reviewer_name ?? "—"}</TableCell>
              <TableCell>{r.overall_rating != null ? `${r.overall_rating}/5` : "—"}</TableCell>
              <TableCell><Badge variant="outline">{r.status_label}</Badge></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function OnboardingTab({ id }: { id: string }) {
  const { data, isLoading } = useEmployeeOnboarding(id);
  const toggle = useToggleOnboardingItem(id);
  const canManage = useHRCan("hr.onboarding.manage");

  if (isLoading || !data) return <Skeleton className="h-64" />;

  return (
    <Card><CardContent className="p-6">
      <div className="mb-4 flex items-center gap-3">
        <div className="h-2 w-48 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary" style={{ width: `${data.progress.percent}%` }} />
        </div>
        <span className="text-sm font-medium">
          {data.progress.done}/{data.progress.total} · {data.progress.percent}% complete
        </span>
        {data.completed_at ? <Badge variant="secondary">Done</Badge> : null}
      </div>
      <ul className="space-y-2">
        {data.items.map((it) => (
          <li key={it.id} className="flex items-center gap-3 text-sm">
            <Checkbox
              checked={it.is_done}
              disabled={!canManage || toggle.isPending}
              onCheckedChange={(v) =>
                toggle.mutate(
                  { id: it.id, is_done: Boolean(v) },
                  { onError: (e: unknown) => toast.error((e as Error).message ?? "Failed") },
                )
              }
            />
            <span className={it.is_done ? "text-muted-foreground line-through" : ""}>{it.label}</span>
          </li>
        ))}
      </ul>
    </CardContent></Card>
  );
}

function QualificationsTab({ id }: { id: string }) {
  const { data, isLoading } = useHREmployeeQualifications(id);
  const add = useAddQualification(id);
  const canManage = useHRCan("hr.employee.manage");
  const [f, setF] = React.useState({ qualification_type: "academic", name: "", institution: "", year_obtained: "" });

  return (
    <div className="space-y-6">
      {isLoading ? (
        <Skeleton className="h-32" />
      ) : !data?.length ? (
        <p className="text-sm text-muted-foreground">No qualifications recorded.</p>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Type</TableHead><TableHead>Name</TableHead>
              <TableHead>Institution</TableHead><TableHead>Year</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {data.map((q) => (
                <TableRow key={q.id}>
                  <TableCell className="capitalize">{q.qualification_type}</TableCell>
                  <TableCell>{q.name}{q.is_highest ? <Badge variant="secondary" className="ml-2">Highest</Badge> : null}</TableCell>
                  <TableCell>{q.institution || "—"}</TableCell>
                  <TableCell>{q.year_obtained ?? "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {canManage ? (
        <Card><CardContent className="p-4">
          <p className="mb-3 text-sm font-medium">Add qualification</p>
          <form
            className="grid gap-3 sm:grid-cols-4"
            onSubmit={(e) => {
              e.preventDefault();
              add.mutate(
                {
                  qualification_type: f.qualification_type,
                  name: f.name,
                  institution: f.institution,
                  year_obtained: f.year_obtained ? Number(f.year_obtained) : null,
                },
                {
                  onSuccess: () => { setF({ qualification_type: "academic", name: "", institution: "", year_obtained: "" }); toast.success("Added"); },
                  onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
                },
              );
            }}
          >
            <div className="space-y-1">
              <Label>Type</Label>
              <Select value={f.qualification_type} onValueChange={(v) => setF((p) => ({ ...p, qualification_type: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="academic">Academic</SelectItem>
                  <SelectItem value="teaching">Teaching</SelectItem>
                  <SelectItem value="professional">Professional</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Name</Label>
              <Input required value={f.name} onChange={(e) => setF((p) => ({ ...p, name: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <Label>Institution</Label>
              <Input value={f.institution} onChange={(e) => setF((p) => ({ ...p, institution: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <Label>Year</Label>
              <Input type="number" value={f.year_obtained} onChange={(e) => setF((p) => ({ ...p, year_obtained: e.target.value }))} />
            </div>
            <div className="sm:col-span-4">
              <Button type="submit" size="sm" disabled={add.isPending}>Add</Button>
            </div>
          </form>
        </CardContent></Card>
      ) : null}
    </div>
  );
}

function DocumentsTab({ id }: { id: string }) {
  const { data, isLoading } = useHREmployeeDocuments(id);
  const upload = useUploadDocument(id);
  const del = useDeleteDocument(id);
  const canManage = useHRCan("hr.document.manage");
  const [docType, setDocType] = React.useState("");
  const [expiry, setExpiry] = React.useState("");
  const fileRef = React.useRef<HTMLInputElement>(null);

  return (
    <div className="space-y-6">
      {isLoading ? (
        <Skeleton className="h-40" />
      ) : !data?.length ? (
        <p className="text-sm text-muted-foreground">No documents uploaded.</p>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Type</TableHead><TableHead>Uploaded</TableHead>
              <TableHead>Expiry</TableHead><TableHead>Status</TableHead><TableHead></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {data.map((d) => (
                <TableRow key={d.id}>
                  <TableCell>{d.document_type}</TableCell>
                  <TableCell>{d.uploaded_at.slice(0, 10)}</TableCell>
                  <TableCell>{d.expiry_date ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant={d.status === "expired" ? "destructive" : d.status === "expiring" ? "secondary" : "outline"}>
                      {d.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="space-x-2 text-right">
                    {d.file_url ? <a href={d.file_url} className="text-sm underline" target="_blank" rel="noreferrer">Open</a> : null}
                    {canManage ? (
                      <button
                        className="text-sm text-destructive hover:underline"
                        onClick={() => del.mutate(d.id, { onSuccess: () => toast.success("Removed") })}
                      >
                        Delete
                      </button>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {canManage ? (
        <Card><CardContent className="p-4">
          <p className="mb-3 text-sm font-medium">Upload document</p>
          <form
            className="grid gap-3 sm:grid-cols-4"
            onSubmit={(e) => {
              e.preventDefault();
              const file = fileRef.current?.files?.[0];
              if (!file || !docType) { toast.error("Pick a file and a type"); return; }
              const form = new FormData();
              form.append("file", file);
              form.append("document_type", docType);
              if (expiry) form.append("expiry_date", expiry);
              upload.mutate(form, {
                onSuccess: () => {
                  setDocType(""); setExpiry("");
                  if (fileRef.current) fileRef.current.value = "";
                  toast.success("Uploaded");
                },
                onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
              });
            }}
          >
            <div className="space-y-1">
              <Label>Document type</Label>
              <Input value={docType} onChange={(e) => setDocType(e.target.value)} placeholder="e.g. NRC / Passport" />
            </div>
            <div className="space-y-1">
              <Label>Expiry (optional)</Label>
              <Input type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label>File</Label>
              <Input type="file" ref={fileRef} />
            </div>
            <div className="sm:col-span-4">
              <Button type="submit" size="sm" disabled={upload.isPending}>Upload</Button>
            </div>
          </form>
        </CardContent></Card>
      ) : null}
    </div>
  );
}

function AttendanceTab({ id }: { id: string }) {
  const { data, isLoading } = useHREmployeeAttendance(id);
  if (isLoading) return <Skeleton className="h-40" />;
  const s = data?.summary ?? {};
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-4">
        {["present", "absent", "late", "on_leave"].map((k) => (
          <Card key={k}><CardContent className="p-4">
            <p className="text-xs uppercase text-muted-foreground">{k.replace("_", " ")}</p>
            <p className="text-2xl font-semibold">{s[k] ?? 0}</p>
          </CardContent></Card>
        ))}
      </div>
      <p className="text-sm text-muted-foreground">
        Attendance rate: {s.attendance_rate != null ? `${s.attendance_rate}%` : "—"} (last 90 days)
      </p>
      <div className="rounded-lg border">
        <Table>
          <TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Status</TableHead><TableHead>Remarks</TableHead></TableRow></TableHeader>
          <TableBody>
            {(data?.records ?? []).slice(0, 60).map((r) => (
              <TableRow key={r.id}>
                <TableCell>{r.date}</TableCell>
                <TableCell>{r.status_label}</TableCell>
                <TableCell className="text-muted-foreground">{r.remarks ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function HistoryTab({ id }: { id: string }) {
  const { data, isLoading } = useHREmployeeHistory(id);
  if (isLoading) return <Skeleton className="h-40" />;
  if (!data?.length) return <p className="p-6 text-sm text-muted-foreground">No employment history recorded yet.</p>;
  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader><TableRow>
          <TableHead>Date</TableHead><TableHead>Event</TableHead>
          <TableHead>From</TableHead><TableHead>To</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {data.map((h) => (
            <TableRow key={h.id}>
              <TableCell>{h.effective_date}</TableCell>
              <TableCell>{h.event_type_label}</TableCell>
              <TableCell className="text-muted-foreground">{h.old_value ? Object.values(h.old_value).join(", ") : "—"}</TableCell>
              <TableCell>{h.new_value ? Object.values(h.new_value).join(", ") : "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function DisciplinaryTab({ id }: { id: string }) {
  const canView = useHRCan("hr.disciplinary.view");
  const { data, isLoading } = useEmployeeDisciplinary(canView ? id : undefined);
  if (!canView) {
    return (
      <p className="p-6 text-sm text-muted-foreground">
        Restricted — you need the “View disciplinary records” permission.
      </p>
    );
  }
  if (isLoading) return <Skeleton className="h-40" />;
  const rows = data?.results ?? [];
  if (!rows.length) {
    return <p className="p-6 text-sm text-muted-foreground">No disciplinary cases on record.</p>;
  }
  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader><TableRow>
          <TableHead>Title</TableHead><TableHead>Type</TableHead>
          <TableHead>Severity</TableHead><TableHead>Outcome</TableHead>
          <TableHead>Status</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {rows.map((c) => (
            <TableRow key={c.id}>
              <TableCell className="font-medium">
                <Link href="/hr/relations" className="hover:underline">{c.title}</Link>
              </TableCell>
              <TableCell>{c.case_type_label ?? c.case_type}</TableCell>
              <TableCell><Badge variant="outline">{c.severity}</Badge></TableCell>
              <TableCell>{c.outcome ?? "—"}</TableCell>
              <TableCell><Badge variant="secondary">{c.status}</Badge></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function PayrollTab({ id }: { id: string }) {
  const canView = useHRCan("hr.payroll.view");
  const canManage = useHRCan("hr.payroll.manage");
  const { data, isLoading } = useEmployeePayroll(canView ? id : undefined);
  const groups = usePayrollGroups().data ?? [];
  const save = useSaveEmployeePayroll(id);
  const [f, setF] = React.useState<Record<string, string>>({});

  React.useEffect(() => {
    if (data?.profile) {
      setF({
        payroll_group_id: data.profile.payroll_group_id ?? "",
        basic_pay_amount: String(data.profile.basic_pay_amount ?? ""),
        bank_name: data.profile.bank_name ?? "",
        bank_account_number: data.profile.bank_account_number ?? "",
        bank_branch: data.profile.bank_branch ?? "",
        effective_date: data.profile.effective_date ?? "",
      });
    }
  }, [data]);

  if (!canView) {
    return (
      <p className="p-6 text-sm text-muted-foreground">
        Restricted — you need the “View payroll &amp; payslips” permission.
      </p>
    );
  }
  if (isLoading) return <Skeleton className="h-40" />;

  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));
  const payslips = data?.payslips ?? [];

  return (
    <div className="space-y-6">
      <Card><CardContent className="grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-3">
        <div className="space-y-1">
          <Label>Payroll group</Label>
          <Select value={f.payroll_group_id ?? ""} onValueChange={(v) => set("payroll_group_id", v)} disabled={!canManage}>
            <SelectTrigger><SelectValue placeholder="Unassigned" /></SelectTrigger>
            <SelectContent>
              {groups.map((g) => <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label>Basic pay</Label>
          <Input type="number" value={f.basic_pay_amount ?? ""} disabled={!canManage}
            onChange={(e) => set("basic_pay_amount", e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Effective date</Label>
          <Input type="date" value={f.effective_date ?? ""} disabled={!canManage}
            onChange={(e) => set("effective_date", e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Bank name</Label>
          <Input value={f.bank_name ?? ""} disabled={!canManage}
            onChange={(e) => set("bank_name", e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Account number</Label>
          <Input value={f.bank_account_number ?? ""} disabled={!canManage}
            onChange={(e) => set("bank_account_number", e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Branch</Label>
          <Input value={f.bank_branch ?? ""} disabled={!canManage}
            onChange={(e) => set("bank_branch", e.target.value)} />
        </div>
        {canManage && (
          <div className="sm:col-span-2 lg:col-span-3">
            <Button
              disabled={save.isPending}
              onClick={() =>
                save.mutate(
                  {
                    ...f,
                    payroll_group_id: f.payroll_group_id || null,
                    basic_pay_amount: Number(f.basic_pay_amount || 0),
                    effective_date: f.effective_date || null,
                  },
                  {
                    onSuccess: () => toast.success("Payroll profile saved"),
                    onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
                  },
                )
              }
            >
              Save payroll profile
            </Button>
          </div>
        )}
      </CardContent></Card>

      <div>
        <h3 className="mb-2 text-sm font-semibold">Payslips</h3>
        {payslips.length === 0 ? (
          <p className="text-sm text-muted-foreground">No payslips generated yet.</p>
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader><TableRow>
                <TableHead>Period</TableHead><TableHead>Gross</TableHead>
                <TableHead>Deductions</TableHead><TableHead>Net</TableHead>
                <TableHead>Status</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {payslips.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>
                      <Link href={`/hr/payroll/${p.id}`} className="hover:underline">
                        {p.period_start} → {p.period_end}
                      </Link>
                    </TableCell>
                    <TableCell>{p.gross_earnings}</TableCell>
                    <TableCell>{p.total_deductions}</TableCell>
                    <TableCell className="font-medium">{p.net_pay}</TableCell>
                    <TableCell><Badge variant="secondary">{p.status}</Badge></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}
