"use client";

import * as React from "react";
import { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type ColumnDef } from "@tanstack/react-table";
import { FileText, Printer, Wallet } from "lucide-react";

import type { FeeStatementLine } from "@/lib/types";
import { useChildFees, useChildren } from "@/hooks/use-portal";
import { PageHeader } from "@/components/page-header";
import { DataTable } from "@/components/data-table";
import { EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const money = (v: string | number | null | undefined) =>
  Number(v ?? 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

const columns: ColumnDef<FeeStatementLine>[] = [
  {
    accessorKey: "date",
    header: "Date",
    cell: ({ row }) =>
      row.original.date
        ? new Date(row.original.date).toLocaleDateString()
        : "—",
  },
  {
    accessorKey: "type",
    header: "Type",
    cell: ({ row }) => (
      <Badge variant="secondary" className="capitalize">
        {row.original.type}
      </Badge>
    ),
  },
  { accessorKey: "fee_category", header: "Category" },
  { accessorKey: "description", header: "Description", enableSorting: false },
  {
    accessorKey: "debit",
    header: "Charge",
    cell: ({ row }) =>
      Number(row.original.debit) ? money(row.original.debit) : "—",
  },
  {
    accessorKey: "credit",
    header: "Paid / Credit",
    cell: ({ row }) =>
      Number(row.original.credit) ? money(row.original.credit) : "—",
  },
];

function SummaryCard({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className={`text-2xl font-semibold ${tone ?? ""}`}>{value}</p>
      </CardContent>
    </Card>
  );
}

function FeesView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const childParam = searchParams.get("child") ?? undefined;
  const yearParam = searchParams.get("year") ?? undefined;

  const { data: children, isLoading: childrenLoading } = useChildren();
  const selectedChildId =
    childParam ?? (children && children.length > 0 ? children[0].id : undefined);

  const { data, isLoading, isError, refetch } = useChildFees(
    selectedChildId,
    yearParam,
  );

  const setParams = (childId?: string, year?: string) => {
    const params = new URLSearchParams();
    if (childId) params.set("child", childId);
    if (year) params.set("year", year);
    router.replace(`/parent/fees?${params.toString()}`);
  };

  const statement = data?.statement ?? null;

  return (
    <>
      <PageHeader
        title="Fees & Payments"
        description="Charges, payments and outstanding balance for the selected academic year."
        actions={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => window.print()} disabled={!statement}>
              <Printer /> Print Statement
            </Button>
            <Button asChild variant="outline">
              <Link href="/parent/invoices">
                <FileText /> View Invoices
              </Link>
            </Button>
          </div>
        }
      />

      <div className="flex flex-wrap gap-3">
        <div className="w-full max-w-xs">
          {childrenLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : children && children.length > 0 ? (
            <Select
              value={selectedChildId}
              onValueChange={(id) => setParams(id, yearParam)}
            >
              <SelectTrigger aria-label="Select child">
                <SelectValue placeholder="Select a child" />
              </SelectTrigger>
              <SelectContent>
                {children.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.full_name}
                    {c.current_batch ? ` · ${c.current_batch.name}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}
        </div>

        {data && data.academic_years.length > 0 ? (
          <div className="w-full max-w-xs">
            <Select
              value={data.selected_year?.id}
              onValueChange={(year) => setParams(selectedChildId, year)}
            >
              <SelectTrigger aria-label="Select academic year">
                <SelectValue placeholder="Academic year" />
              </SelectTrigger>
              <SelectContent>
                {data.academic_years.map((y) => (
                  <SelectItem key={y.id} value={y.id}>
                    {y.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}
      </div>

      {!childrenLoading && (!children || children.length === 0) ? (
        <EmptyState
          title="No children linked"
          description="Contact the school office to link your children to your account."
        />
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-64" />
        </div>
      ) : statement ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <SummaryCard label="Total Charged" value={money(statement.total_charged)} />
            <SummaryCard label="Total Paid" value={money(statement.total_paid)} tone="text-green-600" />
            <SummaryCard label="Discounts / Waivers" value={money(statement.total_discounts)} />
            <SummaryCard
              label="Outstanding Balance"
              value={money(statement.current_outstanding)}
              tone={Number(statement.current_outstanding) > 0 ? "text-red-600" : "text-green-600"}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Statement · {statement.academic_year}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <DataTable
                columns={columns}
                data={statement.line_items}
                searchable={statement.line_items.length > 8}
                searchPlaceholder="Search activity…"
                emptyTitle="No fee activity this year"
              />
            </CardContent>
          </Card>
        </div>
      ) : (
        <EmptyState
          icon={Wallet}
          title="No fee records"
          description="There are no fee records for the selected academic year."
        />
      )}
    </>
  );
}

export default function ParentFeesPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-4">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-64" />
        </div>
      }
    >
      <FeesView />
    </Suspense>
  );
}
