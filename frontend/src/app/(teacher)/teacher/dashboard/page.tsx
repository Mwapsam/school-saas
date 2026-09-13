"use client";

import Link from "next/link";
import { CheckCircle2, ClipboardList, School, Users } from "lucide-react";

import { useTeacherDashboard } from "@/hooks/use-portal";
import { useAuth } from "@/hooks/use-auth";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { EmptyState, ErrorState } from "@/components/states";
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

export default function TeacherDashboardPage() {
  const { user } = useAuth();
  const { data, isLoading, isError, refetch } = useTeacherDashboard();

  const classes = data?.classes ?? [];

  return (
    <>
      <PageHeader
        title={`Welcome${user?.profile?.first_name ? `, ${user.profile.first_name}` : ""}`}
        description="Your classes and today's teaching tasks at a glance."
      />

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard
              label="My classes"
              value={data?.class_count ?? 0}
              icon={School}
              loading={isLoading}
            />
            <StatCard
              label="Total students"
              value={data?.student_count ?? 0}
              icon={Users}
              loading={isLoading}
            />
            <StatCard
              label="Registers marked today"
              value={
                data
                  ? `${data.classes_marked_today} / ${data.class_count}`
                  : "—"
              }
              icon={CheckCircle2}
              accent={
                data && data.classes_marked_today === data.class_count
                  ? "success"
                  : "warning"
              }
              loading={isLoading}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">My classes</CardTitle>
              <CardDescription>
                Jump straight into taking the register for a class.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-16" />
                  <Skeleton className="h-16" />
                </div>
              ) : classes.length === 0 ? (
                <EmptyState
                  icon={School}
                  title="No classes assigned"
                  description="When you are assigned as a class or subject teacher, your classes will appear here."
                />
              ) : (
                <ul className="divide-y rounded-lg border">
                  {classes.map((cls) => (
                    <li
                      key={cls.id}
                      className="flex items-center justify-between gap-4 p-4"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium">{cls.name}</p>
                        <p className="truncate text-sm text-muted-foreground">
                          {cls.course ?? "—"}
                          {cls.academic_year ? ` · ${cls.academic_year}` : ""}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge variant="secondary">
                          {cls.student_count} students
                        </Badge>
                        {cls.is_class_teacher && (
                          <Button asChild size="sm" variant="outline">
                            <Link
                              href={`/teacher/attendance?class=${cls.id}`}
                            >
                              <ClipboardList /> Register
                            </Link>
                          </Button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </>
  );
}
