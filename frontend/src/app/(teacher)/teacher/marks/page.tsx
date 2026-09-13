"use client";

import * as React from "react";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  CheckCheck,
  CheckCircle2,
  Loader2,
  Lock,
  MessageSquare,
  PenLine,
  Save,
  Send,
} from "lucide-react";
import { toast } from "sonner";

import type {
  GradeOption,
  MarkSheetEntry,
  MarkableExam,
  SaveMarksPayload,
} from "@/lib/types";
import { ApiError } from "@/lib/api";
import {
  useExamComments,
  useMarkSheet,
  useSaveExamComments,
  useSaveMarks,
  useTeacherExams,
} from "@/hooks/use-portal";
import { useTouchedComments } from "@/hooks/use-touched-comments";
import { cn } from "@/lib/utils";
import {
  ActivitiesStep,
  type ActivitiesStepHandle,
  type ActivitiesSaveStatus,
} from "@/components/activities-step";
import { PageHeader } from "@/components/page-header";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { EmptyState, ErrorState } from "@/components/states";
import { SignaturePad } from "@/components/signature-pad";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { AssessmentSlot } from "@/lib/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// ── Types ─────────────────────────────────────────────────────────────────────

interface RowState {
  marks: string;
  grade_value_id: string | null;
  is_absent: boolean;
  remarks: string;
}

type SaveStatus = "idle" | "saving" | "saved" | "error";

const NO_GRADE = "__none__";

const SLOT_ORDER: AssessmentSlot[] = [
  "EXAM", "ATTAINMENT", "EFFORT", "CLASSWORK", "TEST",
];

