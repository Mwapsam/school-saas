"use client";

import Link from "next/link";
import {
  Users, GraduationCap, Briefcase, CalendarCheck, CalendarX,
  FileSignature, UserPlus, ListChecks, Clock,
} from "lucide-react";

import { useHRDashboard } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { ErrorState, EmptyState } from "@/components/states";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

const CARD_DEFS: { key: string; label: string; icon: typeof Users; accent?: "primary" | "warning" | "destructive" | "success" }[] = [
  { key: "total_active", label: "Active employees", icon: Users },
  { key: "teaching_staff", label: "Teaching staff", icon: GraduationCap },
  { key: "non_teaching_staff", label: "Non-teaching staff", icon: Briefcase },
  { key: "present_today", label: "Present today", icon: CalendarCheck, accent: "success" },
  { key: "absent_today", label: "Absent today", icon: CalendarX, accent: "destructive" },
  { key: "on_leave", label: "On leave", icon: CalendarCheck },
  { key: "on_probation", label: "On probation", icon: Clock, accent: "warning" },
  { key: "contracts_expiring_soon", label: "Contracts expiring", icon: FileSignature, accent: "warning" },
  { key: "new_this_term", label: "New this term", icon: UserPlus },
  { key: "pending_leave_requests", label: "Pending leave", icon: CalendarCheck, accent: "warning" },
  { key: "pending_hr_tasks", label: "Open HR tasks", icon: ListChecks, accent: "warning" },
  { key: "notice_period", label: "On notice", icon: CalendarX, accent: "warning" },
  { key: "appraisals_due", label: "Appraisals due", icon: Clock, accent: "warning" },
  { key: "employees_exiting", label: "Employees exiting", icon: CalendarX, accent: "warning" },
];

