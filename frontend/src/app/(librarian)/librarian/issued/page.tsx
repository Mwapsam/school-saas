"use client";

import { useState } from "react";
import { BookOpen } from "lucide-react";

import { useLibrarianIssued, useLibrarianLibraries } from "@/hooks/use-portal";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

export default function IssuedBooksPage() {
  const [libraryId, setLibraryId] = useState<string>("");

  const { data: libraries, isLoading: librariesLoading } =
    useLibrarianLibraries();
  const { data: issued, isLoading, isError, refetch } = useLibrarianIssued(
    libraryId || undefined
  );

  const availableLibraries = libraries ?? [];

  return (
    <>
      <PageHeader
        title="Issued Books"
        description="Books currently on loan across your libraries."
      />

      <div className="flex flex-col gap-4 sm:flex-row">
        <Select value={libraryId} onValueChange={setLibraryId}>
          <SelectTrigger className="w-full sm:w-48">
            <SelectValue placeholder="All libraries" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All libraries</SelectItem>
            {availableLibraries.map((lib) => (
              <SelectItem key={lib.id} value={lib.id}>
                {lib.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Issued Books</CardTitle>
            <CardDescription>
              {issued?.length ?? 0} book(s) on loan
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading || librariesLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
              </div>
            ) : issued && issued.length > 0 ? (
              <div className="space-y-4">
                {issued.map((item) => (
                  <div
                    key={item.id}
                    className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{item.book_title}</p>
                      <p className="truncate text-sm text-muted-foreground">
                        {item.borrower_name} ({item.borrower_type})
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Issued: {new Date(item.issue_date).toLocaleDateString()} ·
                        Due: {new Date(item.due_date).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      {item.is_overdue ? (
                        <Badge variant="destructive">Overdue</Badge>
                      ) : (
                        <Badge variant="secondary">On loan</Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={BookOpen}
                title="No books on loan"
                description="Nothing is currently issued from your libraries."
              />
            )}
          </CardContent>
        </Card>
      )}
    </>
  );
}
