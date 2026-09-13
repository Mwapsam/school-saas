import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge conditional + Tailwind class names without specificity conflicts. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}%`;
}

export function formatMarks(
  marks: number | null | undefined,
  max: number | null | undefined,
): string {
  if (marks === null || marks === undefined) return "—";
  if (max === null || max === undefined) return String(marks);
  return `${marks} / ${max}`;
}
