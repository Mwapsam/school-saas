"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";

import {
  useHRAttendance, useMarkAttendance, useAttendanceAnalytics, useHRCan,
} from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { ErrorState, EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

function today() {
  return new Date().toISOString().slice(0, 10);
}

const STATUSES = [
  "present", "absent", "late", "on_leave", "half_day",
  "official_duty", "training", "holiday",
];

export default function HRAttendancePage() {
  const canManage = useHRCan("hr.attendance.manage");
  return (
    <>
      <PageHeader
        title="Staff Attendance"
        description="Daily records, manual marking and the punctuality watchlist."
        actions={canManage ? <MarkAttendanceDialog /> : null}
      />
      <Tabs defaultValue="records">
        <TabsList>
          <TabsTrigger value="records">Records</TabsTrigger>
          <TabsTrigger value="watchlist">Watchlist</TabsTrigger>
        </TabsList>
        <TabsContent value="records" className="pt-4"><RecordsTab /></TabsContent>
        <TabsContent value="watchlist" className="pt-4"><WatchlistTab /></TabsContent>
      </Tabs>
    </>
  );
}

function RecordsTab() {
  const [from, setFrom] = React.useState(today());
  const [to, setTo] = React.useState(today());
  const { data, isLoading, isError, refetch } = useHRAttendance({ from, to });
  const rows = data?.results ?? [];

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <label className="text-sm">From <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="w-40" /></label>
        <label className="text-sm">To <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="w-40" /></label>
      </div>
      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-96" />
      ) : rows.length === 0 ? (
        <EmptyState title="No records" description="No attendance recorded in this range." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Employee</TableHead><TableHead>Date</TableHead>
              <TableHead>Status</TableHead><TableHead>In</TableHead>
              <TableHead>Out</TableHead><TableHead>Remarks</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-medium">{r.employee_name}</TableCell>
                  <TableCell>{r.date}</TableCell>
                  <TableCell>{r.status_label}</TableCell>
                  <TableCell>{r.clock_in ?? "—"}</TableCell>
                  <TableCell>{r.clock_out ?? "—"}</TableCell>
                  <TableCell className="text-muted-foreground">{r.remarks ?? "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function WatchlistTab() {
  const { data, isLoading, isError, refetch } = useAttendanceAnalytics();

  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (isLoading) return <Skeleton className="h-80" />;

  const watchlist = data?.watchlist ?? [];
  const noRecord = data?.no_record_today ?? [];

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Repeated lateness / absence (last 30 days)</h3>
        {watchlist.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nobody on the watchlist.</p>
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader><TableRow>
                <TableHead>Employee</TableHead><TableHead>Late</TableHead><TableHead>Absent</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {watchlist.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">
                      <Link href={`/hr/employees/${r.id}`} className="hover:underline">{r.name}</Link>
                    </TableCell>
                    <TableCell><Badge variant="outline">{r.late_count}</Badge></TableCell>
                    <TableCell><Badge variant="outline">{r.absent_count}</Badge></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-semibold">No attendance recorded today</h3>
        {noRecord.length === 0 ? (
          <p className="text-sm text-muted-foreground">Every active employee has a record today.</p>
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader><TableRow>
                <TableHead>Employee</TableHead><TableHead>Emp No</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {noRecord.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">
                      <Link href={`/hr/employees/${r.id}`} className="hover:underline">{r.name}</Link>
                    </TableCell>
                    <TableCell className="font-mono text-xs">{r.employee_number}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>
    </div>
  );
}

function MarkAttendanceDialog() {
  const mark = useMarkAttendance();
  const [open, setOpen] = React.useState(false);
  const [f, setF] = React.useState({
    employee_id: "", date: today(), status: "present", remarks: "",
  });
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button>Mark attendance</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Mark attendance</DialogTitle></DialogHeader>
        <form
          className="grid gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            mark.mutate(f, {
              onSuccess: () => { setOpen(false); toast.success("Recorded"); },
              onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
            });
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="eid">Employee ID</Label>
            <Input id="eid" required value={f.employee_id}
              onChange={(e) => set("employee_id", e.target.value)}
              placeholder="Employee UUID (from directory)" />
          </div>
          <div className="space-y-1">
            <Label htmlFor="adate">Date</Label>
            <Input id="adate" type="date" required value={f.date}
              onChange={(e) => set("date", e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Status</Label>
            <Select value={f.status} onValueChange={(v) => set("status", v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>{s.replace("_", " ")}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="rem">Remarks</Label>
            <Input id="rem" value={f.remarks} onChange={(e) => set("remarks", e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={mark.isPending}>Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
