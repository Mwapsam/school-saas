"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { useHRPayslip } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function PayslipDetailPage() {
  const { payslipId } = useParams<{ payslipId: string }>();
  const { data, isLoading, isError, refetch } = useHRPayslip(payslipId);

  if (isError) {
    return (
      <>
        <PageHeader title="Payslip" />
        <ErrorState onRetry={() => refetch()} />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={isLoading ? "Payslip" : `${data?.employee_name}`}
        description={data ? `${data.period_start} → ${data.period_end} · ${data.payroll_group ?? ""}` : undefined}
        actions={
          <div className="flex items-center gap-2 print:hidden">
            {data && <Badge variant="secondary">{data.status}</Badge>}
            <Button variant="outline" onClick={() => window.print()}>Print</Button>
            <Button variant="ghost" asChild><Link href="/hr/payroll">Back</Link></Button>
          </div>
        }
      />

      {isLoading || !data ? (
        <Skeleton className="h-80" />
      ) : (
        <div className="space-y-6">
          <Card><CardContent className="grid gap-4 p-6 sm:grid-cols-3">
            <Meta label="Employee no." value={data.employee_number} />
            <Meta label="Basic pay" value={String(data.basic_pay)} />
            <Meta label="Version" value={String(data.version)} />
            <Meta label="Gross earnings" value={String(data.gross_earnings)} />
            <Meta label="Total deductions" value={String(data.total_deductions)} />
            <Meta label="Net pay" value={String(data.net_pay)} />
          </CardContent></Card>

          <div className="rounded-lg border">
            <Table>
              <TableHeader><TableRow>
                <TableHead>Component</TableHead><TableHead>Type</TableHead>
                <TableHead className="text-right">Amount</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {data.line_items.map((li) => (
                  <TableRow key={li.id}>
                    <TableCell>{li.name}</TableCell>
                    <TableCell>
                      <Badge variant={li.type === "deduction" ? "destructive" : "outline"}>
                        {li.type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">{li.amount}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {data.rejection_reason && (
            <p className="text-sm text-destructive">Rejected: {data.rejection_reason}</p>
          )}
        </div>
      )}
    </>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-sm font-medium">{value || "—"}</p>
    </div>
  );
}
