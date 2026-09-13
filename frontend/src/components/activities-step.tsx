"use client";

import * as React from "react";
import { CheckCircle2, Loader2 } from "lucide-react";

import type { ActivityRating, SaveActivitiesPayload } from "@/lib/types";
import { useActivities, useSaveActivities } from "@/hooks/use-portal";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

export type ActivitiesSaveStatus = "idle" | "saving" | "saved" | "error";

interface RowState {
  homework: ActivityRating;
  project:  ActivityRating;
  clubs:    string[];
  sports:   string[];
  other:    string[];
}

export interface ActivitiesStepHandle {
  /** Cancel pending debounce and save immediately. Resolves when done. */
  flushSave: () => Promise<void>;
}

interface ActivitiesStepProps {
  batchId: string;
  examGroupId: string;
  onSaveStatusChange?: (status: ActivitiesSaveStatus) => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const NONE = "__none__";

const emptyRating = (): ActivityRating => ({
  submission: "",
  presentation: "",
  effort: "",
});

const splitNames = (s: string): string[] =>
  (s || "").split(",").map((x) => x.trim()).filter(Boolean);

// ── Sub-components ────────────────────────────────────────────────────────────

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
              onValueChange={(v) => onChange({ ...value, [f]: v === NONE ? "" : v })}
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
      selected.includes(name) ? selected.filter((x) => x !== name) : [...selected, name],
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

function SaveChip({ status }: { status: ActivitiesSaveStatus }) {
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

// ── StudentActivityCard — memoised so only the changed student re-renders ────

interface StudentActivityCardProps {
  student: { student_id: string; full_name: string; admission_no: string };
  row: RowState;
  grades: string[];
  options: { clubs: string[]; sports: string[]; other: string[] };
  status: ActivitiesSaveStatus;
  onChange: (sid: string, patch: Partial<RowState>) => void;
}

const StudentActivityCard = React.memo(function StudentActivityCard({
  student: s,
  row: r,
  grades,
  options,
  status,
  onChange,
}: StudentActivityCardProps) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">{s.full_name}</CardTitle>
        <div className="flex items-center gap-2">
          <SaveChip status={status} />
          <Badge variant="secondary">{s.admission_no}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <RatingRow
            title="Homework"
            value={r.homework}
            grades={grades}
            onChange={(homework) => onChange(s.student_id, { homework })}
          />
          <RatingRow
            title="Project Work"
            value={r.project}
            grades={grades}
            onChange={(project) => onChange(s.student_id, { project })}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <CheckboxPicker
            label="Clubs"
            options={options.clubs}
            selected={r.clubs}
            onChange={(clubs) => onChange(s.student_id, { clubs })}
          />
          <CheckboxPicker
            label="Sports"
            options={options.sports}
            selected={r.sports}
            onChange={(sports) => onChange(s.student_id, { sports })}
          />
          <CheckboxPicker
            label="Other"
            options={options.other}
            selected={r.other}
            onChange={(other) => onChange(s.student_id, { other })}
          />
        </div>
      </CardContent>
    </Card>
  );
});

// ── Main component ────────────────────────────────────────────────────────────

export const ActivitiesStep = React.forwardRef<ActivitiesStepHandle, ActivitiesStepProps>(
  function ActivitiesStep({ batchId, examGroupId, onSaveStatusChange }, ref) {
    const { data, isLoading } = useActivities(batchId, examGroupId);
    const save = useSaveActivities(batchId);

    const [rows, setRows]         = React.useState<Record<string, RowState>>({});
    const [seed, setSeed]         = React.useState("");
    const [status, setStatus]     = React.useState<ActivitiesSaveStatus>("idle");

    const initialSeedDone  = React.useRef(false);
    const saveTimer        = React.useRef<ReturnType<typeof setTimeout>>();
    const rowsRef          = React.useRef(rows);
    const examGroupRef     = React.useRef(examGroupId);
    // Stable ref so doSave never needs onSaveStatusChange in its dep array
    const onSaveStatusRef  = React.useRef(onSaveStatusChange);

    React.useEffect(() => { rowsRef.current        = rows;                }, [rows]);
    React.useEffect(() => { examGroupRef.current   = examGroupId;         }, [examGroupId]);
    React.useEffect(() => { onSaveStatusRef.current = onSaveStatusChange; }, [onSaveStatusChange]);

    // Reset when exam group changes
    React.useEffect(() => {
      initialSeedDone.current = false;
    }, [examGroupId]);

    // Seed rows from API data
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
      setStatus("idle");
      setTimeout(() => { initialSeedDone.current = true; }, 100);
    }, [data]);

    const handleRowChange = React.useCallback(
      (sid: string, patch: Partial<RowState>) =>
        setRows((prev) => ({ ...prev, [sid]: { ...prev[sid], ...patch } })),
      [],
    );

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

    const doSave = React.useCallback(async () => {
      if (!examGroupRef.current) return;
      try {
        await save.mutateAsync(buildPayload());
        setStatus("saved");
        onSaveStatusRef.current?.("saved");
      } catch {
        setStatus("error");
        onSaveStatusRef.current?.("error");
      }
    }, [save, buildPayload]);

    // Auto-save (2s debounce) — "saving" status only fires when timer actually runs
    React.useEffect(() => {
      if (!initialSeedDone.current || !examGroupRef.current) return;
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => {
        setStatus("saving");
        onSaveStatusRef.current?.("saving");
        void doSave();
      }, 2000);
      return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [rows]);

    // Expose flushSave to parent
    React.useImperativeHandle(ref, () => ({
      flushSave: async () => {
        if (saveTimer.current) clearTimeout(saveTimer.current);
        await doSave();
      },
    }), [doSave]);

    const students = data?.students ?? [];
    const grades   = data?.grades   ?? [];
    const options  = data?.activity_options ?? { clubs: [], sports: [], other: [] };
    const isDirty  = React.useMemo(() => JSON.stringify(rows) !== seed, [rows, seed]);

    if (isLoading) {
      return (
        <div className="space-y-4">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      );
    }

    if (students.length === 0) {
      return (
        <EmptyState
          title="No pupils assigned to you"
          description="Ask an administrator to assign students to you as their class teacher in this class."
        />
      );
    }

    return (
      <div className="space-y-4">
        {data?.term && (
          <p className="text-sm text-muted-foreground">
            Recording for{" "}
            <span className="font-medium text-foreground">{data.term}</span>
            {data.academic_year ? ` · ${data.academic_year}` : ""}
            {isDirty && (
              <span className="ml-2 text-orange-500 text-xs font-medium">
                · Unsaved changes
              </span>
            )}
          </p>
        )}

        {students.map((s) => {
          const r = rows[s.student_id];
          if (!r) return null;
          return (
            <StudentActivityCard
              key={s.student_id}
              student={s}
              row={r}
              grades={grades}
              options={options}
              status={status}
              onChange={handleRowChange}
            />
          );
        })}
      </div>
    );
  },
);
