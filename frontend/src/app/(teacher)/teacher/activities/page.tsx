"use client";

import * as React from "react";
import { CheckCircle2, Loader2, Save } from "lucide-react";
import { toast } from "sonner";

import type { ActivityRating, SaveActivitiesPayload } from "@/lib/types";
import { ApiError } from "@/lib/api";
import {
  useActivities,
  useSaveActivities,
  useTeacherClasses,
} from "@/hooks/use-portal";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/page-header";
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
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// ── Types ─────────────────────────────────────────────────────────────────────

type SaveStatus = "idle" | "saving" | "saved" | "error";

const NONE = "__none__";

const emptyRating = (): ActivityRating => ({
  submission: "",
  presentation: "",
  effort: "",
});

const splitNames = (s: string): string[] =>
  (s || "").split(",").map((x) => x.trim()).filter(Boolean);

interface RowState {
  homework:  ActivityRating;
  project:   ActivityRating;
  clubs:     string[];
  sports:    string[];
  other:     string[];
}

// ── Sub-components ────────────────────────────────────────────────────────────

function CheckboxPicker({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const all = [...options];
  selected.forEach((s) => { if (!all.includes(s)) all.push(s); });

  const toggle = (name: string) =>
    onChange(
      selected.includes(name)
        ? selected.filter((x) => x !== name)
        : [...selected, name],
    );

  return (
    <div>
      <Label className="text-xs">{label}</Label>
      {all.length === 0 ? (
        <p className="mt-1 text-xs text-muted-foreground">
          No {label.toLowerCase()} configured in the admin app.
        </p>
      ) : (
        <div className="mt-1 flex flex-wrap gap-1.5">
          {all.map((name) => {
            const checked = selected.includes(name);
            return (
              <button
                key={name}
                type="button"
                role="checkbox"
                aria-checked={checked}
                onClick={() => toggle(name)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  checked
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-input bg-background text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
              >
                {name}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function RatingRow({
  title,
  value,
  grades,
  onChange,
}: {
  title: string;
  value: ActivityRating;
  grades: string[];
  onChange: (next: ActivityRating) => void;
}) {
  const fields: (keyof ActivityRating)[] = ["submission", "presentation", "effort"];
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {fields.map((f) => (
          <div key={f}>
            <Label className="text-xs capitalize">{f}</Label>
            <Select
              value={value[f] || NONE}
              onValueChange={(v) =>
                onChange({ ...value, [f]: v === NONE ? "" : v })
              }
            >
              <SelectTrigger className="h-9" aria-label={`${title} ${f}`}>
                <SelectValue placeholder="—" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>—</SelectItem>
                {grades.map((g) => (
                  <SelectItem key={g} value={g}>{g}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ))}
      </div>
    </div>
  );
}

function AutoSaveChip({ status }: { status: SaveStatus }) {
  if (status === "idle") return null;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-all",
        status === "saving" && "bg-muted text-muted-foreground",
        status === "saved"  && "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400",
        status === "error"  && "bg-destructive/10 text-destructive",
      )}
      aria-live="polite"
    >
      {status === "saving" && <Loader2 className="h-3 w-3 animate-spin" />}
      {status === "saved"  && <CheckCircle2 className="h-3 w-3" />}
      {status === "error"  && <span className="font-bold leading-none">!</span>}
      {status === "saving" && "Saving…"}
      {status === "saved"  && "Draft saved"}
      {status === "error"  && "Save failed"}
    </span>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TeacherActivitiesPage() {
  const { data: classes, isLoading: classesLoading } = useTeacherClasses();
  const [batchId, setBatchId]         = React.useState<string>();
  const [examGroupId, setExamGroupId] = React.useState<string>("");
  const [rows, setRows]               = React.useState<Record<string, RowState>>({});
  const [seed, setSeed]               = React.useState("");
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [saveStatus, setSaveStatus]   = React.useState<SaveStatus>("idle");

  // Autosave guards
  const initialSeedDone = React.useRef(false);
  const saveTimer       = React.useRef<ReturnType<typeof setTimeout>>();

  // Stable refs so the timer callback always sees fresh values
  const rowsRef        = React.useRef(rows);
  const examGroupRef   = React.useRef(examGroupId);
  const batchRef       = React.useRef(batchId);
  React.useEffect(() => { rowsRef.current      = rows;        }, [rows]);
  React.useEffect(() => { examGroupRef.current = examGroupId; }, [examGroupId]);
  React.useEffect(() => { batchRef.current     = batchId;     }, [batchId]);

  React.useEffect(() => {
    if (!batchId && classes && classes.length > 0) setBatchId(classes[0].id);
  }, [classes, batchId]);

  const { data, isLoading, isError, refetch, isFetching } = useActivities(
    batchId,
    examGroupId,
  );
  const save = useSaveActivities(batchId ?? "");

  const examGroups = data?.exam_groups ?? [];

  React.useEffect(() => {
    if (examGroups.length > 0 && !examGroupId) setExamGroupId(examGroups[0].id);
  }, [examGroups, examGroupId]);

  // Reset guard whenever the selection changes
  React.useEffect(() => {
    initialSeedDone.current = false;
  }, [batchId, examGroupId]);

  // Seed editable rows from loaded students.
  React.useEffect(() => {
    if (!data?.students) return;
    const next: Record<string, RowState> = {};
    for (const s of data.students) {
      next[s.student_id] = {
        homework: { ...s.homework },
        project:  { ...s.project },
        clubs:    splitNames(s.clubs),
        sports:   splitNames(s.sports),
        other:    splitNames(s.other),
      };
    }
    setRows(next);
    setSeed(JSON.stringify(next));
    setSaveStatus("idle");
    setTimeout(() => { initialSeedDone.current = true; }, 100);
  }, [data]);

  const onClassChange = (id: string) => {
    setBatchId(id);
    setExamGroupId("");
  };

  const setRow = (sid: string, patch: Partial<RowState>) =>
    setRows((prev) => ({ ...prev, [sid]: { ...prev[sid], ...patch } }));

  const students = data?.students ?? [];
  const isDirty  = JSON.stringify(rows) !== seed;
  const grades   = data?.grades ?? [];
  const options  = data?.activity_options ?? { clubs: [], sports: [], other: [] };

  // ── Build payload ─────────────────────────────────────────────────────────

  const buildPayload = React.useCallback(
    (): SaveActivitiesPayload => ({
      exam_group: examGroupRef.current,
      students: (data?.students ?? []).map((s) => {
        const r = rowsRef.current[s.student_id];
        return {
          student_id: s.student_id,
          homework: r?.homework ?? emptyRating(),
          project:  r?.project  ?? emptyRating(),
          clubs:   (r?.clubs  ?? []).join(", "),
          sports:  (r?.sports ?? []).join(", "),
          other:   (r?.other  ?? []).join(", "),
        };
      }),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data],
  );

  // ── Auto-save (2s debounce) ───────────────────────────────────────────────

  React.useEffect(() => {
    if (!initialSeedDone.current || !batchRef.current || !examGroupRef.current) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    setSaveStatus("saving");
    saveTimer.current = setTimeout(async () => {
      try {
        await save.mutateAsync(buildPayload());
        setSaveStatus("saved");
      } catch {
        setSaveStatus("error");
      }
    }, 2000);
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows]);

  // ── Manual save (with confirm dialog) ────────────────────────────────────

  const onSave = async () => {
    try {
      const res = await save.mutateAsync(buildPayload());
      toast.success(`Saved activities for ${res.saved} pupils.`);
      setSaveStatus("saved");
      setConfirmOpen(false);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Could not save activities.",
      );
      setSaveStatus("error");
    }
  };

  return (
    <>
      <PageHeader
        title="Term Activities"
        description="Record homework & project ratings and club, sport and other participation for the report."
      />

      <Card>
        <CardContent className="grid gap-4 p-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="class">Class</Label>
            {classesLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : (
              <Select value={batchId} onValueChange={onClassChange}>
                <SelectTrigger id="class" aria-label="Select class">
                  <SelectValue placeholder="Select a class" />
                </SelectTrigger>
                <SelectContent>
                  {(classes ?? []).map((c) => (
                    <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="examGroup">Term / Exam plan</Label>
            <Select
              value={examGroupId}
              onValueChange={setExamGroupId}
              disabled={examGroups.length === 0}
            >
              <SelectTrigger id="examGroup" aria-label="Select term">
                <SelectValue placeholder="Select a term" />
              </SelectTrigger>
              <SelectContent>
                {examGroups.map((g) => (
                  <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {!classesLoading && (!classes || classes.length === 0) ? (
        <EmptyState
          title="No classes assigned"
          description="You need to be a class teacher to record term activities."
        />
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : !isLoading && examGroups.length === 0 ? (
        <EmptyState
          title="No activated terms"
          description="An exam plan must be activated in the gradebook before you can record activities."
        />
      ) : isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      ) : students.length === 0 ? (
        <EmptyState
          title="No pupils assigned to you"
          description="Ask an administrator to assign students to you as their class teacher in this class."
        />
      ) : (
        <>
          {data?.term ? (
            <p className="text-sm text-muted-foreground">
              Recording for{" "}
              <span className="font-medium text-foreground">{data.term}</span>
              {data.academic_year ? ` · ${data.academic_year}` : ""}.
            </p>
          ) : null}

          <div className="space-y-4 pb-24">
            {students.map((s) => {
              const r = rows[s.student_id];
              if (!r) return null;
              return (
                <Card key={s.student_id}>
                  <CardHeader className="flex-row items-center justify-between space-y-0">
                    <CardTitle className="text-base">{s.full_name}</CardTitle>
                    <Badge variant="secondary">{s.admission_no}</Badge>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <RatingRow
                        title="Homework"
                        value={r.homework}
                        grades={grades}
                        onChange={(homework) => setRow(s.student_id, { homework })}
                      />
                      <RatingRow
                        title="Project Work"
                        value={r.project}
                        grades={grades}
                        onChange={(project) => setRow(s.student_id, { project })}
                      />
                    </div>
                    <div className="grid gap-4 sm:grid-cols-3">
                      <CheckboxPicker
                        label="Clubs"
                        options={options.clubs}
                        selected={r.clubs}
                        onChange={(clubs) => setRow(s.student_id, { clubs })}
                      />
                      <CheckboxPicker
                        label="Sports"
                        options={options.sports}
                        selected={r.sports}
                        onChange={(sports) => setRow(s.student_id, { sports })}
                      />
                      <CheckboxPicker
                        label="Other"
                        options={options.other}
                        selected={r.other}
                        onChange={(other) => setRow(s.student_id, { other })}
                      />
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      )}

      {/* ── Sticky footer ─────────────────────────────────────────────────── */}
      {students.length > 0 ? (
        <div className="fixed bottom-0 left-0 right-0 z-20 border-t bg-background/95 shadow-[0_-1px_12px_rgba(0,0,0,.07)] backdrop-blur supports-[backdrop-filter]:bg-background/85 lg:left-64">
          <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:px-6 lg:px-8">
            <div className="flex-1">
              <AutoSaveChip status={saveStatus} />
              {saveStatus === "idle" && (
                <span className="text-sm text-muted-foreground">
                  {isDirty ? "You have unsaved changes." : "All changes saved."}
                  {isFetching ? " · Refreshing…" : ""}
                </span>
              )}
            </div>
            <Button
              onClick={() => setConfirmOpen(true)}
              disabled={!isDirty || save.isPending}
              size="sm"
            >
              {save.isPending
                ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                : <Save className="mr-1.5 h-4 w-4" />}
              Save activities
            </Button>
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Save term activities?"
        description={`This records homework, project and activity participation for ${students.length} pupil${
          students.length === 1 ? "" : "s"
        }${data?.term ? ` for ${data.term}` : ""}. This action is logged.`}
        confirmLabel="Save activities"
        loading={save.isPending}
        onConfirm={onSave}
      />
    </>
  );
}
