"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { usePerformanceReview, useUpdateReview, useCompleteReview, useHRCan } from "@/hooks/use-hr";
import type { HRPerformanceCriterion } from "@/lib/types";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";

const NARRATIVE: [keyof NarrativeState, string][] = [
  ["objectives", "Objectives"],
  ["strengths", "Strengths"],
  ["improvement_areas", "Areas for improvement"],
  ["development_actions", "Development actions"],
  ["reviewer_comments", "Reviewer comments"],
  ["employee_comments", "Employee comments"],
];
type NarrativeState = {
  objectives: string; strengths: string; improvement_areas: string;
  development_actions: string; reviewer_comments: string; employee_comments: string;
};

export default function ReviewDetailPage() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const { data, isLoading, isError, refetch } = usePerformanceReview(reviewId);
  const update = useUpdateReview(reviewId);
  const complete = useCompleteReview(reviewId);
  const canConduct = useHRCan("hr.performance.conduct");

  const [narr, setNarr] = React.useState<NarrativeState>({
    objectives: "", strengths: "", improvement_areas: "",
    development_actions: "", reviewer_comments: "", employee_comments: "",
  });
  const [rating, setRating] = React.useState("");
  const [crit, setCrit] = React.useState<HRPerformanceCriterion[]>([]);

  React.useEffect(() => {
    if (data) {
      setNarr({
        objectives: data.objectives, strengths: data.strengths,
        improvement_areas: data.improvement_areas, development_actions: data.development_actions,
        reviewer_comments: data.reviewer_comments, employee_comments: data.employee_comments,
      });
      setRating(data.overall_rating != null ? String(data.overall_rating) : "");
      setCrit(data.criteria);
    }
  }, [data]);

  if (isError) {
    return (<><PageHeader title="Review" /><ErrorState onRetry={() => refetch()} /></>);
  }

  const save = () => {
    update.mutate(
      {
        ...narr,
        overall_rating: rating ? Number(rating) : null,
        criteria: crit.map((c) => ({ id: c.id, rating: c.rating, comment: c.comment })),
      },
      {
        onSuccess: () => toast.success("Saved"),
        onError: (e: unknown) => toast.error((e as Error).message ?? "Failed"),
      },
    );
  };

  return (
    <>
      <PageHeader
        title={isLoading ? "Loading…" : `${data?.employee_name} · ${data?.review_period}`}
        description={data ? `${data.is_teacher_review ? "Teacher review" : "Review"} · ${data.review_date}` : undefined}
        actions={data ? (
          <div className="flex items-center gap-2">
            <Badge variant="outline">{data.status_label}</Badge>
            {canConduct && data.status !== "completed" ? (
              <>
                <Button variant="outline" onClick={save} disabled={update.isPending}>Save</Button>
                <Button
                  onClick={() => complete.mutate(undefined, { onSuccess: () => toast.success("Completed") })}
                  disabled={complete.isPending}
                >
                  Complete
                </Button>
              </>
            ) : null}
          </div>
        ) : undefined}
      />

      {isLoading || !data ? (
        <Skeleton className="h-96" />
      ) : (
        <div className="space-y-6">
          <Card><CardContent className="p-6">
            <div className="mb-4 flex items-center gap-3">
              <Label className="w-40">Overall rating (1–5)</Label>
              <Input
                type="number" min={1} max={5} className="w-24"
                value={rating} disabled={!canConduct || data.status === "completed"}
                onChange={(e) => setRating(e.target.value)}
              />
            </div>
            <div className="space-y-3">
              {crit.map((c, i) => (
                <div key={c.id} className="grid gap-2 sm:grid-cols-[1fr_6rem_2fr]">
                  <span className="self-center text-sm">{c.name}</span>
                  <Input
                    type="number" min={1} max={5} placeholder="1–5"
                    value={c.rating ?? ""}
                    disabled={!canConduct || data.status === "completed"}
                    onChange={(e) => {
                      const v = e.target.value ? Number(e.target.value) : null;
                      setCrit((prev) => prev.map((x, j) => (j === i ? { ...x, rating: v } : x)));
                    }}
                  />
                  <Input
                    placeholder="Comment"
                    value={c.comment}
                    disabled={!canConduct || data.status === "completed"}
                    onChange={(e) =>
                      setCrit((prev) => prev.map((x, j) => (j === i ? { ...x, comment: e.target.value } : x)))
                    }
                  />
                </div>
              ))}
            </div>
          </CardContent></Card>

          <div className="grid gap-4 sm:grid-cols-2">
            {NARRATIVE.map(([key, label]) => (
              <div key={key} className="space-y-1">
                <Label>{label}</Label>
                <Textarea
                  rows={3}
                  value={narr[key]}
                  disabled={!canConduct || data.status === "completed"}
                  onChange={(e) => setNarr((p) => ({ ...p, [key]: e.target.value }))}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
