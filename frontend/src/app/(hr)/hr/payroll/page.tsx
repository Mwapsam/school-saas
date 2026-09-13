"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";

import {
  useHRPayslips, useGeneratePayslips, usePayslipAction, usePayrollGroups, useHRCan,
} from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  generated: "secondary",
  approved: "default",
  rejected: "destructive",
  paid: "outline",
};

export default function HRPayrollPage() {
  const canManage = useHRCan("hr.payroll.manage");
  const [status, setStatus] = React.useState("all");
  const [page, setPage] = React.useState(1);
  const params: Record<string, string> = { page: String(page) };
  if (status !== "all") params.status = status;

  const { data, isLoading, isError, refetch } = useHRPayslips(params);
  const action = usePayslipAction();
  const rows = data?.results ?? [];

  const run = (id: string, act: string, body?: Record<string, unknown>) =>
    action.mutate(
      { id, action: act, body },
      {
        onSuccess: () => toast.success("Done"),
        onError: (e: unknown) => toast.error((e as Error).message ?? "Failed"),
      },
    );

  return (
    <>
      <PageHeader
        title="Payroll"
        description="Generate, approve and pay staff payslips."
        actions={
          <div className="flex gap-2">
            <Button variant="outline" asChild><Link href="/hr/payroll/settings">Settings</Link></Button>
            {canManage && <GenerateDialog />}
          </div>
        }
      />

      <Select value={status} onValueChange={(v) => { setStatus(v); setPage(1); }}>
        <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Any status</SelectItem>
          <SelectItem value="generated">Generated</SelectItem>
          <SelectItem value="approved">Approved</SelectItem>
          <SelectItem value="rejected">Rejected</SelectItem>
          <SelectItem value="paid">Paid</SelectItem>
        </SelectContent>
      </Select>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-96" />
      ) : rows.length === 0 ? (
        <EmptyState title="No payslips" description="Generate a payroll run to get started." />
      ) : (
        <>
          <div className="rounded-lg border">
            <Table>
              <TableHeader><TableRow>
                <TableHead>Employee</TableHead><TableHead>Period</TableHead>
                <TableHead>Net pay</TableHead><TableHead>Status</TableHead>
                {canManage && <TableHead className="text-right">Actions</TableHead>}
              </TableRow></TableHeader>
              <TableBody>
                {rows.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">
                      <Link href={`/hr/payroll/${p.id}`} className="hover:underline">
                        {p.employee_name}
                      </Link>
                    </TableCell>
                    <TableCell>{p.period_start} → {p.period_end}</TableCell>
                    <TableCell className="font-medium">{p.net_pay}</TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[p.status] ?? "outline"}>{p.status}</Badge>
                    </TableCell>
                    {canManage && (
                      <TableCell className="text-right space-x-1">
                        {p.status === "generated" && (
                          <>
                            <Button size="sm" variant="outline" onClick={() => run(p.id, "approve")}>Approve</Button>
                            <Button size="sm" variant="ghost"
                              onClick={() => {
                                const reason = prompt("Rejection reason?");
                                if (reason) run(p.id, "reject", { reason });
                              }}>Reject</Button>
                          </>
                        )}
                        {p.status === "approved" && (
                          <Button size="sm" onClick={() => run(p.id, "mark-paid")}>Mark paid</Button>
                        )}
                        {p.status !== "paid" && (
                          <Button size="sm" variant="ghost" onClick={() => run(p.id, "regenerate")}>Regenerate</Button>
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>{data?.count ?? 0} payslips</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={!data?.previous}
                onClick={() => setPage((p) => Math.max(1, p - 1))}>Previous</Button>
              <Button variant="outline" size="sm" disabled={!data?.next}
                onClick={() => setPage((p) => p + 1)}>Next</Button>
            </div>
          </div>
        </>
      )}
    </>
  );
}

function GenerateDialog() {
  const gen = useGeneratePayslips();
  const groups = usePayrollGroups().data ?? [];
  const [open, setOpen] = React.useState(false);
  const [f, setF] = React.useState({
    period_start: "", period_end: "", payroll_group_id: "", employee_id: "",
  });
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button>Generate payslips</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Generate payslips</DialogTitle></DialogHeader>
        <form
          className="grid gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const body: Record<string, unknown> = {
              period_start: f.period_start, period_end: f.period_end,
            };
            if (f.payroll_group_id) body.payroll_group_id = f.payroll_group_id;
            else if (f.employee_id) body.employee_id = f.employee_id;
            gen.mutate(body, {
              onSuccess: () => { setOpen(false); toast.success("Payroll run created"); },
              onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
            });
          }}
        >
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Period start</Label>
              <Input type="date" required value={f.period_start}
                onChange={(e) => set("period_start", e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Period end</Label>
              <Input type="date" required value={f.period_end}
                onChange={(e) => set("period_end", e.target.value)} />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Payroll group (whole group)</Label>
            <Select value={f.payroll_group_id} onValueChange={(v) => set("payroll_group_id", v)}>
              <SelectTrigger><SelectValue placeholder="Choose a group…" /></SelectTrigger>
              <SelectContent>
                {groups.map((g) => <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>…or a single employee ID</Label>
            <Input value={f.employee_id} onChange={(e) => set("employee_id", e.target.value)}
              placeholder="Employee UUID" disabled={!!f.payroll_group_id} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={gen.isPending}>Generate</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
