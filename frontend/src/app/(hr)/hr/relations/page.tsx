"use client";

import * as React from "react";
import { toast } from "sonner";

import {
  useDisciplinaryList, useCreateDisciplinary, useUpdateDisciplinary,
  useGrievanceList, useCreateGrievance, useUpdateGrievance,
  useHREmployees, useHRCan,
} from "@/hooks/use-hr";
import type { HRDisciplinaryCase, HRGrievance } from "@/lib/types";
import { PageHeader } from "@/components/page-header";
import { ErrorState, EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Sheet, SheetContent, SheetTitle,
} from "@/components/ui/sheet";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const CASE_TYPES = [
  ["misconduct", "Misconduct"],
  ["poor_performance", "Poor Performance"],
  ["attendance", "Attendance / Punctuality"],
  ["policy_breach", "Policy Breach"],
  ["insubordination", "Insubordination"],
  ["safeguarding", "Safeguarding Concern"],
  ["other", "Other"],
] as const;
const SEVERITIES = [
  ["minor", "Minor"], ["major", "Major"], ["gross", "Gross Misconduct"],
] as const;
const CASE_STATUSES = [
  ["open", "Open"],
  ["under_investigation", "Under Investigation"],
  ["hearing", "Hearing Scheduled"],
  ["action_taken", "Action Taken"],
  ["appealed", "Appealed"],
  ["closed", "Closed"],
] as const;
const OUTCOMES = [
  ["none", "No Outcome Yet"],
  ["no_action", "No Action / Cleared"],
  ["verbal_warning", "Verbal Warning"],
  ["written_warning", "Written Warning"],
  ["final_warning", "Final Written Warning"],
  ["suspension", "Suspension"],
  ["demotion", "Demotion"],
  ["dismissal", "Dismissal"],
] as const;
const GRIEVANCE_CATS = [
  ["harassment", "Harassment / Bullying"],
  ["discrimination", "Discrimination"],
  ["workload", "Workload / Working Hours"],
  ["pay", "Pay / Benefits"],
  ["management", "Management / Supervision"],
  ["working_conditions", "Working Conditions"],
  ["safeguarding", "Safeguarding Concern"],
  ["other", "Other"],
] as const;
const GRIEVANCE_STATUSES = [
  ["submitted", "Submitted"],
  ["under_review", "Under Review"],
  ["mediation", "Mediation"],
  ["resolved", "Resolved"],
  ["dismissed", "Dismissed"],
  ["escalated", "Escalated"],
] as const;