function AlertList({
  title, rows, render, empty,
}: {
  title: string;
  rows: Record<string, unknown>[] | undefined;
  render: (row: Record<string, unknown>) => React.ReactNode;
  empty: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">
          {title}
          {rows?.length ? (
            <Badge variant="secondary" className="ml-2">{rows.length}</Badge>
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {!rows?.length ? (
          <p className="text-muted-foreground">{empty}</p>
        ) : (
          rows.slice(0, 8).map((row, i) => <div key={i}>{render(row)}</div>)
        )}
      </CardContent>
    </Card>
  );
}

export default function HRDashboardPage() {
  const { data, isLoading, isError, refetch } = useHRDashboard();

  if (isError) {
    return (
      <>
        <PageHeader title="HR Dashboard" />
        <ErrorState onRetry={() => refetch()} />
      </>
    );
  }

  const cards = data?.cards ?? {};
  const alerts = data?.alerts;

  return (
    <>
      <PageHeader
        title="HR Dashboard"
        description="Workforce snapshot and items that need HR attention."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {CARD_DEFS.filter((d) => isLoading || cards[d.key] != null).map((d) => (
          <StatCard
            key={d.key}
            label={d.label}
            value={cards[d.key] ?? 0}
            icon={d.icon}
            loading={isLoading}
            accent={d.accent}
          />
        ))}
      </div>

      <h2 className="mt-8 text-lg font-semibold">HR attention required</h2>
      {isLoading ? (
        <div className="grid gap-4 lg:grid-cols-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-48" />)}
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          <AlertList
            title="Contracts expiring"
            rows={alerts?.contracts_expiring}
            empty="No contracts expiring in the next 90 days."
            render={(r) => (
              <Link href={`/hr/employees/${r.id}`} className="flex justify-between hover:underline">
                <span>{String(r.name)}</span>
                <span className="text-muted-foreground">{String(r.days_remaining)}d</span>
              </Link>
            )}
          />
          <AlertList
            title="Probation reviews due"
            rows={alerts?.probation_reviews_due}
            empty="No probation reviews due."
            render={(r) => (
              <Link href={`/hr/employees/${r.id}`} className="flex justify-between hover:underline">
                <span>{String(r.name)}</span>
                <span className="text-muted-foreground">{String(r.probation_end_date)}</span>
              </Link>
            )}
          />
          <AlertList
            title="Documents expiring"
            rows={alerts?.documents_expiring}
            empty="No documents expiring soon."
            render={(r) => (
              <Link href={`/hr/employees/${r.id}`} className="flex justify-between hover:underline">
                <span>{String(r.name)} · {String(r.document_type)}</span>
                <span className="text-muted-foreground">{String(r.expiry_date)}</span>
              </Link>
            )}
          />
          <AlertList
            title="Pending leave approvals"
            rows={alerts?.pending_leave_approvals}
            empty="No leave awaiting a decision."
            render={(r) => (
              <Link href="/hr/leave" className="flex justify-between hover:underline">
                <span>{String(r.name)}</span>
                <Badge variant="outline">{String(r.stage)}</Badge>
              </Link>
            )}
          />
          <AlertList
            title="Attendance watchlist"
            rows={alerts?.attendance_watchlist}
            empty="No repeated lateness or absence."
            render={(r) => (
              <Link href={`/hr/employees/${r.id}`} className="flex justify-between hover:underline">
                <span>{String(r.name)}</span>
                <span className="text-muted-foreground">
                  {String(r.late_count)} late · {String(r.absent_count)} abs
                </span>
              </Link>
            )}
          />
          <AlertList
            title="Open HR tasks"
            rows={alerts?.open_tasks}
            empty="No open tasks."
            render={(r) => (
              <Link href="/hr/tasks" className="flex justify-between hover:underline">
                <span>{String(r.title)}</span>
                <span className="text-muted-foreground">{r.due_date ? String(r.due_date) : "—"}</span>
              </Link>
            )}
          />
          <AlertList
            title="Missing documents"
            rows={alerts?.documents_missing}
            empty="Every employee has their required documents."
            render={(r) => (
              <Link href={`/hr/employees/${r.id}`} className="flex justify-between gap-2 hover:underline">
                <span>{String(r.name)}</span>
                <span className="text-right text-muted-foreground">
                  {Array.isArray(r.missing) ? (r.missing as string[]).join(", ") : ""}
                </span>
              </Link>
            )}
          />
          <AlertList
            title="Appraisals due"
            rows={alerts?.appraisals_due}
            empty="No overdue appraisals."
            render={(r) => (
              <Link href={`/hr/performance/${String(r.review_id)}`} className="flex justify-between hover:underline">
                <span>{String(r.name)}</span>
                <span className="text-muted-foreground">{String(r.review_date ?? "")}</span>
              </Link>
            )}
          />
          <AlertList
            title="Onboarding outstanding"
            rows={alerts?.onboarding_outstanding}
            empty="No onboarding in progress."
            render={(r) => (
              <Link href={`/hr/employees/${r.id}`} className="flex justify-between hover:underline">
                <span>{String(r.name)}</span>
                <span className="text-muted-foreground">
                  {r.progress != null ? `${String(r.progress)}%` : ""}
                </span>
              </Link>
            )}
          />
          <AlertList
            title="Training expiring"
            rows={alerts?.training_expiring}
            empty="No training or certifications expiring soon."
            render={(r) => (
              <Link href={`/hr/employees/${r.id}`} className="flex justify-between hover:underline">
                <span>{String(r.name)}{r.training ? ` · ${String(r.training)}` : ""}</span>
                <span className="text-muted-foreground">{String(r.expiry_date ?? "")}</span>
              </Link>
            )}
          />
          <AlertList
            title="Exit clearance outstanding"
            rows={alerts?.exit_clearance_outstanding}
            empty="No exit clearances pending."
            render={(r) => (
              <Link href={`/hr/employees/${r.id}`} className="flex justify-between hover:underline">
                <span>{String(r.name)}</span>
                <span className="text-muted-foreground">
                  {r.progress != null ? `${String(r.progress)}%` : ""}
                </span>
              </Link>
            )}
          />
        </div>
      )}

      {!isLoading && !alerts ? (
        <EmptyState title="No data yet" description="The dashboard will populate as HR records are added." />
      ) : null}
    </>
  );
}
