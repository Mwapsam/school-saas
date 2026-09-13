"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";

import {
  useHRLeave, useLeaveReview, useHRCan, useLeaveCalendar, useLeaveBalances,
} from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { ErrorState, EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function HRLeavePage() {
  return (
    <>
      <PageHeader title="Leave" description="Requests, calendar and balances." />
      <Tabs defaultValue="requests">
        <TabsList>
          <TabsTrigger value="requests">Requests</TabsTrigger>
          <TabsTrigger value="calendar">Calendar</TabsTrigger>
          <TabsTrigger value="balances">Balances</TabsTrigger>
        </TabsList>
        <TabsContent value="requests" className="pt-4"><RequestsTab /></TabsContent>
        <TabsContent value="calendar" className="pt-4"><CalendarTab /></TabsContent>
        <TabsContent value="balances" className="pt-4"><BalancesTab /></TabsContent>
      </Tabs>
    </>
  );
}

function RequestsTab() {
  const [stage, setStage] = React.useState("all");
  const params: Record<string, string> = {};
  if (stage !== "all") params.stage = stage;
  const { data, isLoading, isError, refetch } = useHRLeave(params);
  const review = useLeaveReview();
  const canApprove = useHRCan("hr.leave.approve");
  const rows = data?.results ?? [];

  const act = (id: string, s: "supervisor" | "hr", approve: boolean) => {
    review.mutate(
      { id, stage: s, approve },
      {
        onSuccess: () => toast.success(approve ? "Approved" : "Rejected"),
        onError: (e: unknown) => toast.error((e as Error).message ?? "Failed"),
      },
    );
  };

  return (
    <div className="space-y-4">
      <Select value={stage} onValueChange={setStage}>
        <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All requests</SelectItem>
          <SelectItem value="supervisor">Awaiting supervisor</SelectItem>
          <SelectItem value="hr">Awaiting HR</SelectItem>
        </SelectContent>
      </Select>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-96" />
      ) : rows.length === 0 ? (
        <EmptyState title="Nothing here" description="No leave requests match." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Employee</TableHead><TableHead>Type</TableHead>
              <TableHead>Dates</TableHead><TableHead>Days</TableHead>
              <TableHead>Supervisor</TableHead><TableHead>HR</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((l) => (
                <TableRow key={l.id}>
                  <TableCell className="font-medium">{l.employee_name}</TableCell>
                  <TableCell>{l.leave_type_name}</TableCell>
                  <TableCell>{l.start_date} → {l.end_date}</TableCell>
                  <TableCell>{l.days}</TableCell>
                  <TableCell><Badge variant="outline">{l.supervisor_status}</Badge></TableCell>
                  <TableCell><Badge variant="outline">{l.hr_status}</Badge></TableCell>
                  <TableCell className="text-right space-x-1">
                    {canApprove && l.supervisor_status === "pending" ? (
                      <>
                        <Button size="sm" variant="outline" onClick={() => act(l.id, "supervisor", true)}>Sup ✓</Button>
                        <Button size="sm" variant="ghost" onClick={() => act(l.id, "supervisor", false)}>✕</Button>
                      </>
                    ) : canApprove && l.supervisor_status === "approved" && l.hr_status === "pending" ? (
                      <>
                        <Button size="sm" onClick={() => act(l.id, "hr", true)}>HR ✓</Button>
                        <Button size="sm" variant="ghost" onClick={() => act(l.id, "hr", false)}>✕</Button>
                      </>
                    ) : (
                      <span className="text-xs text-muted-foreground">{l.status}</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function isoDaysFromNow(days: number) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function CalendarTab() {
  const [from, setFrom] = React.useState(isoDaysFromNow(-7));
  const [to, setTo] = React.useState(isoDaysFromNow(45));
  const { data, isLoading, isError, refetch } = useLeaveCalendar({ from, to });
  const rows = data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">From
          <input type="date" className="ml-2 rounded border px-2 py-1" value={from}
            onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label className="text-sm">To
          <input type="date" className="ml-2 rounded border px-2 py-1" value={to}
            onChange={(e) => setTo(e.target.value)} />
        </label>
      </div>
      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-80" />
      ) : rows.length === 0 ? (
        <EmptyState title="Nobody away" description="No approved leave in this window." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Employee</TableHead><TableHead>Department</TableHead>
              <TableHead>Type</TableHead><TableHead>From</TableHead><TableHead>To</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-medium">
                    <Link href={`/hr/employees/${r.employee_id}`} className="hover:underline">
                      {r.employee_name}
                    </Link>
                  </TableCell>
                  <TableCell>{r.department ?? "—"}</TableCell>
                  <TableCell>{r.leave_type}</TableCell>
                  <TableCell>{r.start_date}</TableCell>
                  <TableCell>{r.end_date}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function BalancesTab() {
  const { data, isLoading, isError, refetch } = useLeaveBalances();
  const rows = data ?? [];
  const types = rows[0]?.balances.map((b) => b.leave_type) ?? [];

  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (isLoading) return <Skeleton className="h-80" />;
  if (rows.length === 0) {
    return <EmptyState title="No balances" description="Configure leave types in HR Settings." />;
  }

  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table>
        <TableHeader><TableRow>
          <TableHead>Employee</TableHead>
          <TableHead>Department</TableHead>
          {types.map((t) => <TableHead key={t}>{t} (rem.)</TableHead>)}
        </TableRow></TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.employee_id}>
              <TableCell className="font-medium">
                <Link href={`/hr/employees/${r.employee_id}`} className="hover:underline">
                  {r.employee_name}
                </Link>
              </TableCell>
              <TableCell>{r.department ?? "—"}</TableCell>
              {r.balances.map((b) => (
                <TableCell key={b.leave_type_id}>
                  {b.remaining} / {b.allocated}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
