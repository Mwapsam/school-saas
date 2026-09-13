"use client";

import Link from "next/link";

import { useOnboardingList } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { ErrorState, EmptyState } from "@/components/states";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

function Bar({ percent }: { percent: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-32 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${percent}%` }} />
      </div>
      <span className="text-xs text-muted-foreground">{percent}%</span>
    </div>
  );
}

export default function OnboardingPage() {
  const { data, isLoading, isError, refetch } = useOnboardingList();
  const rows = data?.results ?? [];

  return (
    <>
      <PageHeader
        title="Onboarding"
        description="New hires with an onboarding checklist still in progress."
      />

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-72" />
      ) : rows.length === 0 ? (
        <EmptyState title="Nothing in progress" description="Every new hire is fully onboarded." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Employee</TableHead><TableHead>Department</TableHead>
              <TableHead>Started</TableHead><TableHead>Progress</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((o) => (
                <TableRow key={o.id}>
                  <TableCell>
                    <Link href={`/hr/employees/${o.employee_id}`} className="font-medium hover:underline">
                      {o.employee_name}
                    </Link>
                    <span className="ml-2 font-mono text-xs text-muted-foreground">{o.employee_number}</span>
                  </TableCell>
                  <TableCell>{o.department ?? "—"}</TableCell>
                  <TableCell>{o.started_at.slice(0, 10)}</TableCell>
                  <TableCell><Bar percent={o.progress.percent} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}
