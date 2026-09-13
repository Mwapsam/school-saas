"use client";

import * as React from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Download, FileText } from "lucide-react";

import type { FamilyInvoice } from "@/lib/types";
import { downloadInvoicePdf, useParentInvoices } from "@/hooks/use-portal";
import { PageHeader } from "@/components/page-header";
import { DataTable } from "@/components/data-table";
import { EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

const money = (v: string | number | null | undefined) =>
  Number(v ?? 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

const statusVariant = (status: FamilyInvoice["status"]) =>
  status === "paid" ? "success" : status === "void" ? "secondary" : "warning";

function DownloadButton({ invoice }: { invoice: FamilyInvoice }) {
  const [downloading, setDownloading] = React.useState(false);

  return (
    <Button
      size="sm"
      variant="outline"
      disabled={downloading}
      onClick={async () => {
        setDownloading(true);
        try {
          await downloadInvoicePdf(invoice.id, invoice.invoice_number);
        } finally {
          setDownloading(false);
        }
      }}
    >
      <Download /> {downloading ? "Preparing…" : "Download PDF"}
    </Button>
  );
}

const columns: ColumnDef<FamilyInvoice>[] = [
  { accessorKey: "invoice_number", header: "Fee Note #" },
  { accessorKey: "academic_year", header: "Academic Year" },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <Badge variant={statusVariant(row.original.status)} className="capitalize">
        {row.original.status}
      </Badge>
    ),
  },
  {
    accessorKey: "total_amount",
    header: "Total",
    cell: ({ row }) => money(row.original.total_amount),
  },
  {
    accessorKey: "amount_paid",
    header: "Paid",
    cell: ({ row }) => money(row.original.amount_paid),
  },
  {
    accessorKey: "balance_due",
    header: "Balance Due",
    cell: ({ row }) => (
      <span className={Number(row.original.balance_due) > 0 ? "text-red-600" : "text-green-600"}>
        {money(row.original.balance_due)}
      </span>
    ),
  },
  {
    id: "actions",
    header: "",
    enableSorting: false,
    cell: ({ row }) => <DownloadButton invoice={row.original} />,
  },
];

export default function ParentInvoicesPage() {
  const { data: invoices, isLoading, isError, refetch } = useParentInvoices();

  return (
    <>
      <PageHeader
        title="Fee Notes"
        description="Consolidated fee notes covering all your children, one per academic year."
      />

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-64" />
        </div>
      ) : invoices && invoices.length > 0 ? (
        <DataTable
          columns={columns}
          data={invoices}
          searchable={invoices.length > 8}
          searchPlaceholder="Search fee notes…"
          emptyTitle="No fee notes"
        />
      ) : (
        <EmptyState
          icon={FileText}
          title="No fee notes yet"
          description="Your school publishes a fee note once fees are finalized for a billing period. Check back once one is published."
        />
      )}
    </>
  );
}
