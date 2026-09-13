"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";

import { usePerformanceReviews, useCreateReview, useHREmployees, useHRCan } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { ErrorState, EmptyState } from "@/components/states";
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

export default function PerformancePage() {
  const [status, setStatus] = React.useState("all");
  const params: Record<string, string> = {};
  if (status !== "all") params.status = status;
  const { data, isLoading, isError, refetch } = usePerformanceReviews(params);
  const rows = data?.results ?? [];

  return (
    <>
      <PageHeader
        title="Performance"
        description="Appraisals for teaching and non-teaching staff."
        actions={<NewReviewDialog />}
      />

      <Select value={status} onValueChange={setStatus}>
        <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All</SelectItem>
          <SelectItem value="draft">Draft</SelectItem>
          <SelectItem value="in_review">In review</SelectItem>
          <SelectItem value="employee_ack">Awaiting employee</SelectItem>
          <SelectItem value="completed">Completed</SelectItem>
        </SelectContent>
      </Select>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-80" />
      ) : rows.length === 0 ? (
        <EmptyState title="No reviews" description="Create a review to get started." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Employee</TableHead><TableHead>Period</TableHead>
              <TableHead>Date</TableHead><TableHead>Reviewer</TableHead>
              <TableHead>Rating</TableHead><TableHead>Status</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>
                    <Link href={`/hr/performance/${r.id}`} className="font-medium hover:underline">
                      {r.employee_name}
                    </Link>
                    {r.is_teacher_review ? <Badge variant="outline" className="ml-2">Teacher</Badge> : null}
                  </TableCell>
                  <TableCell>{r.review_period}</TableCell>
                  <TableCell>{r.review_date}</TableCell>
                  <TableCell>{r.reviewer_name ?? "—"}</TableCell>
                  <TableCell>{r.overall_rating != null ? `${r.overall_rating}/5` : "—"}</TableCell>
                  <TableCell><Badge variant="outline">{r.status_label}</Badge></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}

function NewReviewDialog() {
  const canConduct = useHRCan("hr.performance.conduct");
  const create = useCreateReview();
  const { data: employees } = useHREmployees({ page: "1", page_size: "200" });
  const [open, setOpen] = React.useState(false);
  const [f, setF] = React.useState({ employee_id: "", review_period: "", review_date: "" });

  if (!canConduct) return null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button>New review</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New performance review</DialogTitle></DialogHeader>
        <form
          className="grid gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate(f, {
              onSuccess: () => { setOpen(false); toast.success("Review created"); },
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
          <div className="space-y-1">
            <Label>Review period</Label>
            <Input required placeholder="e.g. 2026 Term 1" value={f.review_period}
              onChange={(e) => setF((p) => ({ ...p, review_period: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Review date</Label>
            <Input type="date" required value={f.review_date}
              onChange={(e) => setF((p) => ({ ...p, review_date: e.target.value }))} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={create.isPending || !f.employee_id}>Create</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
