"use client";

import { useMyAttendance } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/states";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function MyAttendancePage() {
  const { data, isLoading } = useMyAttendance();

  return (
    <>
      <PageHeader title="My Attendance" description="Your attendance over the last 90 days." />
      {isLoading ? (
        <Skeleton className="h-72" />
      ) : !data?.length ? (
        <EmptyState title="No records" description="No attendance has been recorded for you yet." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Date</TableHead><TableHead>Status</TableHead>
              <TableHead>In</TableHead><TableHead>Out</TableHead><TableHead>Remarks</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {data.map((r) => (
                <TableRow key={r.id}>
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
    </>
  );
}
