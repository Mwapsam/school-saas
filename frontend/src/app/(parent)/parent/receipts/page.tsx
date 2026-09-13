"use client";

import * as React from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Download, Receipt as ReceiptIcon } from "lucide-react";

import type { Receipt } from "@/lib/types";
import { downloadReceiptPdf, useParentReceipts } from "@/hooks/use-portal";
import { PageHeader } from "@/components/page-header";
import { DataTable } from "@/components/data-table";
import { EmptyState, ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

const money = (v: string | number | null | undefined) =>
  Number(v ?? 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

function DownloadButton({ receipt }: { receipt: Receipt }) {
  const [downloading, setDownloading] = React.useState(false);

  return (
    <Button
      size="sm"
      variant="outline"
      disabled={downloading}
      onClick={async () => {
        setDownloading(true);
        try {
          await downloadReceiptPdf(receipt.reference_number);
        } finally {
          setDownloading(false);
        }
      }}
    >
      <Download /> {downloading ? "Preparing…" : "Download PDF"}
    </Button>
  );
}

const columns: ColumnDef<Receipt>[] = [
  { accessorKey: "reference_number", header: "Receipt #" },
  { accessorKey: "student_name", header: "Student" },
  {
    accessorKey: "paid_on",
    header: "Paid On",
    cell: ({ row }) => new Date(row.original.paid_on).toLocaleDateString(),
  },
  {
    accessorKey: "total_amount",
    header: "Amount",
    cell: ({ row }) => money(row.original.total_amount),
  },
  {
    id: "actions",
    header: "",
    enableSorting: false,
    cell: ({ row }) => <DownloadButton receipt={row.original} />,
  },
];

export default function ParentReceiptsPage() {
  const { data: receipts, isLoading, isError, refetch } = useParentReceipts();

  return (
    <>
      <PageHeader
        title="Receipts"
        description="Payment receipts for all your children, available as soon as a payment is recorded."
      />

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-64" />
        </div>
      ) : receipts && receipts.length > 0 ? (
        <DataTable
          columns={columns}
          data={receipts}
          searchable={receipts.length > 8}
          searchPlaceholder="Search receipts…"
          emptyTitle="No receipts"
        />
      ) : (
        <EmptyState
          icon={ReceiptIcon}
          title="No receipts yet"
          description="A receipt appears here as soon as a payment is recorded for one of your children."
        />
      )}
    </>
  );
}
