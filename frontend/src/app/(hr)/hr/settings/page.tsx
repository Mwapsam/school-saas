"use client";

import * as React from "react";
import { toast } from "sonner";

import {
  useHRLookup, useSaveHRLookup, useDeleteHRLookup,
  useHRWorkingDays, useSaveHRWorkingDays,
  useHRDocumentTypes, useSaveHRDocumentTypes,
  useHRCan,
} from "@/hooks/use-hr";
import type { HRLookup } from "@/lib/types";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const LOOKUPS: { key: string; label: string; extra: { name: string; label: string; type?: string }[] }[] = [
  { key: "department", label: "Departments", extra: [{ name: "code", label: "Code" }] },
  { key: "category", label: "Employee categories", extra: [{ name: "prefix", label: "Prefix" }] },
  { key: "position", label: "Positions", extra: [] },
  { key: "grade", label: "Grades", extra: [{ name: "priority", label: "Priority", type: "number" }] },
  {
    key: "leave-type",
    label: "Leave types",
    extra: [
      { name: "code", label: "Code" },
      { name: "default_annual_days", label: "Annual days", type: "number" },
    ],
  },
];

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function HRSettingsPage() {
  const canManage = useHRCan("hr.settings.manage");

  return (
    <>
      <PageHeader
        title="HR Settings"
        description="Lookup tables, working-day rules, and the required-document policy."
      />
      {!canManage && (
        <p className="text-sm text-muted-foreground">
          You have read-only access to HR settings.
        </p>
      )}
      <Tabs defaultValue="department">
        <TabsList className="flex-wrap">
          {LOOKUPS.map((l) => (
            <TabsTrigger key={l.key} value={l.key}>{l.label}</TabsTrigger>
          ))}
          <TabsTrigger value="working-days">Working days</TabsTrigger>
          <TabsTrigger value="documents">Required documents</TabsTrigger>
        </TabsList>

        {LOOKUPS.map((l) => (
          <TabsContent key={l.key} value={l.key} className="pt-4">
            <LookupTable spec={l} canManage={canManage} />
          </TabsContent>
        ))}

        <TabsContent value="working-days" className="pt-4">
          <WorkingDaysPanel canManage={canManage} />
        </TabsContent>
        <TabsContent value="documents" className="pt-4">
          <DocumentTypesPanel canManage={canManage} />
        </TabsContent>
      </Tabs>
    </>
  );
}

