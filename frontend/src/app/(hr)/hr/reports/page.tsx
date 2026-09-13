"use client";

import * as React from "react";

import { useHRReportIndex, useHRReport, useHRCan } from "@/hooks/use-hr";
import { API } from "@/lib/config";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function HRReportsPage() {
  const { data: index, isLoading: idxLoading } = useHRReportIndex();
  const [slug, setSlug] = React.useState<string | undefined>();
  const { data: report, isLoading, isError, refetch } = useHRReport(slug);
  const canExport = useHRCan("reports.hr.export");

  React.useEffect(() => {
    if (!slug && index?.reports?.length) setSlug(index.reports[0].slug);
  }, [index, slug]);

  return (
    <>
      <PageHeader
        title="HR Reports"
        description="Filter, view and export workforce data."
        actions={
          slug ? (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" asChild>
                <a href={API.hrReport(slug, "?format=csv")}>Export CSV</a>
              </Button>
              {canExport ? (
                <Button variant="outline" size="sm" asChild>
                  <a href={API.hrReport(slug, "?format=pdf")} target="_blank" rel="noreferrer">Export PDF</a>
                </Button>
              ) : null}
            </div>
          ) : undefined
        }
      />

      {idxLoading ? (
        <Skeleton className="h-10 w-64" />
      ) : (
        <Select value={slug} onValueChange={setSlug}>
          <SelectTrigger className="w-72"><SelectValue placeholder="Choose a report" /></SelectTrigger>
          <SelectContent>
            {index?.reports?.map((r) => (
              <SelectItem key={r.slug} value={r.slug}>
                {r.slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-96" />
      ) : report ? (
        <>
          <h2 className="text-lg font-semibold">{report.title}</h2>
          <p className="text-sm text-muted-foreground">{report.rows.length} rows</p>
          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader><TableRow>
                {report.columns.map(([key, label]) => <TableHead key={key}>{label}</TableHead>)}
              </TableRow></TableHeader>
              <TableBody>
                {report.rows.map((row, i) => (
                  <TableRow key={i}>
                    {report.columns.map(([key]) => (
                      <TableCell key={key}>{String(row[key] ?? "")}</TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      ) : null}
    </>
  );
}