export default function RelationsPage() {
  const canView = useHRCan("hr.disciplinary.view");

  if (!canView) {
    return (
      <>
        <PageHeader title="Employee Relations" description="Disciplinary cases and grievances." />
        <EmptyState
          title="Restricted"
          description="You do not have permission to view employee relations records."
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Employee Relations"
        description="Disciplinary cases and grievances. Access is restricted and every change is logged."
      />
      <Tabs defaultValue="disciplinary">
        <TabsList>
          <TabsTrigger value="disciplinary">Disciplinary</TabsTrigger>
          <TabsTrigger value="grievances">Grievances</TabsTrigger>
        </TabsList>
        <TabsContent value="disciplinary" className="pt-4">
          <DisciplinaryPanel />
        </TabsContent>
        <TabsContent value="grievances" className="pt-4">
          <GrievancePanel />
        </TabsContent>
      </Tabs>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Disciplinary                                                        */
/* ------------------------------------------------------------------ */
function DisciplinaryPanel() {
  const canManage = useHRCan("hr.disciplinary.manage");
  const [status, setStatus] = React.useState("all");
  const [selected, setSelected] = React.useState<HRDisciplinaryCase | null>(null);
  const params: Record<string, string> = {};
  if (status !== "all") params.status = status;
  const { data, isLoading, isError, refetch } = useDisciplinaryList(params);
  const rows = data?.results ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-52"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {CASE_STATUSES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
        {canManage ? <NewCaseDialog /> : null}
      </div>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-72" />
      ) : rows.length === 0 ? (
        <EmptyState title="No cases" description="No disciplinary cases match." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Employee</TableHead><TableHead>Case</TableHead>
              <TableHead>Type</TableHead><TableHead>Severity</TableHead>
              <TableHead>Outcome</TableHead><TableHead>Status</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((c) => (
                <TableRow
                  key={c.id}
                  className="cursor-pointer"
                  onClick={() => setSelected(c)}
                >
                  <TableCell className="font-medium">{c.employee_name}</TableCell>
                  <TableCell>{c.title}</TableCell>
                  <TableCell>{c.case_type_label}</TableCell>
                  <TableCell>
                    <Badge variant={c.severity === "gross" ? "destructive" : "outline"}>
                      {c.severity_label}
                    </Badge>
                  </TableCell>
                  <TableCell>{c.outcome === "none" ? "—" : c.outcome_label}</TableCell>
                  <TableCell><Badge variant="outline">{c.status_label}</Badge></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <CaseSheet
        row={selected}
        canManage={canManage}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}

function NewCaseDialog() {
  const create = useCreateDisciplinary();
  const { data: employees } = useHREmployees({ page: "1", page_size: "300" });
  const [open, setOpen] = React.useState(false);
  const [f, setF] = React.useState({
    employee_id: "", case_type: "misconduct", severity: "minor",
    title: "", description: "", incident_date: "",
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button>New case</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New disciplinary case</DialogTitle></DialogHeader>
        <form
          className="grid gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const body: Record<string, unknown> = { ...f };
            if (!f.incident_date) delete body.incident_date;
            create.mutate(body, {
              onSuccess: () => { setOpen(false); toast.success("Case opened"); },
              onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
            });
          }}
        >
          <div className="space-y-1">
            <Label>Employee</Label>
            <Select value={f.employee_id} onValueChange={(v) => setF((p) => ({ ...p, employee_id: v }))}>
              <SelectTrigger><SelectValue placeholder="Choose employee" /></SelectTrigger>
              <SelectContent>
                {(employees?.results ?? []).map((e) => (
                  <SelectItem key={e.id} value={e.id}>{e.full_name} ({e.employee_number})</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Type</Label>
              <Select value={f.case_type} onValueChange={(v) => setF((p) => ({ ...p, case_type: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CASE_TYPES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Severity</Label>
              <Select value={f.severity} onValueChange={(v) => setF((p) => ({ ...p, severity: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {SEVERITIES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <Label>Title</Label>
            <Input required value={f.title}
              onChange={(e) => setF((p) => ({ ...p, title: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Incident date</Label>
            <Input type="date" value={f.incident_date}
              onChange={(e) => setF((p) => ({ ...p, incident_date: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Description</Label>
            <Textarea value={f.description}
              onChange={(e) => setF((p) => ({ ...p, description: e.target.value }))} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={create.isPending || !f.employee_id || !f.title}>
              Open case
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function CaseSheet({
  row, canManage, onClose,
}: {
  row: HRDisciplinaryCase | null;
  canManage: boolean;
  onClose: () => void;
}) {
  const update = useUpdateDisciplinary();
  const [f, setF] = React.useState<Record<string, string>>({});

  React.useEffect(() => {
    if (row) {
      setF({
        status: row.status,
        outcome: row.outcome,
        severity: row.severity,
        investigation_notes: row.investigation_notes ?? "",
        outcome_notes: row.outcome_notes ?? "",
        appeal_notes: row.appeal_notes ?? "",
        hearing_date: row.hearing_date ?? "",
        action_date: row.action_date ?? "",
        warning_expiry_date: row.warning_expiry_date ?? "",
      });
    }
  }, [row]);

  return (
    <Sheet open={!!row} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {row ? (
          <>
            <div className="space-y-1">
              <SheetTitle>{row.title}</SheetTitle>
            </div>
            <div className="mt-4 space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3 text-muted-foreground">
                <div><span className="text-foreground">Employee:</span> {row.employee_name}</div>
                <div><span className="text-foreground">Type:</span> {row.case_type_label}</div>
                <div><span className="text-foreground">Incident:</span> {row.incident_date ?? "—"}</div>
                <div><span className="text-foreground">Opened:</span> {row.created_at.slice(0, 10)}</div>
              </div>
              {row.description ? (
                <p className="whitespace-pre-wrap rounded-md bg-muted p-3">{row.description}</p>
              ) : null}

              {canManage ? (
                <form
                  className="space-y-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const body: Record<string, unknown> = { ...f };
                    ["hearing_date", "action_date", "warning_expiry_date"].forEach((k) => {
                      if (!body[k]) body[k] = null;
                    });
                    update.mutate(
                      { id: row.id, body },
                      {
                        onSuccess: () => { toast.success("Case updated"); onClose(); },
                        onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
                      },
                    );
                  }}
                >
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Status">
                      <Select value={f.status} onValueChange={(v) => setF((p) => ({ ...p, status: v }))}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {CASE_STATUSES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field label="Severity">
                      <Select value={f.severity} onValueChange={(v) => setF((p) => ({ ...p, severity: v }))}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {SEVERITIES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field label="Outcome">
                      <Select value={f.outcome} onValueChange={(v) => setF((p) => ({ ...p, outcome: v }))}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {OUTCOMES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field label="Hearing date">
                      <Input type="date" value={f.hearing_date}
                        onChange={(e) => setF((p) => ({ ...p, hearing_date: e.target.value }))} />
                    </Field>
                    <Field label="Action date">
                      <Input type="date" value={f.action_date}
                        onChange={(e) => setF((p) => ({ ...p, action_date: e.target.value }))} />
                    </Field>
                    <Field label="Warning expiry">
                      <Input type="date" value={f.warning_expiry_date}
                        onChange={(e) => setF((p) => ({ ...p, warning_expiry_date: e.target.value }))} />
                    </Field>
                  </div>
                  <Field label="Investigation notes">
                    <Textarea value={f.investigation_notes}
                      onChange={(e) => setF((p) => ({ ...p, investigation_notes: e.target.value }))} />
                  </Field>
                  <Field label="Outcome notes">
                    <Textarea value={f.outcome_notes}
                      onChange={(e) => setF((p) => ({ ...p, outcome_notes: e.target.value }))} />
                  </Field>
                  <Field label="Appeal notes">
                    <Textarea value={f.appeal_notes}
                      onChange={(e) => setF((p) => ({ ...p, appeal_notes: e.target.value }))} />
                  </Field>
                  <Button type="submit" disabled={update.isPending}>Save changes</Button>
                </form>
              ) : (
                <div className="space-y-2 text-muted-foreground">
                  <div><span className="text-foreground">Status:</span> {row.status_label}</div>
                  <div><span className="text-foreground">Outcome:</span> {row.outcome_label}</div>
                  {row.investigation_notes ? <p className="whitespace-pre-wrap">{row.investigation_notes}</p> : null}
                </div>
              )}
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

/* ------------------------------------------------------------------ */
/* Grievances                                                          */
/* ------------------------------------------------------------------ */
function GrievancePanel() {
  const canManage = useHRCan("hr.disciplinary.manage");
  const [status, setStatus] = React.useState("all");
  const [selected, setSelected] = React.useState<HRGrievance | null>(null);
  const params: Record<string, string> = {};
  if (status !== "all") params.status = status;
  const { data, isLoading, isError, refetch } = useGrievanceList(params);
  const rows = data?.results ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-52"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {GRIEVANCE_STATUSES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
        {canManage ? <NewGrievanceDialog /> : null}
      </div>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-72" />
      ) : rows.length === 0 ? (
        <EmptyState title="No grievances" description="No grievances match." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Raised by</TableHead><TableHead>Grievance</TableHead>
              <TableHead>Category</TableHead><TableHead>Against</TableHead>
              <TableHead>Status</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((g) => (
                <TableRow
                  key={g.id}
                  className="cursor-pointer"
                  onClick={() => setSelected(g)}
                >
                  <TableCell className="font-medium">{g.raised_by_name}</TableCell>
                  <TableCell>{g.title}</TableCell>
                  <TableCell>{g.category_label}</TableCell>
                  <TableCell>{g.against_name ?? "—"}</TableCell>
                  <TableCell><Badge variant="outline">{g.status_label}</Badge></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <GrievanceSheet
        row={selected}
        canManage={canManage}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}

function NewGrievanceDialog() {
  const create = useCreateGrievance();
  const { data: employees } = useHREmployees({ page: "1", page_size: "300" });
  const [open, setOpen] = React.useState(false);
  const [f, setF] = React.useState({
    raised_by_id: "", against_id: "", category: "management",
    title: "", description: "", date_raised: "",
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button>Log grievance</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Log a grievance</DialogTitle></DialogHeader>
        <form
          className="grid gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const body: Record<string, unknown> = { ...f };
            if (!f.against_id) delete body.against_id;
            if (!f.date_raised) delete body.date_raised;
            create.mutate(body, {
              onSuccess: () => { setOpen(false); toast.success("Grievance logged"); },
              onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
            });
          }}
        >
          <div className="space-y-1">
            <Label>Raised by</Label>
            <Select value={f.raised_by_id} onValueChange={(v) => setF((p) => ({ ...p, raised_by_id: v }))}>
              <SelectTrigger><SelectValue placeholder="Choose employee" /></SelectTrigger>
              <SelectContent>
                {(employees?.results ?? []).map((e) => (
                  <SelectItem key={e.id} value={e.id}>{e.full_name} ({e.employee_number})</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Against (optional)</Label>
            <Select value={f.against_id} onValueChange={(v) => setF((p) => ({ ...p, against_id: v }))}>
              <SelectTrigger><SelectValue placeholder="Not specified" /></SelectTrigger>
              <SelectContent>
                {(employees?.results ?? []).map((e) => (
                  <SelectItem key={e.id} value={e.id}>{e.full_name} ({e.employee_number})</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Category</Label>
            <Select value={f.category} onValueChange={(v) => setF((p) => ({ ...p, category: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {GRIEVANCE_CATS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Title</Label>
            <Input required value={f.title}
              onChange={(e) => setF((p) => ({ ...p, title: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Date raised</Label>
            <Input type="date" value={f.date_raised}
              onChange={(e) => setF((p) => ({ ...p, date_raised: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Description</Label>
            <Textarea value={f.description}
              onChange={(e) => setF((p) => ({ ...p, description: e.target.value }))} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={create.isPending || !f.raised_by_id || !f.title}>
              Log grievance
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function GrievanceSheet({
  row, canManage, onClose,
}: {
  row: HRGrievance | null;
  canManage: boolean;
  onClose: () => void;
}) {
  const update = useUpdateGrievance();
  const [f, setF] = React.useState<Record<string, string>>({});

  React.useEffect(() => {
    if (row) {
      setF({
        status: row.status,
        review_notes: row.review_notes ?? "",
        resolution_notes: row.resolution_notes ?? "",
      });
    }
  }, [row]);

  return (
    <Sheet open={!!row} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {row ? (
          <>
            <div className="space-y-1"><SheetTitle>{row.title}</SheetTitle></div>
            <div className="mt-4 space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3 text-muted-foreground">
                <div><span className="text-foreground">Raised by:</span> {row.raised_by_name}</div>
                <div><span className="text-foreground">Against:</span> {row.against_name ?? "—"}</div>
                <div><span className="text-foreground">Category:</span> {row.category_label}</div>
                <div><span className="text-foreground">Raised:</span> {row.date_raised ?? "—"}</div>
              </div>
              {row.description ? (
                <p className="whitespace-pre-wrap rounded-md bg-muted p-3">{row.description}</p>
              ) : null}

              {canManage ? (
                <form
                  className="space-y-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    update.mutate(
                      { id: row.id, body: f },
                      {
                        onSuccess: () => { toast.success("Grievance updated"); onClose(); },
                        onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
                      },
                    );
                  }}
                >
                  <Field label="Status">
                    <Select value={f.status} onValueChange={(v) => setF((p) => ({ ...p, status: v }))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {GRIEVANCE_STATUSES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field label="Review notes">
                    <Textarea value={f.review_notes}
                      onChange={(e) => setF((p) => ({ ...p, review_notes: e.target.value }))} />
                  </Field>
                  <Field label="Resolution notes">
                    <Textarea value={f.resolution_notes}
                      onChange={(e) => setF((p) => ({ ...p, resolution_notes: e.target.value }))} />
                  </Field>
                  <Button type="submit" disabled={update.isPending}>Save changes</Button>
                </form>
              ) : (
                <div className="space-y-2 text-muted-foreground">
                  <div><span className="text-foreground">Status:</span> {row.status_label}</div>
                  {row.resolution_notes ? <p className="whitespace-pre-wrap">{row.resolution_notes}</p> : null}
                </div>
              )}
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      {children}
    </div>
  );
}
