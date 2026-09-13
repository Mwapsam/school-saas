"use client";

import * as React from "react";
import { toast } from "sonner";

import { useMyLeave, useApplyForLeave, useMyLeaveBalance } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { ErrorState, EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function MyLeavePage() {
  const { data, isLoading, isError, refetch } = useMyLeave();
  const balances = useMyLeaveBalance();
  const apply = useApplyForLeave();
  const [form, setForm] = React.useState({ start_date: "", end_date: "", reason: "" });

  return (
    <>
      <PageHeader title="My Leave" description="Apply for leave and track its status." />

      {balances.data && balances.data.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {balances.data.map((b) => (
            <Card key={b.leave_type_id}>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">{b.leave_type}</p>
                <p className="text-2xl font-semibold">{b.remaining}</p>
                <p className="text-xs text-muted-foreground">
                  of {b.allocated} · {b.used} used
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Card><CardContent className="p-6">
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            apply.mutate(form, {
              onSuccess: () => {
                setForm({ start_date: "", end_date: "", reason: "" });
                toast.success("Leave request submitted");
              },
              onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
            });
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="start">From</Label>
            <Input id="start" type="date" required value={form.start_date}
              onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="end">To</Label>
            <Input id="end" type="date" required value={form.end_date}
              onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))} />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label htmlFor="reason">Reason</Label>
            <Textarea id="reason" required value={form.reason}
              onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))} />
          </div>
          <div className="sm:col-span-2">
            <Button type="submit" disabled={apply.isPending}>Submit request</Button>
          </div>
        </form>
      </CardContent></Card>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-64" />
      ) : !data?.length ? (
        <EmptyState title="No leave requests" description="Your leave history will show here." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Type</TableHead><TableHead>Dates</TableHead><TableHead>Days</TableHead>
              <TableHead>Supervisor</TableHead><TableHead>HR</TableHead><TableHead>Overall</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {data.map((l) => (
                <TableRow key={l.id}>
                  <TableCell>{l.leave_type_name}</TableCell>
                  <TableCell>{l.start_date} → {l.end_date}</TableCell>
                  <TableCell>{l.days}</TableCell>
                  <TableCell><Badge variant="outline">{l.supervisor_status}</Badge></TableCell>
                  <TableCell><Badge variant="outline">{l.hr_status}</Badge></TableCell>
                  <TableCell><Badge>{l.status}</Badge></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}
