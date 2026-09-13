"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";

import { useVacancies, useCreateVacancy, useHRCan } from "@/hooks/use-hr";
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
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const EMP_TYPES = [
  ["full_time", "Full-time"], ["part_time", "Part-time"], ["contract", "Contract"],
  ["temporary", "Temporary"], ["intern", "Internship"],
] as const;

export default function RecruitmentPage() {
  const [status, setStatus] = React.useState("all");
  const params: Record<string, string> = {};
  if (status !== "all") params.status = status;
  const { data, isLoading, isError, refetch } = useVacancies(params);
  const rows = data?.results ?? [];

  return (
    <>
      <PageHeader
        title="Recruitment"
        description="Open vacancies and applicant pipelines."
        actions={<NewVacancyDialog />}
      />

      <Select value={status} onValueChange={setStatus}>
        <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All statuses</SelectItem>
          <SelectItem value="draft">Draft</SelectItem>
          <SelectItem value="open">Open</SelectItem>
          <SelectItem value="closed">Closed</SelectItem>
          <SelectItem value="filled">Filled</SelectItem>
          <SelectItem value="cancelled">Cancelled</SelectItem>
        </SelectContent>
      </Select>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-80" />
      ) : rows.length === 0 ? (
        <EmptyState title="No vacancies" description="Create a vacancy to start recruiting." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Title</TableHead><TableHead>Department</TableHead>
              <TableHead>Type</TableHead><TableHead>Positions</TableHead>
              <TableHead>Applicants</TableHead><TableHead>Closing</TableHead>
              <TableHead>Status</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((v) => (
                <TableRow key={v.id}>
                  <TableCell>
                    <Link href={`/hr/recruitment/${v.id}`} className="font-medium hover:underline">
                      {v.title}
                    </Link>
                  </TableCell>
                  <TableCell>{v.department_name ?? "—"}</TableCell>
                  <TableCell>{v.employment_type_label}</TableCell>
                  <TableCell>{v.number_of_positions}</TableCell>
                  <TableCell>{v.applicant_count}</TableCell>
                  <TableCell>{v.closing_date ?? "—"}</TableCell>
                  <TableCell><Badge variant="outline">{v.status_label}</Badge></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}

function NewVacancyDialog() {
  const canManage = useHRCan("hr.recruitment.manage");
  const create = useCreateVacancy();
  const [open, setOpen] = React.useState(false);
  const [f, setF] = React.useState({
    title: "", number_of_positions: "1", employment_type: "full_time",
    is_teaching_role: "false", closing_date: "", job_description: "",
  });

  if (!canManage) return null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button>New vacancy</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New vacancy</DialogTitle></DialogHeader>
        <form
          className="grid gap-3 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate(
              {
                title: f.title,
                number_of_positions: Number(f.number_of_positions) || 1,
                employment_type: f.employment_type,
                is_teaching_role: f.is_teaching_role === "true",
                closing_date: f.closing_date || null,
                job_description: f.job_description,
                status: "open",
              },
              {
                onSuccess: () => { setOpen(false); toast.success("Vacancy created"); },
                onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
              },
            );
          }}
        >
          <div className="space-y-1 sm:col-span-2">
            <Label>Title</Label>
            <Input required value={f.title} onChange={(e) => setF((p) => ({ ...p, title: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Positions</Label>
            <Input type="number" min={1} value={f.number_of_positions}
              onChange={(e) => setF((p) => ({ ...p, number_of_positions: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Closing date</Label>
            <Input type="date" value={f.closing_date}
              onChange={(e) => setF((p) => ({ ...p, closing_date: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Employment type</Label>
            <Select value={f.employment_type} onValueChange={(v) => setF((p) => ({ ...p, employment_type: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {EMP_TYPES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Teaching role?</Label>
            <Select value={f.is_teaching_role} onValueChange={(v) => setF((p) => ({ ...p, is_teaching_role: v }))}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="false">No</SelectItem>
                <SelectItem value="true">Yes</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label>Job description</Label>
            <Textarea value={f.job_description}
              onChange={(e) => setF((p) => ({ ...p, job_description: e.target.value }))} />
          </div>
          <DialogFooter className="sm:col-span-2">
            <Button type="submit" disabled={create.isPending}>Create</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
