"use client";

import * as React from "react";

import type { TeacherCommentEntry } from "@/lib/types";

export interface TouchedComments {
  /** Current comment text per student id. */
  rows: Record<string, string>;
  /** Record an edit — marks the field as touched since the last seed. */
  setComment: (studentId: string, value: string) => void;
  /**
   * Apply server values for the comment set identified by `contextKey`.
   *
   * Within one context, a field the teacher has already edited is preserved:
   * a response that lands after typing began must never discard those
   * keystrokes, and the field must stay touched so a blank still counts as a
   * deliberate clear.
   *
   * When `contextKey` changes, that preservation would be corruption rather
   * than protection — the edits belong to a different exam group / term whose
   * roster uses the very same student ids, so carrying them over writes one
   * exam group's comments (and its `cleared` flags) onto another's. So a new
   * context drops the touched set and takes the server values outright.
   * The key is required precisely so a caller cannot forget to pass it.
   */
  seed: (serverComments: Record<string, string>, contextKey: string) => void;
  /** Payload entries for a roster, with `cleared` set per the save contract. */
  buildEntries: (studentIds: string[]) => TeacherCommentEntry[];
}

/**
 * Owns the "edited since load" tracking every teacher-comment screen needs.
 *
 * The backend cannot tell a comment the teacher deliberately emptied apart
 * from one that never received its saved value — both arrive as `""`. So the
 * UI must say which it is, via `cleared`. See the authoritative contract in
 * `TeacherCommentService.save_comments` (core/services/teacher_comment_service.py);
 * the staff exam-group page implements the same rule in plain JS with
 * `data-touched` attributes.
 */
export function useTouchedComments(): TouchedComments {
  const [rows, setRows] = React.useState<Record<string, string>>({});
  const rowsRef = React.useRef(rows);
  const touched = React.useRef<Set<string>>(new Set());
  const contextRef = React.useRef<string>();

  React.useEffect(() => {
    rowsRef.current = rows;
  }, [rows]);

  const setComment = React.useCallback((studentId: string, value: string) => {
    touched.current.add(studentId);
    setRows((prev) => ({ ...prev, [studentId]: value }));
  }, []);

  const seed = React.useCallback(
    (serverComments: Record<string, string>, contextKey: string) => {
      const sameContext = contextRef.current === contextKey;
      contextRef.current = contextKey;
      if (!sameContext) touched.current = new Set();
      setRows((prev) => {
        const next = { ...serverComments };
        // Untouched fields take the server value and a fresh baseline; touched
        // ones keep the teacher's in-progress edit. After a context switch
        // nothing is touched, so the server values stand as-is.
        if (sameContext) {
          for (const id of touched.current) next[id] = prev[id] ?? "";
        }
        rowsRef.current = next;
        return next;
      });
    },
    [],
  );

  const buildEntries = React.useCallback(
    (studentIds: string[]): TeacherCommentEntry[] =>
      studentIds.map((studentId) => {
        const comment = rowsRef.current[studentId] ?? "";
        return {
          student_id: studentId,
          comment,
          cleared: touched.current.has(studentId) && comment === "",
        };
      }),
    [],
  );

  return { rows, setComment, seed, buildEntries };
}
