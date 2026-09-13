"use client";

import * as React from "react";
import { toast } from "sonner";

import { useHRTasks, useCreateTask, useUpdateTask } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { ErrorState, EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const NEXT: Record<string, "pending" | "in_progress" | "completed"> = {
  pending: "in_progress",
  in_progress: "completed",
  completed: "pending",
};

export default function HRTasksPage() {
  const [status, setStatus] = React.useState("all");
  const [title, setTitle] = React.useState("");
  const [due, setDue] = React.useState("");
  const params: Record<string, string> = {};
  if (status !== "all") params.status = status;
  const { data, isLoading, isError, refetch } = useHRTasks(params);
  const create = useCreateTask();
  const update = useUpdateTask();
  const rows = data?.results ?? [];

  const add = () => {
    if (!title.trim()) return;
    create.mutate(
      { title, due_date: due || null },
      {
        onSuccess: () => { setTitle(""); setDue(""); toast.success("Task added"); },
        onError: (e: unknown) => toast.error((e as Error).message ?? "Failed"),
      },
    );
  };

  return (
    <>
      <PageHeader title="HR Tasks" description="Reminders and to-dos on the HR desk." />

      <div className="flex flex-wrap items-end gap-2">
        <Input placeholder="New task…" value={title} onChange={(e) => setTitle(e.target.value)} className="max-w-xs" />
        <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} className="w-40" />
        <Button onClick={add} disabled={create.isPending}>Add</Button>
        <div className="flex-1" />
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="in_progress">In progress</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-80" />
      ) : rows.length === 0 ? (
        <EmptyState title="No tasks" description="You're all caught up." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Task</TableHead><TableHead>Category</TableHead>
              <TableHead>Due</TableHead><TableHead>Status</TableHead>
              <TableHead className="text-right">Advance</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((t) => (
                <TableRow key={t.id}>
                  <TableCell className="font-medium">{t.title}</TableCell>
                  <TableCell><Badge variant="outline">{t.category}</Badge></TableCell>
                  <TableCell>{t.due_date ?? "—"}</TableCell>
                  <TableCell>{t.status.replace("_", " ")}</TableCell>
                  <TableCell className="text-right">
                    <Button size="sm" variant="outline"
                      onClick={() => update.mutate({ id: t.id, body: { status: NEXT[t.status] } })}>
                      → {NEXT[t.status].replace("_", " ")}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}
