"use client";

import * as React from "react";
import { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type ColumnDef } from "@tanstack/react-table";
import { Download, FileText, Lock } from "lucide-react";

import type { StudentReportCard } from "@/lib/types";
import { ApiError } from "@/lib/api";
import {
  downloadReportCardPdf,
  useChildReportCards,
  useChildren,
} from "@/hooks/use-portal";
import { PageHeader } from "@/components/page-header";
import { DataTable } from "@/components/data-table";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
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

function DownloadButton({
  childId,
  report,
  childName,
}: {
  childId: string;
  report: StudentReportCard;
  childName: string;
}) {
  const [downloading, setDownloading] = React.useState(false);

  return (
    <Button
      size="sm"
      variant="outline"
      disabled={downloading}
      onClick={async () => {
        setDownloading(true);
        try {
          const label = (report.term ?? report.name).replace(/\s+/g, "_");
          await downloadReportCardPdf(
            childId,
            report.id,
            `${childName.replace(/\s+/g, "_")}_${label}_Report.pdf`,
          );
        } finally {
          setDownloading(false);
        }
      }}
    >
      <Download /> {downloading ? "Preparing…" : "Download PDF"}
    </Button>
  );
}

function ResultsView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const childParam = searchParams.get("child") ?? undefined;

  const { data: children, isLoading: childrenLoading } = useChildren();
  const selectedChildId =
    childParam ?? (children && children.length > 0 ? children[0].id : undefined);

  const selectedChild = children?.find((c) => c.id === selectedChildId);

  const {
    data: reportCards,
    isLoading,
    isError,
    error,
    refetch,
  } = useChildReportCards(selectedChildId);

  const locked = error instanceof ApiError && error.status === 402;
  const outstandingBalance =
    locked && error.data && typeof error.data === "object" && "outstanding_balance" in error.data
      ? (error.data as { outstanding_balance: string }).outstanding_balance
      : null;

  const onChildChange = (id: string) => {
    router.replace(`/parent/results?child=${id}`);
  };

  const columns: ColumnDef<StudentReportCard>[] = [
    { accessorKey: "term", header: "Term", cell: ({ row }) => row.original.term ?? "—" },
    { accessorKey: "name", header: "Exam / Report" },
    {
      accessorKey: "generated_at",
      header: "Generated",
      cell: ({ row }) =>
        row.original.generated_at
          ? new Date(row.original.generated_at).toLocaleDateString(undefined, {
              year: "numeric",
              month: "long",
              day: "numeric",
            })
          : "—",
    },
    {
      id: "actions",
      header: "",
      enableSorting: false,
      cell: ({ row }) =>
        selectedChildId && selectedChild ? (
          <DownloadButton
            childId={selectedChildId}
            report={row.original}
            childName={selectedChild.full_name}
          />
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        title="Report Cards"
        description="Download your child's report cards by term."
      />

      <div className="max-w-xs">
        {childrenLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : children && children.length > 0 ? (
          <Select value={selectedChildId} onValueChange={onChildChange}>
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

      {!childrenLoading && (!children || children.length === 0) ? (
        <EmptyState
          title="No children linked"
          description="Contact the school office to link your children to your account."
        />
      ) : locked ? (
        <EmptyState
          icon={Lock}
          title="Results locked"
          description={`Report cards are withheld until outstanding fees are settled.${
            outstandingBalance ? ` Balance due: ${money(outstandingBalance)}.` : ""
          }`}
          action={
            selectedChildId ? (
              <Button asChild variant="outline">
                <Link href={`/parent/fees?child=${selectedChildId}`}>View fees & payments</Link>
              </Button>
            ) : undefined
          }
        />
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-64" />
        </div>
      ) : reportCards && reportCards.length > 0 ? (
        <DataTable
          columns={columns}
          data={reportCards}
          searchable={reportCards.length > 8}
          searchPlaceholder="Search report cards…"
          emptyTitle="No report cards"
        />
      ) : (
        <EmptyState
          icon={FileText}
          title="No report cards yet"
          description="Report cards appear here once the school publishes and generates them."
        />
      )}
    </>
  );
}

export default function ParentResultsPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-4">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-72" />
        </div>
      }
    >
      <ResultsView />
    </Suspense>
  );
}
