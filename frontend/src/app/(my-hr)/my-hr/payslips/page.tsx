"use client";

import * as React from "react";

import { useMyPayslips, useMyPayslip } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sheet, SheetContent, SheetTitle, SheetTrigger,
} from "@/components/ui/sheet";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function MyPayslipsPage() {
  const { data, isLoading, isError, refetch } = useMyPayslips();

  return (
    <>
      <PageHeader title="My Payslips" description="Your processed payslips." />
      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-64" />
      ) : !data?.length ? (
        <EmptyState title="No payslips yet" description="Payslips appear here once payroll processes them." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Period</TableHead><TableHead>Gross</TableHead>
              <TableHead>Deductions</TableHead><TableHead>Net pay</TableHead>
              <TableHead>Status</TableHead><TableHead />
            </TableRow></TableHeader>
            <TableBody>
              {data.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>{p.period_start} → {p.period_end}</TableCell>
                  <TableCell>{p.gross_earnings}</TableCell>
                  <TableCell>{p.total_deductions}</TableCell>
                  <TableCell className="font-medium">{p.net_pay}</TableCell>
                  <TableCell><Badge variant="secondary">{p.status}</Badge></TableCell>
                  <TableCell className="text-right"><PayslipSheet id={p.id} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}

function PayslipSheet({ id }: { id: string }) {
  const [open, setOpen] = React.useState(false);
  const { data } = useMyPayslip(open ? id : undefined);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild><Button variant="ghost" size="sm">View</Button></SheetTrigger>
      <SheetContent>
        <SheetTitle>Payslip</SheetTitle>
        {!data ? (
          <Skeleton className="mt-4 h-64" />
        ) : (
          <div className="mt-4 space-y-4 text-sm">
            <p className="text-muted-foreground">{data.period_start} → {data.period_end}</p>
            <Table>
              <TableHeader><TableRow>
                <TableHead>Component</TableHead><TableHead className="text-right">Amount</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {data.line_items.map((li) => (
                  <TableRow key={li.id}>
                    <TableCell>{li.name}{li.type === "deduction" ? " (−)" : ""}</TableCell>
                    <TableCell className="text-right">{li.amount}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="flex justify-between border-t pt-2 font-medium">
              <span>Net pay</span><span>{data.net_pay}</span>
            </div>
            <Button variant="outline" className="w-full" onClick={() => window.print()}>Print</Button>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
