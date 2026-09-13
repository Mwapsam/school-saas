"use client";

import { Check, Clock, X, CircleSlash } from "lucide-react";

import type { AttendanceStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

type Concrete = Exclude<AttendanceStatus, "unmarked">;

const OPTIONS: {
  value: Concrete;
  label: string;
  icon: typeof Check;
  active: string;
}[] = [
  { value: "present", label: "Present", icon: Check, active: "bg-success text-success-foreground border-success" },
  { value: "late", label: "Late", icon: Clock, active: "bg-warning text-warning-foreground border-warning" },
  { value: "half_day", label: "Half", icon: CircleSlash, active: "bg-primary text-primary-foreground border-primary" },
  { value: "absent", label: "Absent", icon: X, active: "bg-destructive text-destructive-foreground border-destructive" },
];

export function AttendanceStatusControl({
  value,
  onChange,
  studentName,
}: {
  value: AttendanceStatus;
  onChange: (status: Concrete) => void;
  studentName: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={`Attendance status for ${studentName}`}
      className="inline-flex flex-wrap gap-1"
    >
      {OPTIONS.map((opt) => {
        const Icon = opt.icon;
        const selected = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(opt.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              selected
                ? opt.active
                : "border-input bg-background text-muted-foreground hover:bg-accent hover:text-accent-foreground",
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
