"use client";

import * as React from "react";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CalendarDays, CheckCheck, Save } from "lucide-react";
import { toast } from "sonner";

import type {
  AttendanceStatus,
  RegisterEntry,
  SaveAttendancePayload,
} from "@/lib/types";
import { ApiError } from "@/lib/api";
import { useRegister, useSaveAttendance, useTeacherClasses } from "@/hooks/use-portal";
import { PageHeader } from "@/components/page-header";
import { AttendanceStatusControl } from "@/components/attendance-status-control";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Concrete = Exclude<AttendanceStatus, "unmarked">;
type StatusMap = Record<string, AttendanceStatus>;

function localToday() {
  const d = new Date();
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60_000).toISOString().slice(0, 10);
}

function RegisterView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const classParam = searchParams.get("class") ?? undefined;

  const [date, setDate] = React.useState(localToday());
  const [statuses, setStatuses] = React.useState<StatusMap>({});
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  const { data: classes, isLoading: classesLoading } = useTeacherClasses();
  const classTeacherClasses = React.useMemo(
    () => (classes ?? []).filter(c => c.is_class_teacher),
    [classes]
  );
  const selectedClassId =
    classParam ?? (classTeacherClasses && classTeacherClasses.length > 0 ? classTeacherClasses[0].id : undefined);

  const {
    data: register,
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useRegister(selectedClassId, date);

  const save = useSaveAttendance(selectedClassId ?? "");

  // Seed local edit state whenever a fresh register loads.
  React.useEffect(() => {
    if (!register) return;
    const next: StatusMap = {};
    for (const e of register.entries) next[e.student_id] = e.status;
    setStatuses(next);
  }, [register]);

  const onClassChange = (id: string) => {
    router.replace(`/teacher/attendance?class=${id}`);
  };

  const setStatus = (studentId: string, status: Concrete) => {
    setStatuses((prev) => ({ ...prev, [studentId]: status }));
  };

  const markAllPresent = () => {
    if (!register) return;
    const next: StatusMap = {};
    for (const e of register.entries) next[e.student_id] = "present";
    setStatuses(next);
  };

  const entries = register?.entries ?? [];
  const markedCount = entries.filter(
    (e) => statuses[e.student_id] && statuses[e.student_id] !== "unmarked",
  ).length;
  const presentCount = entries.filter(
    (e) => statuses[e.student_id] === "present" || statuses[e.student_id] === "late",
  ).length;

  const isDirty = React.useMemo(() => {
    if (!register) return false;
    return register.entries.some((e) => statuses[e.student_id] !== e.status);
  }, [register, statuses]);

  const onSave = async () => {
    const payload: SaveAttendancePayload = {
      date,
      entries: entries
        .filter((e) => statuses[e.student_id] && statuses[e.student_id] !== "unmarked")
        .map((e) => ({
          student_id: e.student_id,
          status: statuses[e.student_id] as Concrete,
        })),
    };
    try {
      const res = await save.mutateAsync(payload);
      toast.success(`Attendance saved for ${res.saved} students.`);
      setConfirmOpen(false);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Could not save attendance.";
      toast.error(message);
    }
  };

  return (
    <>
      <PageHeader
        title="Attendance Register"
        description="Take and update attendance for your classes."
        actions={
          <Button variant="outline" onClick={markAllPresent} disabled={!entries.length}>
            <CheckCheck /> Mark all present
          </Button>
        }
      />

      <Card>
        <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-2">
            <Label htmlFor="class">Class</Label>
            {classesLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : classTeacherClasses.length > 0 ? (
              <Select value={selectedClassId} onValueChange={onClassChange}>
                <SelectTrigger id="class" aria-label="Select class">
                  <SelectValue placeholder="Select a class" />
                </SelectTrigger>
                <SelectContent>
                  {classTeacherClasses.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name} · {c.student_count} students
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : null}
          </div>
          <div className="space-y-2 sm:w-48">
            <Label htmlFor="date">Date</Label>
            <div className="relative">
              <CalendarDays className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="date"
                type="date"
                value={date}
                max={localToday()}
                onChange={(e) => setDate(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {!classesLoading && classTeacherClasses.length === 0 ? (
        <EmptyState
          title="No classes to manage"
          description="Attendance registers are only available to class teachers. You are currently a subject teacher."
        />
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : (
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">
              {register?.batch.name ?? "Roster"}
            </CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">{markedCount} marked</Badge>
              <Badge variant="success">{presentCount} present</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : entries.length === 0 ? (
              <EmptyState
                title="No students in this class"
                description="Add students to this class in the admin app first."
              />
            ) : (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">#</TableHead>
                      <TableHead>Student</TableHead>
                      <TableHead className="text-right">Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entries.map((entry: RegisterEntry, index) => (
                      <TableRow key={entry.student_id}>
                        <TableCell className="text-muted-foreground">
                          {entry.roll_number || index + 1}
                        </TableCell>
                        <TableCell>
                          <div className="font-medium">{entry.full_name}</div>
                          <div className="text-xs text-muted-foreground">
                            {entry.admission_no}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex justify-end">
                            <AttendanceStatusControl
                              studentName={entry.full_name}
                              value={statuses[entry.student_id] ?? "unmarked"}
                              onChange={(s) => setStatus(entry.student_id, s)}
                            />
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Sticky save bar */}
      {entries.length > 0 ? (
        <div className="sticky bottom-4 z-20 flex items-center justify-between gap-4 rounded-lg border bg-background/95 p-4 shadow-lg backdrop-blur">
          <p className="text-sm text-muted-foreground">
            {isDirty ? "You have unsaved changes." : "All changes saved."}
            {isFetching ? " · Refreshing…" : ""}
          </p>
          <Button
            onClick={() => setConfirmOpen(true)}
            disabled={!isDirty || markedCount === 0 || save.isPending}
          >
            <Save /> Save attendance
          </Button>
        </div>
      ) : null}

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Submit attendance?"
        description={`This will record attendance for ${markedCount} student${
          markedCount === 1 ? "" : "s"
        } on ${date}. This action is logged.`}
        confirmLabel="Save attendance"
        loading={save.isPending}
        onConfirm={onSave}
      />
    </>
  );
}

export default function TeacherAttendancePage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-4">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-96" />
        </div>
      }
    >
      <RegisterView />
    </Suspense>
  );
}
