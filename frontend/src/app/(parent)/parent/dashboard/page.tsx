"use client";

import Link from "next/link";
import { CalendarCheck, GraduationCap, Lock, TrendingUp, Users } from "lucide-react";

import { useParentDashboard } from "@/hooks/use-portal";
import { useAuth } from "@/hooks/use-auth";
import { formatPercent, initials } from "@/lib/utils";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { EmptyState, ErrorState } from "@/components/states";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const money = (v: string | number | null | undefined) =>
  Number(v ?? 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

export default function ParentDashboardPage() {
  const { user } = useAuth();
  const { data, isLoading, isError, refetch } = useParentDashboard();

  const children = data?.children ?? [];
  const avgAttendance =
    children.length > 0
      ? children.reduce(
          (sum, c) => sum + (c.attendance.attendance_rate ?? 0),
          0,
        ) / children.length
      : null;

  return (
    <>
      <PageHeader
        title={`Welcome${user?.profile?.first_name ? `, ${user.profile.first_name}` : ""}`}
        description="A quick overview of your children's progress."
      />

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard
              label="Children"
              value={children.length}
              icon={Users}
              loading={isLoading}
            />
            <StatCard
              label="Average attendance"
              value={formatPercent(avgAttendance)}
              icon={CalendarCheck}
              accent="success"
              loading={isLoading}
            />
            <StatCard
              label="Published result sets"
              value={children.reduce(
                (s, c) => s + c.published_result_count,
                0,
              )}
              icon={GraduationCap}
              loading={isLoading}
            />
          </div>

          {isLoading ? (
            <div className="grid gap-4 md:grid-cols-2">
              <Skeleton className="h-48" />
              <Skeleton className="h-48" />
            </div>
          ) : children.length === 0 ? (
            <EmptyState
              icon={Users}
              title="No children linked yet"
              description="When your children are linked to your account, their progress will appear here. Contact the school office if this looks wrong."
            />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {children.map(({ child, attendance, latest_result, published_result_count, results_locked, outstanding_balance }) => (
                <Card key={child.id}>
                  <CardHeader className="flex-row items-center gap-3 space-y-0">
                    <Avatar className="h-11 w-11">
                      <AvatarFallback>{initials(child.full_name)}</AvatarFallback>
                    </Avatar>
                    <div className="min-w-0 flex-1">
                      <CardTitle className="truncate text-base">
                        {child.full_name}
                      </CardTitle>
                      <CardDescription className="truncate">
                        {child.current_batch?.name ?? "No class assigned"} ·{" "}
                        {child.admission_no}
                      </CardDescription>
                      {child.guardians && child.guardians.length > 0 && (
                        <CardDescription className="mt-1 truncate text-xs">
                          Other guardian:{" "}
                          {child.guardians
                            .map((g) => g.name)
                            .join(", ")}
                        </CardDescription>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div className="rounded-lg bg-muted/50 p-3">
                        <p className="text-muted-foreground">Attendance</p>
                        <p className="text-lg font-semibold">
                          {formatPercent(attendance.attendance_rate)}
                        </p>
                      </div>
                      <div className="rounded-lg bg-muted/50 p-3">
                        <p className="text-muted-foreground">Result sets</p>
                        <p className="text-lg font-semibold">
                          {results_locked ? "—" : published_result_count}
                        </p>
                      </div>
                    </div>

                    {results_locked ? (
                      <div className="flex items-center justify-between rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-900 dark:bg-amber-950">
                        <div className="flex items-center gap-2">
                          <Lock className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                          <span className="font-medium">Results locked</span>
                        </div>
                        <span className="text-amber-700 dark:text-amber-400">
                          Balance due: {money(outstanding_balance)}
                        </span>
                      </div>
                    ) : latest_result ? (
                      <div className="flex items-center justify-between rounded-lg border p-3 text-sm">
                        <div className="flex items-center gap-2">
                          <TrendingUp className="h-4 w-4 text-primary" />
                          <span className="font-medium">Latest:</span>
                          <span className="text-muted-foreground">
                            {latest_result.name}
                          </span>
                        </div>
                        <Badge variant="secondary">
                          {latest_result.subjects.length} subjects
                        </Badge>
                      </div>
                    ) : null}

                    <Button asChild variant="outline" className="w-full">
                      <Link href={results_locked ? `/parent/fees?child=${child.id}` : `/parent/results?child=${child.id}`}>
                        {results_locked ? "View fees & payments" : "View academic results"}
                      </Link>
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