function LookupTable({
  spec, canManage,
}: {
  spec: (typeof LOOKUPS)[number];
  canManage: boolean;
}) {
  const { data, isLoading, isError, refetch } = useHRLookup(spec.key);
  const save = useSaveHRLookup(spec.key);
  const del = useDeleteHRLookup(spec.key);
  const [draft, setDraft] = React.useState<Record<string, string>>({});

  const set = (k: string, v: string) => setDraft((p) => ({ ...p, [k]: v }));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const body: Record<string, unknown> = { name: draft.name, status: true };
    for (const f of spec.extra) {
      if (draft[f.name] !== undefined && draft[f.name] !== "") {
        body[f.name] = f.type === "number" ? Number(draft[f.name]) : draft[f.name];
      }
    }
    save.mutate(
      { body },
      {
        onSuccess: () => { setDraft({}); toast.success("Saved"); },
        onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
      },
    );
  };

  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (isLoading) return <Skeleton className="h-64" />;

  const rows = data ?? [];

  return (
    <div className="space-y-4">
      {canManage && (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label>Name</Label>
            <Input required value={draft.name ?? ""} onChange={(e) => set("name", e.target.value)} />
          </div>
          {spec.extra.map((f) => (
            <div className="space-y-1" key={f.name}>
              <Label>{f.label}</Label>
              <Input
                type={f.type ?? "text"}
                value={draft[f.name] ?? ""}
                onChange={(e) => set(f.name, e.target.value)}
              />
            </div>
          ))}
          <Button type="submit" disabled={save.isPending}>Add</Button>
        </form>
      )}

      {rows.length === 0 ? (
        <EmptyState title="Nothing configured yet" description="Add the first entry above." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                {spec.extra.map((f) => <TableHead key={f.name}>{f.label}</TableHead>)}
                <TableHead>Status</TableHead>
                {canManage && <TableHead className="w-24" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r: HRLookup) => (
                <TableRow key={r.id}>
                  <TableCell className="font-medium">{r.name}</TableCell>
                  {spec.extra.map((f) => (
                    <TableCell key={f.name}>
                      {(r as unknown as Record<string, unknown>)[f.name] as React.ReactNode ?? "—"}
                    </TableCell>
                  ))}
                  <TableCell>
                    <Badge variant={r.status === false ? "outline" : "default"}>
                      {r.status === false ? "Inactive" : "Active"}
                    </Badge>
                  </TableCell>
                  {canManage && (
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost" size="sm"
                          onClick={() => save.mutate({ id: r.id, body: { status: !(r.status !== false) } })}
                        >
                          {r.status === false ? "Enable" : "Disable"}
                        </Button>
                        <Button
                          variant="ghost" size="sm"
                          onClick={() => {
                            if (confirm(`Delete "${r.name}"?`)) {
                              del.mutate(r.id, {
                                onError: (err: unknown) =>
                                  toast.error((err as Error).message ?? "In use — cannot delete"),
                              });
                            }
                          }}
                        >
                          Delete
                        </Button>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function WorkingDaysPanel({ canManage }: { canManage: boolean }) {
  const { data, isLoading, isError, refetch } = useHRWorkingDays();
  const save = useSaveHRWorkingDays();
  const [days, setDays] = React.useState<number[] | null>(null);
  const [hours, setHours] = React.useState("");

  React.useEffect(() => {
    if (data) {
      setDays(data.working_days);
      setHours(String(data.default_daily_hours ?? ""));
    }
  }, [data]);

  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (isLoading || days === null) return <Skeleton className="h-40" />;

  const toggle = (i: number) =>
    setDays((d) => (d!.includes(i) ? d!.filter((x) => x !== i) : [...d!, i].sort()));

  return (
    <div className="max-w-md space-y-4">
      <div className="flex flex-wrap gap-2">
        {WEEKDAYS.map((label, i) => (
          <Button
            key={label}
            type="button"
            variant={days.includes(i) ? "default" : "outline"}
            size="sm"
            disabled={!canManage}
            onClick={() => toggle(i)}
          >
            {label}
          </Button>
        ))}
      </div>
      <div className="space-y-1">
        <Label>Default daily hours</Label>
        <Input
          type="number" value={hours} disabled={!canManage}
          onChange={(e) => setHours(e.target.value)}
        />
      </div>
      {canManage && (
        <Button
          disabled={save.isPending}
          onClick={() =>
            save.mutate(
              { working_days: days, default_daily_hours: Number(hours) },
              { onSuccess: () => toast.success("Saved") },
            )
          }
        >
          Save working days
        </Button>
      )}
    </div>
  );
}

function DocumentTypesPanel({ canManage }: { canManage: boolean }) {
  const { data, isLoading, isError, refetch } = useHRDocumentTypes();
  const save = useSaveHRDocumentTypes();
  const [list, setList] = React.useState<string[] | null>(null);
  const [entry, setEntry] = React.useState("");

  React.useEffect(() => {
    if (data) setList(data.required_document_types);
  }, [data]);

  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (isLoading || list === null) return <Skeleton className="h-40" />;

  const persist = (next: string[]) => {
    setList(next);
    save.mutate(next, { onError: () => toast.error("Failed to save") });
  };

  return (
    <div className="max-w-md space-y-4">
      <p className="text-sm text-muted-foreground">
        Every active employee is expected to have a document of each type below.
        Missing ones show on the HR dashboard.
      </p>
      {canManage && (
        <div className="flex gap-2">
          <Input
            placeholder="e.g. Safeguarding policy"
            value={entry}
            onChange={(e) => setEntry(e.target.value)}
          />
          <Button
            type="button"
            onClick={() => {
              const v = entry.trim();
              if (v && !list.includes(v)) persist([...list, v]);
              setEntry("");
            }}
          >
            Add
          </Button>
        </div>
      )}
      <ul className="space-y-1">
        {list.map((t) => (
          <li key={t} className="flex items-center justify-between rounded border px-3 py-2 text-sm">
            <span>{t}</span>
            {canManage && (
              <Button
                variant="ghost" size="sm"
                onClick={() => persist(list.filter((x) => x !== t))}
              >
                Remove
              </Button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
