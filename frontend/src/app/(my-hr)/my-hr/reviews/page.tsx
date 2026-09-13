"use client";

import * as React from "react";
import { toast } from "sonner";

import { useMyReviews, useUpdateMyReview } from "@/hooks/use-hr";
import type { HRPerformanceReview } from "@/lib/types";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function MyReviewsPage() {
  const { data, isLoading } = useMyReviews();
  const [open, setOpen] = React.useState<HRPerformanceReview | null>(null);

  return (
    <>
      <PageHeader
        title="My Reviews"
        description="Your performance appraisals. Add your comments and acknowledge the outcome."
      />

      {isLoading ? (
        <Skeleton className="h-56" />
      ) : !data?.length ? (
        <EmptyState title="No reviews" description="No appraisals have been shared with you yet." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Period</TableHead><TableHead>Date</TableHead>
              <TableHead>Reviewer</TableHead><TableHead>Rating</TableHead>
              <TableHead>Status</TableHead><TableHead></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {data.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.review_period}</TableCell>
                  <TableCell>{r.review_date}</TableCell>
                  <TableCell>{r.reviewer_name ?? "—"}</TableCell>
                  <TableCell>{r.overall_rating != null ? `${r.overall_rating}/5` : "—"}</TableCell>
                  <TableCell><Badge variant="outline">{r.status_label}</Badge></TableCell>
                  <TableCell className="text-right">
                    <Button size="sm" variant="ghost" onClick={() => setOpen(r)}>View</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <ReviewSheet review={open} onClose={() => setOpen(null)} />
    </>
  );
}

function ReviewSheet({
  review, onClose,
}: {
  review: HRPerformanceReview | null;
  onClose: () => void;
}) {
  const update = useUpdateMyReview();
  const [comments, setComments] = React.useState("");

  React.useEffect(() => {
    setComments(review?.employee_comments ?? "");
  }, [review]);

  if (!review) return <Sheet open={false} onOpenChange={() => {}} />;

  const acknowledged = review.status === "employee_ack" || review.status === "completed";

  return (
    <Sheet open onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <div className="space-y-1">
          <SheetTitle>{review.review_period}</SheetTitle>
        </div>
        <div className="mt-4 space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-2 text-muted-foreground">
            <div><span className="text-foreground">Reviewer:</span> {review.reviewer_name ?? "—"}</div>
            <div><span className="text-foreground">Date:</span> {review.review_date}</div>
            <div><span className="text-foreground">Overall:</span> {review.overall_rating != null ? `${review.overall_rating}/5` : "—"}</div>
            <div><span className="text-foreground">Status:</span> {review.status_label}</div>
          </div>

          {review.criteria.length > 0 ? (
            <div className="rounded-md border">
              <Table>
                <TableHeader><TableRow>
                  <TableHead>Criterion</TableHead><TableHead>Rating</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {review.criteria.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell>{c.name}</TableCell>
                      <TableCell>{c.rating != null ? `${c.rating}/5` : "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : null}

          {review.strengths ? <Block label="Strengths" value={review.strengths} /> : null}
          {review.improvement_areas ? <Block label="Areas for improvement" value={review.improvement_areas} /> : null}
          {review.development_actions ? <Block label="Development actions" value={review.development_actions} /> : null}
          {review.reviewer_comments ? <Block label="Reviewer comments" value={review.reviewer_comments} /> : null}

          <div className="space-y-1">
            <span className="font-medium">Your comments</span>
            <Textarea
              value={comments}
              disabled={review.status === "completed"}
              onChange={(e) => setComments(e.target.value)}
            />
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              disabled={update.isPending || review.status === "completed"}
              onClick={() =>
                update.mutate(
                  { id: review.id, body: { employee_comments: comments } },
                  {
                    onSuccess: () => toast.success("Comments saved"),
                    onError: (e: unknown) => toast.error((e as Error).message),
                  },
                )
              }
            >
              Save comments
            </Button>
            <Button
              disabled={update.isPending || acknowledged}
              onClick={() =>
                update.mutate(
                  { id: review.id, body: { employee_comments: comments, acknowledge: true } },
                  {
                    onSuccess: () => { toast.success("Review acknowledged"); onClose(); },
                    onError: (e: unknown) => toast.error((e as Error).message),
                  },
                )
              }
            >
              {acknowledged ? "Acknowledged" : "Acknowledge"}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Block({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <span className="font-medium">{label}</span>
      <p className="whitespace-pre-wrap text-muted-foreground">{value}</p>
    </div>
  );
}
