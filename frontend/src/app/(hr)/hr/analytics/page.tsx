"use client";

import * as React from "react";

import { useHRAnalytics } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { ErrorState } from "@/components/states";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const CONTRACT_LABELS: Record<string, string> = {
  permanent: "Permanent",
  fixed_term: "Fixed Term",
  probation: "Probation",
  temporary: "Temporary",
  casual: "Casual",
  consultant: "Consultant / Contract",
  intern: "Internship",
};

function BarRow({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="w-40 shrink-0 truncate text-muted-foreground">{label}</span>
      <div className="h-3 flex-1 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 shrink-0 text-right tabular-nums">{value}</span>
    </div>
  );
}

export default function AnalyticsPage() {
  const [months, setMonths] = React.useState("12");
  const { data, isLoading, isError, refetch } = useHRAnalytics(Number(months));

  return (
    <>
      <PageHeader
        title="HR Analytics"
        description="Workforce, turnover and tenure trends."
        actions={
          <Select value={months} onValueChange={setMonths}>
            <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="6">Last 6 months</SelectItem>
              <SelectItem value="12">Last 12 months</SelectItem>
              <SelectItem value="24">Last 24 months</SelectItem>
            </SelectContent>
          </Select>
        }
      />

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading || !data ? (
        <Skeleton className="h-96" />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Active staff" value={data.headcount.active} />
            <StatCard
              label="Teaching / non-teaching"
              value={`${data.headcount.teaching} / ${data.headcount.non_teaching}`}
            />
            <StatCard
              label="Turnover (12m)"
              value={`${data.turnover.turnover_rate}%`}
              hint={`${data.turnover.exits_12m} exits · ${data.turnover.joiners_12m} joiners`}
              accent={data.turnover.turnover_rate >= 20 ? "warning" : "primary"}
            />
            <StatCard
              label="Attendance rate (30d)"
              value={data.attendance_rate == null ? "—" : `${data.attendance_rate}%`}
            />
          </div>

          <Card>
            <CardHeader><CardTitle>Joiners &amp; leavers by month</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader><TableRow>
                  <TableHead>Month</TableHead>
                  <TableHead className="text-right">Joined</TableHead>
                  <TableHead className="text-right">Left</TableHead>
                  <TableHead className="text-right">Net</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {data.trend.map((t) => (
                    <TableRow key={t.month}>
                      <TableCell>{t.month}</TableCell>
                      <TableCell className="text-right tabular-nums">{t.joined}</TableCell>
                      <TableCell className="text-right tabular-nums">{t.left}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {t.joined - t.left > 0 ? "+" : ""}{t.joined - t.left}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Tenure distribution</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {data.tenure.map((b) => (
                  <BarRow
                    key={b.band}
                    label={b.band}
                    value={b.count}
                    max={Math.max(...data.tenure.map((x) => x.count), 1)}
                  />
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>Contract mix</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {data.contract_mix.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No contracts recorded.</p>
                ) : (
                  data.contract_mix.map((c) => (
                    <BarRow
                      key={c.contract_type}
                      label={CONTRACT_LABELS[c.contract_type] ?? c.contract_type}
                      value={c.count}
                      max={Math.max(...data.contract_mix.map((x) => x.count), 1)}
                    />
                  ))
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>Approved leave days by type (12m)</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {data.leave_days.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No approved leave.</p>
                ) : (
                  data.leave_days.map((l) => (
                    <BarRow
                      key={l.type}
                      label={l.type}
                      value={l.days}
                      max={Math.max(...data.leave_days.map((x) => x.days), 1)}
                    />
                  ))
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>By department</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader><TableRow>
                    <TableHead>Department</TableHead>
                    <TableHead className="text-right">Headcount</TableHead>
                    <TableHead className="text-right">Exits (12m)</TableHead>
                  </TableRow></TableHeader>
                  <TableBody>
                    {data.by_department.map((d) => (
                      <TableRow key={d.department}>
                        <TableCell>{d.department}</TableCell>
                        <TableCell className="text-right tabular-nums">{d.headcount}</TableCell>
                        <TableCell className="text-right tabular-nums">{d.exits_12m}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
