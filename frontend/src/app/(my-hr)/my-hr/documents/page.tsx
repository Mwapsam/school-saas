"use client";

import { useMyDocuments } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function MyDocumentsPage() {
  const { data, isLoading } = useMyDocuments();

  return (
    <>
      <PageHeader title="My Documents" description="Documents HR holds on your file." />
      {isLoading ? (
        <Skeleton className="h-56" />
      ) : !data?.length ? (
        <EmptyState title="No documents" description="Nothing has been uploaded to your file yet." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Type</TableHead><TableHead>Uploaded</TableHead>
              <TableHead>Expiry</TableHead><TableHead>Status</TableHead><TableHead></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {data.map((d) => (
                <TableRow key={d.id}>
                  <TableCell>{d.document_type}</TableCell>
                  <TableCell>{d.uploaded_at.slice(0, 10)}</TableCell>
                  <TableCell>{d.expiry_date ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant={d.status === "expired" ? "destructive" : d.status === "expiring" ? "secondary" : "outline"}>
                      {d.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {d.file_url ? <a href={d.file_url} target="_blank" rel="noreferrer" className="text-sm underline">Open</a> : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}