const STEPS = [
  { label: "Enter Marks",           description: "Scores & absences" },
  { label: "Term Activities",       description: "Homework, clubs & sports" },
  { label: "Comments & Signature",  description: "Report card feedback" },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function examLabel(e: MarkableExam) {
  return `${e.batch.name} · ${e.subject}`;
}

function groupExamsBySlot(exams: MarkableExam[]) {
  const bySlot = new Map<AssessmentSlot, MarkableExam[]>();
  for (const e of exams) {
    const list = bySlot.get(e.assessment_slot) ?? [];
    list.push(e);
    bySlot.set(e.assessment_slot, list);
  }
  const ordered = [...bySlot.keys()].sort(
    (a, b) => SLOT_ORDER.indexOf(a) - SLOT_ORDER.indexOf(b),
  );
  return ordered.map((slot) => ({
    slot,
    label: bySlot.get(slot)![0].assessment_slot_display,
    exams: bySlot.get(slot)!,
  }));
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StepIndicator({ current }: { current: number }) {
  return (
    <div className="flex items-start" role="list" aria-label="Progress">
      {STEPS.map((step, i) => {
        const num    = i + 1;
        const done   = num < current;
        const active = num === current;
        return (
          <React.Fragment key={i}>
            <div
              className="flex min-w-0 flex-col items-center gap-2"
              role="listitem"
              aria-current={active ? "step" : undefined}
            >
              <div
                className={cn(
                  "flex h-9 w-9 select-none items-center justify-center rounded-full text-sm font-semibold transition-all duration-300",
                  done   && "bg-primary text-primary-foreground shadow-sm shadow-primary/30",
                  active && "bg-primary text-primary-foreground shadow-md shadow-primary/30 ring-4 ring-primary/15",
                  !done && !active && "border-2 border-muted-foreground/25 text-muted-foreground",
                )}
              >
                {done ? <CheckCheck className="h-4 w-4" /> : num}
              </div>
              <div className="flex flex-col items-center gap-0.5 text-center">
                <span className={cn(
                  "text-xs font-semibold leading-tight whitespace-nowrap transition-colors",
                  active && "text-primary",
                  done   && "text-foreground",
                  !done && !active && "text-muted-foreground",
                )}>
                  {step.label}
                </span>
                <span className="hidden text-[10px] text-muted-foreground sm:block">
                  {step.description}
                </span>
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <div className="mx-3 mt-[18px] h-0.5 flex-1 overflow-hidden rounded-full bg-muted">
                <div className={cn(
                  "h-full w-0 rounded-full bg-primary transition-all duration-500",
                  done && "w-full",
                )} />
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function AutoSaveChip({ status }: { status: SaveStatus | ActivitiesSaveStatus }) {
  if (status === "idle") return null;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-all duration-300",
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

// ── Memoised row components ───────────────────────────────────────────────────

function gradeForMarks(
  marks: number,
  max: number,
  grades: { name: string; min_percentage: number | null }[],
): string | null {
  const scale = grades
    .filter((g) => g.min_percentage !== null)
    .sort((a, b) => (b.min_percentage as number) - (a.min_percentage as number));
  if (!scale.length || !max) return null;
  const pct = (marks / max) * 100;
  const hit = scale.find((g) => pct >= (g.min_percentage as number));
  return (hit ?? scale[scale.length - 1]).name;
}

interface MarkTableRowProps {
  entry: MarkSheetEntry;
  index: number;
  row: RowState | undefined;
  gradeOnly: boolean;
  max: number;
  locked: boolean;
  availableGrades: GradeOption[];
  onChange: (studentId: string, patch: Partial<RowState>) => void;
}

const MarkTableRow = React.memo(function MarkTableRow({
  entry,
  index,
  row: r,
  gradeOnly,
  max,
  locked,
  availableGrades,
  onChange,
}: MarkTableRowProps) {
  const invalid =
    !!r && !r.is_absent && !gradeOnly &&
    r.marks.trim() !== "" &&
    (Number.isNaN(Number(r.marks)) || Number(r.marks) < 0 || Number(r.marks) > max);

  return (
    <TableRow>
      <TableCell className="text-muted-foreground">
        {entry.roll_number || index + 1}
      </TableCell>
      <TableCell>
        <div className="font-medium">{entry.full_name}</div>
        <div className="text-xs text-muted-foreground">{entry.admission_no}</div>
      </TableCell>
      <TableCell>
        {gradeOnly ? (
          <Select
            value={r?.grade_value_id ?? NO_GRADE}
            onValueChange={(v) =>
              onChange(entry.student_id, { grade_value_id: v === NO_GRADE ? null : v })
            }
            disabled={locked || r?.is_absent}
          >
            <SelectTrigger aria-label={`Grade for ${entry.full_name}`}>
              <SelectValue placeholder="Select grade" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_GRADE}>—</SelectItem>
              {availableGrades.map((g) => (
                <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <Input
            type="number"
            inputMode="decimal"
            min={0}
            max={max}
            step="0.5"
            value={r?.marks ?? ""}
            disabled={locked || r?.is_absent}
            aria-invalid={invalid}
            aria-label={`Marks for ${entry.full_name}`}
            className={cn(invalid && "border-destructive focus-visible:ring-destructive")}
            onChange={(e) => onChange(entry.student_id, { marks: e.target.value })}
          />
        )}
        {!gradeOnly && !invalid && r?.marks && !r?.is_absent && (() => {
          const g = gradeForMarks(Number(r.marks), max, availableGrades);
          return g ? <Badge variant="secondary" className="mt-1">{g}</Badge> : null;
        })()}
        {invalid && (
          <p className="mt-1 text-xs text-destructive" role="alert">
            Enter 0–{max}
          </p>
        )}
      </TableCell>
      <TableCell className="text-center">
        <input
          type="checkbox"
          className="h-4 w-4 cursor-pointer accent-primary"
          checked={r?.is_absent ?? false}
          disabled={locked}
          aria-label={`Mark ${entry.full_name} absent`}
          onChange={(e) => onChange(entry.student_id, { is_absent: e.target.checked })}
        />
      </TableCell>
    </TableRow>
  );
});

interface CommentRowProps {
  entry: MarkSheetEntry;
  index: number;
  comment: string;
  locked: boolean;
  onChange: (studentId: string, value: string) => void;
}

const CommentRow = React.memo(function CommentRow({
  entry,
  index,
  comment,
  locked,
  onChange,
}: CommentRowProps) {
  const charCount = comment.length;
  const nearLimit = charCount > 450;
  return (
    <div className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-start sm:gap-4 sm:px-5">
      <div className="flex min-w-0 items-center gap-3 sm:w-56 sm:flex-shrink-0">
        <div
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary"
          aria-hidden
        >
          {index + 1}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium leading-snug">{entry.full_name}</p>
          <p className="text-xs text-muted-foreground">{entry.admission_no}</p>
        </div>
      </div>
      <div className="relative flex-1">
        <Textarea
          value={comment}
          onChange={(e) => onChange(entry.student_id, e.target.value)}
          disabled={locked}
          maxLength={500}
          rows={2}
          placeholder={`Write a comment for ${entry.full_name.split(" ")[0]}…`}
          className={cn(
            "resize-none pb-6 text-sm transition-colors",
            nearLimit && "border-orange-300 focus-visible:ring-orange-300",
          )}
          aria-label={`Comment for ${entry.full_name}`}
        />
        <span
          className={cn(
            "pointer-events-none absolute bottom-2 right-2.5 text-[11px] tabular-nums transition-colors",
            nearLimit ? "font-medium text-orange-500" : "text-muted-foreground/60",
          )}
          aria-live="polite"
        >
          {charCount}/500
        </span>
      </div>
    </div>
  );
});

// ── Main page ─────────────────────────────────────────────────────────────────

function MarksView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const examParam = searchParams.get("exam") ?? undefined;

  const { data: exams, isLoading: examsLoading } = useTeacherExams();
  const selectedExamId =
    examParam ?? (exams && exams.length > 0 ? exams[0].id : undefined);

  const { data, isLoading, isError, refetch, isFetching } =
    useMarkSheet(selectedExamId);
  const save         = useSaveMarks(selectedExamId ?? "");
  const isClassTeacherRef = React.useRef(true); // Default to true; updated after first render
  const examGroupId = data?.exam?.exam_group_id;
  const { data: commentsData } = useExamComments(examGroupId);
  const saveComments = useSaveExamComments(examGroupId ?? "");

  // ── State ────────────────────────────────────────────────────────────────────
  const [step, setStep] = React.useState<1 | 2 | 3>(1);
  const [rows, setRows] = React.useState<Record<string, RowState>>({});
  const {
    rows: commentRows,
    setComment: handleCommentChange,
    seed: seedComments,
    buildEntries: buildCommentEntries,
  } = useTouchedComments();
  const [signatureImage, setSignatureImage] = React.useState("");
  const [marksSaveStatus, setMarksSaveStatus]       = React.useState<SaveStatus>("idle");
  const [activitiesSaveStatus, setActivitiesSaveStatus] = React.useState<ActivitiesSaveStatus>("idle");
  const [commentSaveStatus, setCommentSaveStatus]   = React.useState<SaveStatus>("idle");
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  const activitiesRef = React.useRef<ActivitiesStepHandle>(null);

  // Stable refs
  const rowsRef        = React.useRef(rows);
  const signatureRef   = React.useRef(signatureImage);
  const entriesRef     = React.useRef<MarkSheetEntry[]>([]);
  const gradeOnlyRef   = React.useRef(false);
  const maxRef         = React.useRef(0);
  const examGroupIdRef = React.useRef<string | undefined>(undefined);
  const initialSeedDoneMarks    = React.useRef(false);
  const initialSeedDoneComments = React.useRef(false);
  const marksSaveTimer   = React.useRef<ReturnType<typeof setTimeout>>();
  const commentSaveTimer = React.useRef<ReturnType<typeof setTimeout>>();

  React.useEffect(() => { rowsRef.current        = rows;         }, [rows]);
  React.useEffect(() => { signatureRef.current   = signatureImage; }, [signatureImage]);
  React.useEffect(() => { examGroupIdRef.current = examGroupId;   }, [examGroupId]);

  const meta     = data?.exam;
  const entries  = data?.entries ?? [];
  const gradeOnly = !!meta?.is_grade_only;
  const max      = meta?.maximum_marks ?? 0;
  const locked   = !!meta?.result_published;
  const isClassTeacher = !!meta?.is_class_teacher;

  const applicableSteps = React.useMemo(() => {
    if (!isClassTeacher) return [STEPS[0]]; // Subject teachers: marks only
    return STEPS; // Class teachers: all 3 steps
  }, [isClassTeacher]);

  React.useEffect(() => {
    entriesRef.current  = entries;
    gradeOnlyRef.current = gradeOnly;
    maxRef.current      = max;
  }, [entries, gradeOnly, max]);

  // Reset step and seed state when exam changes
  React.useEffect(() => {
    setStep(1);
    initialSeedDoneMarks.current    = false;
    initialSeedDoneComments.current = false;
  }, [selectedExamId]);

  // Seed marks (only once per exam selection — see reset effect above, which
  // clears initialSeedDoneMarks when selectedExamId changes. Guarding on the
  // ref here stops a post-autosave refetch from re-seeding and clobbering
  // marks the teacher is still editing.)
  React.useEffect(() => {
    if (!data || initialSeedDoneMarks.current) return;
    const next: Record<string, RowState> = {};
    for (const e of data.entries) {
      next[e.student_id] = {
        marks:          e.marks != null ? String(e.marks) : "",
        grade_value_id: e.grade_value_id,
        is_absent:      e.is_absent,
        remarks:        e.remarks ?? "",
      };
    }
    setRows(next);
    setMarksSaveStatus("idle");
    setTimeout(() => { initialSeedDoneMarks.current = true; }, 100);
  }, [data]);

  // Seed comments (only once per exam selection — see comment on the marks
  // seed effect above; same clobbering issue applies here). seedComments
  // additionally protects any field the teacher started typing into before
  // this response landed — scoped to the exam group the response belongs to,
  // so edits never carry across exam groups (their rosters share student ids).
  React.useEffect(() => {
    if (!commentsData || initialSeedDoneComments.current) return;
    const map: Record<string, string> = {};
    if (Array.isArray(commentsData.comments)) {
      for (const c of commentsData.comments) map[c.student_id] = c.comment;
    }
    seedComments(map, examGroupId ?? "");
    setSignatureImage(commentsData.signature_image ?? "");
    setCommentSaveStatus("idle");
    setTimeout(() => { initialSeedDoneComments.current = true; }, 100);
  }, [commentsData, seedComments, examGroupId]);

  // ── Derived ───────────────────────────────────────────────────────────────────

  const onExamChange = (id: string) => router.replace(`/teacher/marks?exam=${id}`);

  const setRow = (id: string, patch: Partial<RowState>) =>
    setRows((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));

  // Stable callbacks passed to memoised row components
  const handleRowChange = React.useCallback(
    (id: string, patch: Partial<RowState>) =>
      setRows((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } })),
    [],
  );

  const invalidId = (id: string): boolean => {
    const r = rows[id];
    if (!r || r.is_absent || gradeOnly) return false;
    if (r.marks.trim() === "") return false;
    const n = Number(r.marks);
    return Number.isNaN(n) || n < 0 || n > max;
  };

  const hasInvalid = entries.some((e) => invalidId(e.student_id));

  const isDirty = React.useMemo(() => {
    if (!data) return false;
    return data.entries.some((e) => {
      const r = rows[e.student_id];
      if (!r) return false;
      const origMarks = e.marks != null ? String(e.marks) : "";
      return (
        r.is_absent !== e.is_absent ||
        r.marks !== origMarks ||
        (r.grade_value_id ?? null) !== (e.grade_value_id ?? null) ||
        r.remarks !== (e.remarks ?? "")
      );
    });
  }, [data, rows]);

  const enteredCount = entries.filter((e) => {
    const r = rows[e.student_id];
    if (!r) return false;
    return r.is_absent || (gradeOnly ? !!r.grade_value_id : r.marks.trim() !== "");
  }).length;

  // ── Save helpers ──────────────────────────────────────────────────────────────

  const buildMarksPayload = React.useCallback(
    (submit: boolean): SaveMarksPayload => ({
      submit,
      entries: entriesRef.current.map((e) => {
        const r = rowsRef.current[e.student_id];
        return {
          student_id:      e.student_id,
          is_absent:       r?.is_absent ?? false,
          marks:           r?.is_absent || gradeOnlyRef.current || !r?.marks.trim() ? null : Number(r.marks),
          grade_value_id:  r?.is_absent || !gradeOnlyRef.current ? null : r?.grade_value_id ?? null,
          remarks:         r?.remarks.trim() || null,
        };
      }),
    }),
    [],
  );

  const buildCommentsPayload = React.useCallback(() => ({
    exam_group_id: examGroupIdRef.current ?? "",
    comments: buildCommentEntries(entriesRef.current.map((e) => e.student_id)),
    signature_image: signatureRef.current,
  }), [buildCommentEntries]);

  const doSaveMarksDraft = React.useCallback(async () => {
    try {
      await save.mutateAsync(buildMarksPayload(false));
      setMarksSaveStatus("saved");
    } catch {
      setMarksSaveStatus("error");
    }
  }, [save, buildMarksPayload]);

  const doSaveCommentsDraft = React.useCallback(async () => {
    try {
      await saveComments.mutateAsync(buildCommentsPayload());
      setCommentSaveStatus("saved");
    } catch {
      setCommentSaveStatus("error");
    }
  }, [saveComments, buildCommentsPayload]);

  // Auto-save: marks (2.5s debounce) — "saving" fires only when timer runs
  React.useEffect(() => {
    if (!initialSeedDoneMarks.current || locked || !selectedExamId) return;
    if (marksSaveTimer.current) clearTimeout(marksSaveTimer.current);
    marksSaveTimer.current = setTimeout(() => {
      setMarksSaveStatus("saving");
      void doSaveMarksDraft();
    }, 2500);
    return () => { if (marksSaveTimer.current) clearTimeout(marksSaveTimer.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows]);

  // Auto-save: comments (1.5s debounce, step 3 only) — "saving" fires only when timer runs
  React.useEffect(() => {
    if (!initialSeedDoneComments.current || step !== 3 || locked || !selectedExamId) return;
    if (commentSaveTimer.current) clearTimeout(commentSaveTimer.current);
    commentSaveTimer.current = setTimeout(() => {
      setCommentSaveStatus("saving");
      void doSaveCommentsDraft();
    }, 1500);
    return () => { if (commentSaveTimer.current) clearTimeout(commentSaveTimer.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [commentRows, signatureImage, step]);

  // ── Step navigation ───────────────────────────────────────────────────────────

  const handleNext = async () => {
    if (step === 1) {
      if (isDirty && !locked) {
        try {
          await save.mutateAsync(buildMarksPayload(false));
          setMarksSaveStatus("saved");
        } catch {
          toast.error("Could not save draft. Please try again.");
          return;
        }
      }
      // Subject teachers: submit directly from step 1; class teachers: go to step 2
      if (!isClassTeacher) {
        await handleSubmit();
      } else {
        setStep(2);
      }
    } else if (step === 2) {
      // Flush any pending activities autosave before advancing
      await activitiesRef.current?.flushSave();
      setStep(3);
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleBack = () => {
    setStep((s) => (s > 1 ? (s - 1) as 1 | 2 | 3 : 1));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleSubmit = async () => {
    try {
      // Class teachers save comments; subject teachers skip
      if (isClassTeacher) {
        await saveComments.mutateAsync(buildCommentsPayload());
      }
      const res = await save.mutateAsync(buildMarksPayload(true));
      toast.success(`Marks submitted for ${res.saved} students.`);
      setConfirmOpen(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not submit marks.");
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────────

  const showSteps = (entries.length > 0 || isLoading) && !isError;

  return (
    <div className="flex flex-col gap-5 pb-32">
      <PageHeader
        title="Marks Entry"
        description="Enter marks, record term activities, then add your signature for the report cards."
      />

      {showSteps && (
        <div className="rounded-xl border bg-card px-5 py-4 shadow-sm">
          <div className="flex items-start" role="list" aria-label="Progress">
            {applicableSteps.map((step_, i) => {
              const num    = i + 1;
              const done   = num < step;
              const active = num === step;
              return (
                <React.Fragment key={i}>
                  <div
                    className="flex min-w-0 flex-col items-center gap-2"
                    role="listitem"
                    aria-current={active ? "step" : undefined}
                  >
                    <div
                      className={cn(
                        "flex h-9 w-9 select-none items-center justify-center rounded-full text-sm font-semibold transition-all duration-300",
                        done   && "bg-primary text-primary-foreground shadow-sm shadow-primary/30",
                        active && "bg-primary text-primary-foreground shadow-md shadow-primary/30 ring-4 ring-primary/15",
                        !done && !active && "border-2 border-muted-foreground/25 text-muted-foreground",
                      )}
                    >
                      {done ? <CheckCheck className="h-4 w-4" /> : num}
                    </div>
                    <div className="flex flex-col items-center gap-0.5 text-center">
                      <span className={cn(
                        "text-xs font-semibold leading-tight whitespace-nowrap transition-colors",
                        active && "text-primary",
                        done   && "text-foreground",
                        !done && !active && "text-muted-foreground",
                      )}>
                        {step_.label}
                      </span>
                      <span className="hidden text-[10px] text-muted-foreground sm:block">
                        {step_.description}
                      </span>
                    </div>
                  </div>
                  {i < applicableSteps.length - 1 && (
                    <div className="mx-3 mt-[18px] h-0.5 flex-1 overflow-hidden rounded-full bg-muted">
                      <div className={cn(
                        "h-full w-0 rounded-full bg-primary transition-all duration-500",
                        done && "w-full",
                      )} />
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      )}

      {/* Exam selector */}
      <Card>
        <CardContent className="flex flex-col gap-2 p-4">
          <Label htmlFor="exam-select">Exam</Label>
          {examsLoading ? (
            <Skeleton className="h-10 w-full max-w-xl" />
          ) : exams && exams.length > 0 ? (
            <Select value={selectedExamId} onValueChange={onExamChange}>
              <SelectTrigger id="exam-select" className="max-w-xl" aria-label="Select exam">
                <SelectValue placeholder="Select an exam" />
              </SelectTrigger>
              <SelectContent>
                {groupExamsBySlot(exams).map((group) => (
                  <SelectGroup key={group.slot}>
                    <SelectLabel>{group.label}</SelectLabel>
                    {group.exams.map((e) => (
                      <SelectItem key={e.id} value={e.id}>{examLabel(e)}</SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </SelectContent>
            </Select>
          ) : null}
        </CardContent>
      </Card>

      {!examsLoading && (!exams || exams.length === 0) && (
        <EmptyState
          title="No exams to mark"
          description="You can enter marks once exams are created for your subjects or classes."
        />
      )}
      {isError && <ErrorState onRetry={() => refetch()} />}

      {/* ════════════════════════════════════════════════════════════════════
          STEP 1 — Marks table
          ════════════════════════════════════════════════════════════════ */}
      {step === 1 && (exams?.length ?? 0) > 0 && (
        <Card>
          <CardHeader className="flex-col items-start gap-2 space-y-0 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="text-base">
                {meta ? `${meta.subject} — ${meta.exam_name}` : "Mark sheet"}
              </CardTitle>
              {meta && (
                <p className="mt-0.5 text-sm text-muted-foreground">
                  {meta.batch.name} · {meta.exam_group}
                </p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {meta && <Badge variant="outline">{meta.assessment_slot_display}</Badge>}
              {meta && (gradeOnly
                ? <Badge variant="secondary">Grade only</Badge>
                : <Badge variant="secondary">Max {max}</Badge>
              )}
              <Badge variant="success">{enteredCount} entered</Badge>
              {meta?.status === "submitted"
                ? <Badge variant="default"><CheckCircle2 className="mr-1 h-3 w-3" /> Submitted</Badge>
                : meta && !locked
                  ? <Badge variant="secondary">Draft</Badge>
                  : null}
              {locked && <Badge variant="warning"><Lock className="mr-1 h-3 w-3" /> Published</Badge>}
            </div>
          </CardHeader>

          <CardContent>
            {locked && (
              <p className="mb-4 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm">
                Results have been published — marks are locked and read-only.
              </p>
            )}

            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : entries.length === 0 ? (
              <EmptyState
                title="No students in this class"
                description="Add students to the class in the admin app first."
              />
            ) : (
              <div className="overflow-x-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10">#</TableHead>
                      <TableHead>Student</TableHead>
                      <TableHead className="w-36 sm:w-44">
                        {gradeOnly ? "Grade" : `Marks (/${max})`}
                      </TableHead>
                      <TableHead className="w-20 text-center sm:w-24">Absent</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entries.map((entry: MarkSheetEntry, index) => (
                      <MarkTableRow
                        key={entry.student_id}
                        entry={entry}
                        index={index}
                        row={rows[entry.student_id]}
                        gradeOnly={gradeOnly}
                        max={max}
                        locked={locked}
                        availableGrades={meta?.available_grades ?? []}
                        onChange={handleRowChange}
                      />
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          STEP 2 — Term Activities (Class teachers only)
          ════════════════════════════════════════════════════════════════ */}
      {step === 2 && isClassTeacher && meta && (
        <ActivitiesStep
          ref={activitiesRef}
          batchId={meta.batch.id}
          examGroupId={meta.exam_group_id}
          onSaveStatusChange={setActivitiesSaveStatus}
        />
      )}

      {/* ════════════════════════════════════════════════════════════════════
          STEP 3 — Comments & Signature (Class teachers only)
          ════════════════════════════════════════════════════════════════ */}
      {step === 3 && isClassTeacher && entries.length > 0 && (
        <>
          {/* Signature card */}
          <Card className="overflow-hidden">
            <div className="flex items-start gap-3 border-b bg-muted/30 px-5 py-4">
              <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <PenLine className="h-4 w-4 text-primary" aria-hidden />
              </div>
              <div>
                <h2 className="text-sm font-semibold leading-tight">Teacher Signature</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Appears on every report card for{" "}
                  <span className="font-medium text-foreground">
                    {meta?.batch.name ?? "this class"}
                  </span>
                </p>
              </div>
            </div>
            <CardContent className="p-5">
              <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
                <div className="flex flex-col gap-1.5">
                  <SignaturePad
                    value={signatureImage}
                    onChange={setSignatureImage}
                    disabled={locked}
                    width={320}
                    height={110}
                  />
                  {!signatureImage && (
                    <p className="text-[11px] text-muted-foreground">
                      Use mouse, stylus, or touch — or upload an image file
                    </p>
                  )}
                </div>
                {signatureImage && (
                  <div className="flex flex-col gap-2">
                    <p className="text-xs font-medium text-muted-foreground">Preview on report card</p>
                    <div className="w-48 rounded-lg border bg-white p-3 shadow-sm">
                      <img src={signatureImage} alt="Signature preview" className="h-12 w-full object-contain" />
                      <div className="mt-2 border-t border-foreground/20 pt-1.5 text-center text-[10px] font-semibold tracking-wide text-foreground/60">
                        Class Teacher
                      </div>
                    </div>
                    <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="h-3 w-3" /> Signature captured
                    </span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Student comments card */}
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b bg-muted/30 px-5 py-4">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <MessageSquare className="h-4 w-4 text-primary" aria-hidden />
                </div>
                <div>
                  <h2 className="text-sm font-semibold leading-tight">Student Comments</h2>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {entries.length} student{entries.length !== 1 ? "s" : ""}
                    {" · "}Optional · max 500 characters each
                  </p>
                </div>
              </div>
              <AutoSaveChip status={commentSaveStatus} />
            </div>
            <div className="divide-y">
              {entries.map((entry: MarkSheetEntry, index) => (
                <CommentRow
                  key={entry.student_id}
                  entry={entry}
                  index={index}
                  comment={commentRows[entry.student_id] ?? ""}
                  locked={locked}
                  onChange={handleCommentChange}
                />
              ))}
            </div>
          </Card>
        </>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          Sticky action footer
          ════════════════════════════════════════════════════════════════ */}
      {(entries.length > 0 || isLoading) && (
        <div className="fixed bottom-0 left-0 right-0 z-20 border-t bg-background/95 shadow-[0_-1px_12px_rgba(0,0,0,.07)] backdrop-blur supports-[backdrop-filter]:bg-background/85 lg:left-64">
          <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:px-6 lg:px-8">
            {/* Left */}
            <div className="flex min-w-0 flex-1 items-center gap-3">
              {step > 1 ? (
                <Button variant="ghost" size="sm" onClick={handleBack} className="shrink-0 gap-1.5">
                  <ArrowLeft className="h-4 w-4" />
                  <span className="hidden sm:inline">
                    {step === 2 ? "Back to Marks" : "Back to Activities"}
                  </span>
                  <span className="sm:hidden">Back</span>
                </Button>
              ) : (
                <p className="truncate text-sm text-muted-foreground">
                  {hasInvalid
                    ? "Fix the highlighted marks before continuing."
                    : `${enteredCount} of ${entries.length} entered`}
                  {isFetching && " · Refreshing…"}
                </p>
              )}
            </div>

            {/* Center: autosave chip */}
            <AutoSaveChip
              status={step === 1 ? marksSaveStatus : step === 2 ? activitiesSaveStatus : commentSaveStatus}
            />

            {/* Right */}
            <div className="flex shrink-0 items-center gap-2">
              {step === 1 && (
                <>
                  {!locked && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void doSaveMarksDraft()}
                      disabled={!isDirty || hasInvalid || save.isPending}
                      className="hidden sm:flex"
                    >
                      {save.isPending
                        ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                        : <Save className="mr-1.5 h-4 w-4" />}
                      Save draft
                    </Button>
                  )}
                  {!isClassTeacher ? (
                    <Button
                      size="sm"
                      onClick={() => setConfirmOpen(true)}
                      disabled={hasInvalid || enteredCount === 0 || save.isPending || locked}
                      className="gap-1.5"
                    >
                      <Send className="h-4 w-4" />
                      Submit marks
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      onClick={() => void handleNext()}
                      disabled={hasInvalid || save.isPending || isLoading}
                      className="gap-1.5"
                    >
                      {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                      <span className="hidden sm:inline">Next: Activities</span>
                      <span className="sm:hidden">Next</span>
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  )}
                </>
              )}

              {step === 2 && (
                <Button
                  size="sm"
                  onClick={() => void handleNext()}
                  className="gap-1.5"
                >
                  <span className="hidden sm:inline">Next: Comments</span>
                  <span className="sm:hidden">Next</span>
                  <ArrowRight className="h-4 w-4" />
                </Button>
              )}

              {step === 3 && (
                <>
                  {!locked && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void doSaveCommentsDraft()}
                      disabled={saveComments.isPending}
                      className="hidden sm:flex"
                    >
                      {saveComments.isPending
                        ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                        : <Save className="mr-1.5 h-4 w-4" />}
                      Save draft
                    </Button>
                  )}
                  <Button
                    size="sm"
                    onClick={() => setConfirmOpen(true)}
                    disabled={
                      hasInvalid ||
                      enteredCount === 0 ||
                      save.isPending ||
                      saveComments.isPending ||
                      locked
                    }
                    className="gap-1.5"
                  >
                    <Send className="h-4 w-4" />
                    Submit marks
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Confirm submit dialog */}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Submit marks?"
        description={`This submits marks for ${enteredCount} student${
          enteredCount === 1 ? "" : "s"
        }${meta ? ` for ${meta.subject} — ${meta.exam_name}` : ""} for review. You can still edit them until an admin publishes the results.`}
        confirmLabel="Submit marks"
        loading={save.isPending || saveComments.isPending}
        onConfirm={() => void handleSubmit()}
      />
    </div>
  );
}

export default function TeacherMarksPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-4">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      }
    >
      <MarksView />
    </Suspense>
  );
}
