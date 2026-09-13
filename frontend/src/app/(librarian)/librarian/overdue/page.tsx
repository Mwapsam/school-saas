"use client";

import { useState } from "react";
import { AlertCircle } from "lucide-react";

import { useLibrarianOverdue, useLibrarianLibraries } from "@/hooks/use-portal";
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

export default function OverdueBooksPage() {
  const [libraryId, setLibraryId] = useState<string>("");

  const { data: libraries, isLoading: librariesLoading } =
    useLibrarianLibraries();
  const { data: overdue, isLoading, isError, refetch } = useLibrarianOverdue(
    libraryId || undefined
  );

  const availableLibraries = libraries ?? [];

  const getDaysOverdue = (dueDate: string) => {
    const due = new Date(dueDate).getTime();
    const today = new Date().getTime();
    const days = Math.floor((today - due) / (1000 * 60 * 60 * 24));
    return Math.max(days, 0);
  };

  return (
    <>
      <PageHeader
        title="Overdue Books"
        description="Track books that are due for return."
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
            <CardTitle>Overdue Books</CardTitle>
            <CardDescription>
              {overdue?.length ?? 0} book(s) overdue
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading || librariesLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
              </div>
            ) : overdue && overdue.length > 0 ? (
              <div className="space-y-4">
                {overdue.map((item) => {
                  const daysOverdue = getDaysOverdue(item.due_date);
                  return (
                    <div
                      key={item.id}
                      className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium">
                          {item.book_title}
                        </p>
                        <p className="truncate text-sm text-muted-foreground">
                          {item.borrower_name} ({item.borrower_type})
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Due: {new Date(item.due_date).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge variant="destructive">
                          {daysOverdue} day{daysOverdue !== 1 ? "s" : ""} overdue
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                icon={AlertCircle}
                title="No overdue books"
                description="All books in your libraries are returned on time."
              />
            )}
          </CardContent>
        </Card>
      )}
    </>
  );
}
