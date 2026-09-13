"use client";

import * as React from "react";
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
} from "lucide-react";
import { toast } from "sonner";

import type { SkillLevel } from "@/lib/types";
import { ApiError } from "@/lib/api";
import {
  useActivities,
  useSaveSkills,
  useSaveSkillsComments,
  useSkillsCatalog,
  useSkillsComments,
  useStudentSkills,
  useSubmitSkills,
  useTeacherClasses,
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
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// ── Types ─────────────────────────────────────────────────────────────────────

type SaveStatus = "idle" | "saving" | "saved" | "error";

const LEVELS: { value: SkillLevel; label: string; active: string }[] = [
  { value: "NOT_YET",      label: "Not Yet",      active: "bg-destructive text-destructive-foreground border-destructive" },
  { value: "BEGINNING",    label: "Beginning",    active: "bg-warning text-warning-foreground border-warning" },
  { value: "SATISFACTORY", label: "Satisfactory", active: "bg-primary text-primary-foreground border-primary" },
  { value: "GOOD",         label: "Good",         active: "bg-success text-success-foreground border-success" },
];

const FULL_YEAR = "__full_year__";

interface StepDef { label: string; description: string }

const STEPS: StepDef[] = [
  { label: "Rate Skills",          description: "Skill checklist per pupil" },
  { label: "Term Activities",      description: "Homework, clubs & sports" },
  { label: "Comments & Signature", description: "Report card feedback" },
];

// ── Sub-components ────────────────────────────────────────────────────────────

function LevelControl({
  value,
  onChange,
  label,
  disabled,
}: {
  value: SkillLevel | undefined;
  onChange: (v: SkillLevel) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex flex-wrap gap-1">
      {LEVELS.map((opt) => {
        const selected = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange(opt.value)}
            className={cn(
              "rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              disabled && "cursor-not-allowed opacity-60",
              selected
                ? opt.active
                : "border-input bg-background text-muted-foreground hover:bg-accent hover:text-accent-foreground",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

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

// ── Memoised skill item — only re-renders when its own level changes ──────────

interface SkillItemProps {
  item: { id: string; description: string };
  value: SkillLevel | undefined;
  onChange: (itemId: string, level: SkillLevel) => void;
  disabled?: boolean;
}

const SkillItem = React.memo(function SkillItem({ item, value, onChange, disabled }: SkillItemProps) {
  return (
    <li className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-sm">{item.description}</span>
      <LevelControl
        label={item.description}
        value={value}
        onChange={(v) => onChange(item.id, v)}
        disabled={disabled}
      />
    </li>
  );
});

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TeacherSkillsPage() {
  const { data: classes, isLoading: classesLoading } = useTeacherClasses();
  const classTeacherClasses = React.useMemo(
    () => (classes ?? []).filter(c => c.is_class_teacher && c.has_skills_assessment),
    [classes]
  );

  const [step, setStep]                             = React.useState<1 | 2 | 3>(1);
  const [batchId, setBatchId]                       = React.useState<string>();
  const [studentId, setStudentId]                   = React.useState<string>();
  const [term, setTerm]                             = React.useState<string>("");
  const [levels, setLevels]                         = React.useState<Record<string, SkillLevel>>({});
  const {
    rows: commentRows,
    setComment,
    seed: seedComments,
    buildEntries: buildCommentEntries,
  } = useTouchedComments();
  const [signatureImage, setSignatureImage]         = React.useState("");
  const [activitiesExamGroupId, setActivitiesExamGroupId] = React.useState("");
  const [confirmOpen, setConfirmOpen]               = React.useState(false);
  const [submitConfirmOpen, setSubmitConfirmOpen]   = React.useState(false);
  const [skillsSaveStatus, setSkillsSaveStatus]     = React.useState<SaveStatus>("idle");
  const [activitiesSaveStatus, setActivitiesSaveStatus] = React.useState<ActivitiesSaveStatus>("idle");
  const [commentSaveStatus, setCommentSaveStatus]   = React.useState<SaveStatus>("idle");

  const activitiesRef = React.useRef<ActivitiesStepHandle>(null);

  // Autosave guards
  const skillsSeedDone  = React.useRef(false);
  const commentSeedDone = React.useRef(false);
  const skillsTimer     = React.useRef<ReturnType<typeof setTimeout>>();
  const commentTimer    = React.useRef<ReturnType<typeof setTimeout>>();

  // Stable refs for timer callbacks
  const levelsRef      = React.useRef(levels);
  const signatureRef   = React.useRef(signatureImage);
  const termRef        = React.useRef(term);
  const studentRef     = React.useRef(studentId);
  const batchRef       = React.useRef(batchId);
  React.useEffect(() => { levelsRef.current      = levels;         }, [levels]);
  React.useEffect(() => { signatureRef.current   = signatureImage; }, [signatureImage]);
  React.useEffect(() => { termRef.current        = term;           }, [term]);
  React.useEffect(() => { studentRef.current     = studentId;      }, [studentId]);
  React.useEffect(() => { batchRef.current       = batchId;        }, [batchId]);

  // Default class once loaded (only class-teacher classes)
  React.useEffect(() => {
    if (!batchId && classTeacherClasses && classTeacherClasses.length > 0) setBatchId(classTeacherClasses[0].id);
  }, [classTeacherClasses, batchId]);

  const { data: catalog, isLoading: catalogLoading, isError, refetch } =
    useSkillsCatalog(batchId);

  // Default student/term once catalogue loads
  React.useEffect(() => {
    if (!catalog) return;
    if (catalog.students.length > 0) {
      setStudentId((prev) =>
        prev && catalog.students.some((s) => s.id === prev) ? prev : catalog.students[0].id
      );
    } else {
      setStudentId(undefined);
    }
  }, [catalog]);

  const { data: existing, isFetching, isError: studentSkillsError, refetch: refetchStudentSkills }   = useStudentSkills(studentId, term);
  const { data: commentsData }           = useSkillsComments(batchId, term);
  // Fetch exam groups for the batch so teacher can pick which term's activities to fill in
  const { data: activitiesMeta }         = useActivities(batchId, "");
  const saveSkills   = useSaveSkills(studentId ?? "");
  const saveComments = useSaveSkillsComments(batchId ?? "");
  const submitSkills = useSubmitSkills(batchId ?? "");

  const locked = catalog?.status === "submitted";

  // Term is locked to the class's skills-assessment exam group (the exam
  // group that actually has a Skill Levels exam, resolved server-side the
  // same way the admin marks-entry page does) — teachers don't choose it,
  // it's derived automatically.
  React.useEffect(() => {
    if (!catalog) return;
    const fallback = catalog.terms[0] ?? "";
    setTerm(catalog.active_term ?? fallback);
  }, [catalog]);

  // Reset guards on batch change (different class = different report set)
  React.useEffect(() => {
    skillsSeedDone.current  = false;
    setActivitiesExamGroupId("");
    setStep(1);
  }, [batchId]);

  // The comment seed guard is scoped to exactly what the seed is keyed on —
  // batch *and* term. Reopening it only on batchId meant a term change never
  // re-seeded: `term` starts "" and useSkillsComments fires straight away, so
  // the guard closed on the pre-catalog fetch and those rows then sat in state
  // while termRef moved on, letting the autosave write one term's comments
  // under another's.
  React.useEffect(() => {
    commentSeedDone.current = false;
  }, [batchId, term]);

  // Auto-select first available exam group for activities
  React.useEffect(() => {
    if (activitiesMeta?.exam_groups?.length && !activitiesExamGroupId) {
      setActivitiesExamGroupId(activitiesMeta.exam_groups[0].id);
    }
  }, [activitiesMeta, activitiesExamGroupId]);

  React.useEffect(() => {
    skillsSeedDone.current = false;
  }, [studentId, term]);

  // Seed skill levels (only once per student/term — see reset effects above,
  // which clear skillsSeedDone on batch/student/term change. Guarding here
  // stops a post-autosave refetch from re-seeding and clobbering levels the
  // teacher is still editing. `existing` is `undefined` while the query is
  // still loading/disabled, so we must wait for real data before marking
  // done — flipping the guard on the undefined placeholder would let a
  // slow fetch land after the guard was already closed, silently dropping
  // the teacher's previously-saved ratings.)
  React.useEffect(() => {
    if (skillsSeedDone.current || existing === undefined) return;
    setLevels(existing.levels ?? {});
    setSkillsSaveStatus("idle");
    skillsSeedDone.current = true;
  }, [existing]);

  // Seed comments (only once per batch selection — same clobbering issue as
  // the skill-levels seed above). seedComments additionally protects any
  // field the teacher started typing into before this response landed —
  // scoped to the batch+term the response belongs to, matching the
  // useSkillsComments query key, so edits never carry across classes or terms.
  React.useEffect(() => {
    if (!commentsData || commentSeedDone.current) return;
    const map: Record<string, string> = {};
    if (Array.isArray(commentsData.comments)) {
      for (const c of commentsData.comments) map[c.student_id] = c.comment;
    }
    seedComments(map, `${batchId ?? ""}:${term}`);
    setSignatureImage(commentsData.signature_image ?? "");
    setCommentSaveStatus("idle");
    setTimeout(() => { commentSeedDone.current = true; }, 100);
  }, [commentsData, seedComments, batchId, term]);

  // ── Derived ───────────────────────────────────────────────────────────────

  const categories = catalog?.categories ?? [];
  const students   = catalog?.students   ?? [];
  const totalItems = categories.reduce((n, c) => n + c.items.length, 0);
  const ratedCount = Object.keys(levels).length;

  const isDirtySkills = React.useMemo(() => {
    const orig = existing?.levels ?? {};
    const keys = new Set([...Object.keys(orig), ...Object.keys(levels)]);
    for (const k of keys) if (orig[k] !== levels[k]) return true;
    return false;
  }, [existing, levels]);

  const setLevel = (itemId: string, level: SkillLevel) =>
    setLevels((prev) => ({ ...prev, [itemId]: level }));

  // Stable callback for memoised SkillItem components
  const handleLevelChange = React.useCallback(
    (itemId: string, level: SkillLevel) =>
      setLevels((prev) => ({ ...prev, [itemId]: level })),
    [],
  );

  const selectedStudent = catalog?.students.find((s) => s.id === studentId);
  const hasContent = (categories.length > 0 || students.length > 0) && !catalogLoading && !isError;
  const className   = classes?.find((c) => c.id === batchId)?.name;

  // ── Payloads ──────────────────────────────────────────────────────────────

  const buildSkillsPayload = React.useCallback(
    () => ({ term: termRef.current || null, levels: levelsRef.current }),
    [],
  );

  const buildCommentsPayload = React.useCallback(
    () => ({
      term: termRef.current || null,
      comments: buildCommentEntries((catalog?.students ?? []).map((s) => s.id)),
      signature_image: signatureRef.current,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [catalog, buildCommentEntries],
  );

  // ── Auto-save: skills (2s debounce) — "saving" fires only when timer runs ──

  React.useEffect(() => {
    if (!skillsSeedDone.current || !studentRef.current || locked) return;
    if (skillsTimer.current) clearTimeout(skillsTimer.current);
    skillsTimer.current = setTimeout(async () => {
      setSkillsSaveStatus("saving");
      try {
        await saveSkills.mutateAsync(buildSkillsPayload());
        setSkillsSaveStatus("saved");
      } catch {
        setSkillsSaveStatus("error");
      }
    }, 2000);
    return () => { if (skillsTimer.current) clearTimeout(skillsTimer.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [levels]);

  // ── Auto-save: comments (1.5s debounce, step 3 only) — "saving" fires only when timer runs

  React.useEffect(() => {
    if (!commentSeedDone.current || step !== 3 || !batchRef.current || locked) return;
    if (commentTimer.current) clearTimeout(commentTimer.current);
    commentTimer.current = setTimeout(async () => {
      setCommentSaveStatus("saving");
      try {
        await saveComments.mutateAsync(buildCommentsPayload());
        setCommentSaveStatus("saved");
      } catch {
        setCommentSaveStatus("error");
      }
    }, 1500);
    return () => { if (commentTimer.current) clearTimeout(commentTimer.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [commentRows, signatureImage, step]);

  // ── Actions ───────────────────────────────────────────────────────────────

  const handleNext = async () => {
    if (step === 1) {
      if (isDirtySkills && studentRef.current) {
        try {
          await saveSkills.mutateAsync(buildSkillsPayload());
          setSkillsSaveStatus("saved");
        } catch (err) {
          console.error("Failed to save skills draft:", err);
          toast.error(
            err instanceof ApiError ? err.message : "Could not save draft. Please try again.",
          );
          setSkillsSaveStatus("error");
          return;
        }
      }
      setStep(2);
    } else if (step === 2) {
      await activitiesRef.current?.flushSave();
      setStep(3);
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleBack = () => {
    setStep((s) => (s > 1 ? (s - 1) as 1 | 2 | 3 : 1));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const onSaveSkills = async () => {
    try {
      const res = await saveSkills.mutateAsync(buildSkillsPayload());
      toast.success(`Saved ${res.saved} skills.`);
      setSkillsSaveStatus("saved");
      setConfirmOpen(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save skills.");
      setSkillsSaveStatus("error");
    }
  };

  const onSubmitResults = async () => {
    try {
      await submitSkills.mutateAsync({ term: term || null });
      toast.success(`Submitted skills results for ${className ?? "this class"}.`);
      setSubmitConfirmOpen(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not submit results.");
    }
  };

  return (
    <>
      <PageHeader
        title="Skills Assessment"
        description="Record the skills checklist for Beginners and Reception pupils."
      />

      {/* Step indicator */}
      {hasContent && (
        <div className="rounded-xl border bg-card px-5 py-4 shadow-sm">
          <StepIndicator current={step} />
        </div>
      )}

      {/* Submit / lock status — whole-class action, visible on every step */}
      {hasContent && (
        <div className="flex flex-col gap-3 rounded-xl border bg-card px-5 py-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
          {locked ? (
            <div className="flex items-center gap-2">
              <Badge variant="warning" className="gap-1.5">
                <Lock className="h-3 w-3" /> Submitted
              </Badge>
              <p className="text-sm text-muted-foreground">
                Skills results for{" "}
                <span className="font-medium text-foreground">{className ?? "this class"}</span>{" "}
                have been submitted — ratings and comments are locked.
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              When you&apos;re finished rating pupils and writing comments, submit results to lock them for the whole class.
            </p>
          )}
          <Button
            size="sm"
            variant={locked ? "outline" : "default"}
            onClick={() => setSubmitConfirmOpen(true)}
            disabled={locked || catalogLoading || students.length === 0}
            className="shrink-0 gap-1.5"
          >
            {locked ? <CheckCircle2 className="h-4 w-4" /> : <Lock className="h-4 w-4" />}
            {locked ? "Submitted" : "Submit results"}
          </Button>
        </div>
      )}

      {/* Selector card */}
      <Card>
        <CardContent className="grid gap-4 p-4 sm:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="class">Class</Label>
            {classesLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : classTeacherClasses.length > 0 ? (
              <Select
                value={batchId}
                onValueChange={(v) => { setBatchId(v); setStudentId(undefined); }}
              >
                <SelectTrigger id="class" aria-label="Select class">
                  <SelectValue placeholder="Select a class" />
                </SelectTrigger>
                <SelectContent>
                  {classTeacherClasses.map((c) => (
                    <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : null}
          </div>
          <div className="space-y-2">
            <Label htmlFor="student">
              Pupil{step === 2 && (
                <span className="ml-1 text-muted-foreground">(step 1)</span>
              )}
            </Label>
            <Select
              value={studentId}
              onValueChange={setStudentId}
              disabled={!catalog || catalog.students.length === 0 || step === 2}
            >
              <SelectTrigger id="student" aria-label="Select pupil">
                <SelectValue placeholder="Select a pupil" />
              </SelectTrigger>
              <SelectContent>
                {(catalog?.students ?? []).map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.full_name} ({s.admission_no})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="term">Term</Label>
            <Select value={term || FULL_YEAR} disabled>
              <SelectTrigger id="term" aria-label="Term (set automatically)">
                <SelectValue placeholder="Term" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={FULL_YEAR}>Full year</SelectItem>
                {(catalog?.terms ?? []).map((t) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-[11px] text-muted-foreground">
              Set automatically from the class&apos;s active exam.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Empty / error states */}
      {!classesLoading && classTeacherClasses.length === 0 ? (
        <EmptyState title="No classes to manage" description="Skills assessment is only available to class teachers. You are currently a subject teacher." />
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : catalogLoading ? (
        <Skeleton className="h-96" />
      ) : catalog && catalog.students.length === 0 ? (
        <EmptyState
          title="No pupils assigned to you"
          description="Ask an administrator to assign students to you as their class teacher in this class."
        />
      ) : categories.length === 0 ? (
        <EmptyState title="No skills configured" description="Skill categories and items are set up in the admin app." />
      ) : null}

      {/* ════════════════════════════════════════════════════════════════════
          STEP 1 — Skills rating grid
          ════════════════════════════════════════════════════════════════ */}
      {step === 1 && categories.length > 0 && studentId && studentSkillsError ? (
        <ErrorState
          description="This pupil is no longer assigned to you. Refresh the class list and try again."
          onRetry={() => refetchStudentSkills()}
        />
      ) : step === 1 && categories.length > 0 && studentId && (
        <div className="space-y-6 pb-28">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {selectedStudent ? (
                <>
                  Assessing{" "}
                  <span className="font-medium text-foreground">{selectedStudent.full_name}</span>
                  {catalog?.academic_year ? ` · ${catalog.academic_year}` : ""}
                </>
              ) : null}
            </p>
            <Badge variant="secondary">{ratedCount} / {totalItems} rated</Badge>
          </div>

          {categories.map((cat) => (
            <Card key={cat.code}>
              <CardHeader>
                <CardTitle className="text-base uppercase tracking-wide">{cat.name}</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="divide-y">
                  {cat.items.map((item) => (
                    <SkillItem
                      key={item.id}
                      item={item}
                      value={levels[item.id]}
                      onChange={handleLevelChange}
                      disabled={locked}
                    />
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          STEP 2 — Term Activities
          ════════════════════════════════════════════════════════════════ */}
      {step === 2 && batchId && (
        <>
          {/* Exam group selector — skills don't have a fixed exam_group, so the teacher picks */}
          {(activitiesMeta?.exam_groups?.length ?? 0) > 1 && (
            <div className="flex items-center gap-3">
              <Label htmlFor="act-eg" className="shrink-0 text-sm">Term for activities</Label>
              <Select value={activitiesExamGroupId} onValueChange={setActivitiesExamGroupId}>
                <SelectTrigger id="act-eg" className="max-w-xs">
                  <SelectValue placeholder="Select term" />
                </SelectTrigger>
                <SelectContent>
                  {(activitiesMeta?.exam_groups ?? []).map((g) => (
                    <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <ActivitiesStep
            ref={activitiesRef}
            batchId={batchId}
            examGroupId={activitiesExamGroupId}
            onSaveStatusChange={setActivitiesSaveStatus}
          />
        </>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          STEP 3 — Comments & Signature (whole class)
          ════════════════════════════════════════════════════════════════ */}
      {step === 3 && (
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
                  Appears on every skills report card for{" "}
                  <span className="font-medium text-foreground">
                    {className ?? "this class"}
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
                  {!signatureImage && !locked && (
                    <p className="text-[11px] text-muted-foreground">
                      Use mouse, stylus, or touch — or upload an image file
                    </p>
                  )}
                </div>
                {signatureImage && (
                  <div className="flex flex-col gap-2">
                    <p className="text-xs font-medium text-muted-foreground">Preview on report card</p>
                    <div className="w-48 rounded-lg border bg-white p-3 shadow-sm">
                      <img
                        src={signatureImage}
                        alt="Signature preview"
                        className="h-12 w-full object-contain"
                      />
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

          {/* Comments card */}
          <Card className="overflow-hidden pb-28">
            <div className="flex items-center justify-between border-b bg-muted/30 px-5 py-4">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <MessageSquare className="h-4 w-4 text-primary" aria-hidden />
                </div>
                <div>
                  <h2 className="text-sm font-semibold leading-tight">Pupil Comments</h2>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {students.length} pupil{students.length !== 1 ? "s" : ""}
                    {" · "}Optional · max 500 characters each
                  </p>
                </div>
              </div>
              <AutoSaveChip status={commentSaveStatus} />
            </div>
            <div className="divide-y">
              {students.map((s, index) => {
                const comment   = commentRows[s.id] ?? "";
                const charCount = comment.length;
                const nearLimit = charCount > 450;
                return (
                  <div
                    key={s.id}
                    className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-start sm:gap-4 sm:px-5"
                  >
                    <div className="flex min-w-0 items-center gap-3 sm:w-56 sm:flex-shrink-0">
                      <div
                        className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary"
                        aria-hidden
                      >
                        {index + 1}
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium leading-snug">{s.full_name}</p>
                        <p className="text-xs text-muted-foreground">{s.admission_no}</p>
                      </div>
                    </div>
                    <div className="relative flex-1">
                      <Textarea
                        value={comment}
                        onChange={(e) => setComment(s.id, e.target.value)}
                        disabled={locked}
                        maxLength={500}
                        rows={2}
                        placeholder={`Write a comment for ${s.full_name.split(" ")[0]}…`}
                        className={cn(
                          "resize-none pb-6 text-sm transition-colors",
                          nearLimit && "border-orange-300 focus-visible:ring-orange-300",
                        )}
                        aria-label={`Comment for ${s.full_name}`}
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
              })}
            </div>
          </Card>
        </>
      )}

      {/* ════════════════════════════════════════════════════════════════════
          Sticky footer
          ════════════════════════════════════════════════════════════════ */}
      {hasContent && studentId && (
        <div className="fixed bottom-0 left-0 right-0 z-20 border-t bg-background/95 shadow-[0_-1px_12px_rgba(0,0,0,.07)] backdrop-blur supports-[backdrop-filter]:bg-background/85 lg:left-64">
          <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:px-6 lg:px-8">
            {/* Left */}
            <div className="flex min-w-0 flex-1 items-center gap-3">
              {step > 1 ? (
                <Button variant="ghost" size="sm" onClick={handleBack} className="shrink-0 gap-1.5">
                  <ArrowLeft className="h-4 w-4" />
                  <span className="hidden sm:inline">
                    {step === 2 ? "Back to Skills" : "Back to Activities"}
                  </span>
                  <span className="sm:hidden">Back</span>
                </Button>
              ) : (
                <>
                  <AutoSaveChip status={skillsSaveStatus} />
                  {skillsSaveStatus === "idle" && (
                    <p className="truncate text-sm text-muted-foreground">
                      {isDirtySkills ? "You have unsaved changes." : "All changes saved."}
                      {isFetching ? " · Refreshing…" : ""}
                    </p>
                  )}
                </>
              )}
            </div>

            {/* Center */}
            <AutoSaveChip
              status={step === 1 ? skillsSaveStatus : step === 2 ? activitiesSaveStatus : commentSaveStatus}
            />

            {/* Right */}
            <div className="flex shrink-0 items-center gap-2">
              {step === 1 && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setConfirmOpen(true)}
                    disabled={!isDirtySkills || ratedCount === 0 || saveSkills.isPending || locked}
                    className="hidden sm:flex"
                  >
                    {saveSkills.isPending
                      ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      : <Save className="mr-1.5 h-4 w-4" />}
                    Save skills
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => void handleNext()}
                    disabled={saveSkills.isPending || catalogLoading}
                    className="gap-1.5"
                  >
                    {saveSkills.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                    <span className="hidden sm:inline">Next: Activities</span>
                    <span className="sm:hidden">Next</span>
                    <ArrowRight className="h-4 w-4" />
                  </Button>
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
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    try {
                      await saveComments.mutateAsync(buildCommentsPayload());
                      toast.success("Comments & signature saved.");
                      setCommentSaveStatus("saved");
                    } catch (err) {
                      toast.error(err instanceof ApiError ? err.message : "Could not save comments.");
                      setCommentSaveStatus("error");
                    }
                  }}
                  disabled={saveComments.isPending || locked}
                  className="gap-1.5"
                >
                  {saveComments.isPending
                    ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    : <Save className="mr-1.5 h-4 w-4" />}
                  Save comments
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Confirm save skills dialog */}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Save skills assessment?"
        description={`This will record ${ratedCount} skill rating${ratedCount === 1 ? "" : "s"}${
          selectedStudent ? ` for ${selectedStudent.full_name}` : ""
        }. This action is logged.`}
        confirmLabel="Save skills"
        loading={saveSkills.isPending}
        onConfirm={onSaveSkills}
      />

      {/* Confirm submit results dialog */}
      <ConfirmDialog
        open={submitConfirmOpen}
        onOpenChange={setSubmitConfirmOpen}
        title="Submit skills results?"
        description={`This locks skill ratings and comments for every pupil in ${
          className ?? "this class"
        }${term ? ` (${term})` : ""}. You won't be able to make further changes after submitting.`}
        confirmLabel="Submit results"
        loading={submitSkills.isPending}
        onConfirm={onSubmitResults}
      />
    </>
  );
}
