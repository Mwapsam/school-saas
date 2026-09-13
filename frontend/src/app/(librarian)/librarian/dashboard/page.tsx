"use client";

import { BookOpen, AlertCircle, CheckCircle2, Users } from "lucide-react";

import { useLibrarianDashboard } from "@/hooks/use-portal";
import { useAuth } from "@/hooks/use-auth";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { EmptyState, ErrorState } from "@/components/states";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function LibrarianDashboardPage() {
  const { user } = useAuth();
  const { data, isLoading, isError, refetch } = useLibrarianDashboard();

  const libraries = data?.libraries ?? [];
  const stats = data?.stats ?? {};

  const totalBooks = Object.values(stats).reduce(
    (sum, lib) => sum + lib.total_books,
    0
  );
  const totalAvailable = Object.values(stats).reduce(
    (sum, lib) => sum + lib.available_books,
    0
  );
  const totalIssued = Object.values(stats).reduce(
    (sum, lib) => sum + lib.issued_books,
    0
  );
  const totalOverdue = Object.values(stats).reduce(
    (sum, lib) => sum + lib.overdue_books,
    0
  );

  return (
    <>
      <PageHeader
        title={`Welcome${user?.profile?.first_name ? `, ${user.profile.first_name}` : ""}`}
        description="Your library collection and borrowing status at a glance."
      />

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Total books"
              value={totalBooks}
              icon={BookOpen}
              loading={isLoading}
            />
            <StatCard
              label="Available"
              value={totalAvailable}
              icon={CheckCircle2}
              loading={isLoading}
              accent="success"
            />
            <StatCard
              label="Issued"
              value={totalIssued}
              icon={Users}
              loading={isLoading}
            />
            <StatCard
              label="Overdue"
              value={totalOverdue}
              icon={AlertCircle}
              loading={isLoading}
              {...(totalOverdue > 0 && { accent: "warning" })}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Your Libraries</CardTitle>
              <CardDescription>
                Libraries you are assigned to manage.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-20" />
                  <Skeleton className="h-20" />
                </div>
              ) : libraries.length === 0 ? (
                <EmptyState
                  icon={BookOpen}
                  title="No libraries assigned"
                  description="When you are assigned to manage a library, it will appear here."
                />
              ) : (
                <ul className="divide-y rounded-lg border">
                  {libraries.map((lib) => {
                    const libStats = stats[lib.id] || {
                      total_books: 0,
                      available_books: 0,
                      issued_books: 0,
                      overdue_books: 0,
                    };
                    return (
                      <li
                        key={lib.id}
                        className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div className="min-w-0">
                          <p className="truncate font-medium">{lib.name}</p>
                          <p className="truncate text-sm text-muted-foreground">
                            {lib.code}
                            {lib.description ? ` • ${lib.description}` : ""}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-4 text-sm">
                          <div>
                            <p className="font-semibold">
                              {libStats.total_books}
                            </p>
                            <p className="text-muted-foreground">Total</p>
                          </div>
                          <div>
                            <p className="font-semibold">
                              {libStats.available_books}
                            </p>
                            <p className="text-muted-foreground">Available</p>
                          </div>
                          <div>
                            <p className="font-semibold">
                              {libStats.issued_books}
                            </p>
                            <p className="text-muted-foreground">Issued</p>
                          </div>
                          {libStats.overdue_books > 0 && (
                            <div className="text-red-600">
                              <p className="font-semibold">
                                {libStats.overdue_books}
                              </p>
                              <p>Overdue</p>
                            </div>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </>
  );
}
