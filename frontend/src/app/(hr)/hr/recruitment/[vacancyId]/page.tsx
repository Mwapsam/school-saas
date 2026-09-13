"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import {
  useVacancy, useApplicants, useCreateApplicant, useAdvanceApplicant,
  useConvertApplicant, useHRCan,
} from "@/hooks/use-hr";
import type { ApplicantStage, HRApplicant } from "@/lib/types";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const STAGES: ApplicantStage[] = [
  "applied", "shortlisted", "interview", "reference_check", "offered", "hired", "unsuccessful",
];
const NEXT: Partial<Record<ApplicantStage, ApplicantStage[]>> = {
  applied: ["shortlisted", "unsuccessful"],
  shortlisted: ["interview", "unsuccessful"],
  interview: ["reference_check", "offered", "unsuccessful"],
  reference_check: ["offered", "unsuccessful"],
  offered: ["hired", "unsuccessful"],
};

export default function VacancyDetailPage() {
  const { vacancyId } = useParams<{ vacancyId: string }>();
  const { data: vacancy, isLoading, isError, refetch } = useVacancy(vacancyId);
  const { data: applicants } = useApplicants(vacancyId);

  if (isError) {
    return (<><PageHeader title="Vacancy" /><ErrorState onRetry={() => refetch()} /></>);
  }

  const byStage = (s: ApplicantStage) => (applicants ?? []).filter((a) => a.stage === s);

  return (
    <>
      <PageHeader
        title={isLoading ? "Loading…" : vacancy?.title ?? "Vacancy"}
        description={vacancy ? `${vacancy.department_name ?? "No department"} · ${vacancy.number_of_positions} position(s) · ${vacancy.status_label}` : undefined}
        actions={vacancy ? <AddApplicantDialog vacancyId={vacancyId} /> : undefined}
      />

      {isLoading || !vacancy ? (
        <Skeleton className="h-80" />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {STAGES.map((s) => (
            <Card key={s}>
              <CardContent className="p-4">
                <p className="mb-3 text-sm font-semibold capitalize">
                  {s.replace("_", " ")}
                  <Badge variant="secondary" className="ml-2">{byStage(s).length}</Badge>
                </p>
                <div className="space-y-2">
                  {byStage(s).map((a) => (
                    <ApplicantCard key={a.id} applicant={a} vacancyId={vacancyId} />
                  ))}
                  {byStage(s).length === 0 ? (
                    <p className="text-xs text-muted-foreground">—</p>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}

function ApplicantCard({ applicant, vacancyId }: { applicant: HRApplicant; vacancyId: string }) {
  const advance = useAdvanceApplicant(vacancyId);
  const canManage = useHRCan("hr.recruitment.manage");
  const canHire = useHRCan("hr.employee.manage");
  const nexts = NEXT[applicant.stage] ?? [];

  return (
    <div className="rounded-md border p-2 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">{applicant.full_name}</span>
        {canManage && nexts.length ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-6 px-2 text-xs">Move</Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {nexts.map((n) => (
                <DropdownMenuItem
                  key={n}
                  onClick={() =>
                    advance.mutate(
                      { id: applicant.id, body: { stage: n } },
                      {
                        onSuccess: () => toast.success(`Moved to ${n.replace("_", " ")}`),
                        onError: (e: unknown) => toast.error((e as Error).message ?? "Failed"),
                      },
                    )
                  }
                  className="capitalize"
                >
                  {n.replace("_", " ")}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>
      {applicant.email ? <p className="text-xs text-muted-foreground">{applicant.email}</p> : null}
      {applicant.cv_url ? (
        <a href={applicant.cv_url} target="_blank" rel="noreferrer" className="text-xs underline">CV</a>
      ) : null}
      {applicant.stage === "offered" && canHire && !applicant.converted_employee_id ? (
        <ConvertDialog applicant={applicant} vacancyId={vacancyId} />
      ) : null}
      {applicant.converted_employee_id ? (
        <Badge variant="secondary" className="mt-1">Hired → employee</Badge>
      ) : null}
    </div>
  );
}

function ConvertDialog({ applicant, vacancyId }: { applicant: HRApplicant; vacancyId: string }) {
  const convert = useConvertApplicant(vacancyId);
  const [open, setOpen] = React.useState(false);
  const [f, setF] = React.useState({ employee_number: "", joining_date: "", gender: "true" });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" className="mt-2 h-7 w-full text-xs">Convert to employee</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Convert {applicant.full_name} to employee</DialogTitle></DialogHeader>
        <form
          className="grid gap-3 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            convert.mutate(
              {
                id: applicant.id,
                body: {
                  employee_number: f.employee_number,
                  joining_date: f.joining_date,
                  gender: f.gender === "true",
                },
              },
              {
                onSuccess: (r) => { setOpen(false); toast.success(`Employee ${r.employee_number} created`); },
                onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
              },
            );
          }}
        >
          <div className="space-y-1">
            <Label>Employee number</Label>
            <Input required value={f.employee_number}
              onChange={(e) => setF((p) => ({ ...p, employee_number: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Joining date</Label>
            <Input type="date" required value={f.joining_date}
              onChange={(e) => setF((p) => ({ ...p, joining_date: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Gender</Label>
            <Select value={f.gender} onValueChange={(v) => setF((p) => ({ ...p, gender: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="true">Male</SelectItem>
                <SelectItem value="false">Female</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <DialogFooter className="sm:col-span-2">
            <Button type="submit" disabled={convert.isPending}>Create employee</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function AddApplicantDialog({ vacancyId }: { vacancyId: string }) {
  const canManage = useHRCan("hr.recruitment.manage");
  const create = useCreateApplicant(vacancyId);
  const [open, setOpen] = React.useState(false);
  const [f, setF] = React.useState({ first_name: "", last_name: "", email: "", phone: "", qualifications_summary: "" });

  if (!canManage) return null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button>Add applicant</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New applicant</DialogTitle></DialogHeader>
        <form
          className="grid gap-3 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate(f, {
              onSuccess: () => { setOpen(false); setF({ first_name: "", last_name: "", email: "", phone: "", qualifications_summary: "" }); toast.success("Applicant added"); },
              onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
            });
          }}
        >
          <div className="space-y-1">
            <Label>First name</Label>
            <Input required value={f.first_name} onChange={(e) => setF((p) => ({ ...p, first_name: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Last name</Label>
            <Input required value={f.last_name} onChange={(e) => setF((p) => ({ ...p, last_name: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Email</Label>
            <Input type="email" value={f.email} onChange={(e) => setF((p) => ({ ...p, email: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Phone</Label>
            <Input value={f.phone} onChange={(e) => setF((p) => ({ ...p, phone: e.target.value }))} />
          </div>
          <DialogFooter className="sm:col-span-2">
            <Button type="submit" disabled={create.isPending}>Add</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
