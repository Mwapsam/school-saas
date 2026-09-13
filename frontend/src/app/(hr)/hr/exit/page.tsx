"use client";

import * as React from "react";
import Link from "next/link";

import { useExitList } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { ErrorState, EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

function Bar({ percent }: { percent: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-28 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${percent}%` }} />
      </div>
      <span className="text-xs text-muted-foreground">{percent}%</span>
    </div>
  );
}

export default function ExitPage() {
  const [status, setStatus] = React.useState("in_progress");
  const params: Record<string, string> = {};
  if (status !== "all") params.status = status;
  const { data, isLoading, isError, refetch } = useExitList(params);
  const rows = data?.results ?? [];

  return (
    <>
      <PageHeader
        title="Employee Exit"
        description="Offboarding records and clearance progress."
      />

      <Select value={status} onValueChange={setStatus}>
        <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="in_progress">In progress</SelectItem>
          <SelectItem value="completed">Completed</SelectItem>
          <SelectItem value="all">All</SelectItem>
        </SelectContent>
      </Select>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-72" />
      ) : rows.length === 0 ? (
        <EmptyState title="Nothing here" description="No exit records match." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Employee</TableHead><TableHead>Type</TableHead>
              <TableHead>Last day</TableHead><TableHead>Final pay</TableHead>
              <TableHead>Clearance</TableHead><TableHead>Status</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((x) => (
                <TableRow key={x.id}>
                  <TableCell>
                    <Link href={`/hr/employees/${x.employee_id}`} className="font-medium hover:underline">
                      {x.employee_name}
                    </Link>
                  </TableCell>
                  <TableCell>{x.exit_type_label}</TableCell>
                  <TableCell>{x.last_working_date ?? "—"}</TableCell>
                  <TableCell className="capitalize">{x.final_payment_status}</TableCell>
                  <TableCell><Bar percent={x.progress.percent} /></TableCell>
                  <TableCell><Badge variant="outline">{x.status_label}</Badge></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}
