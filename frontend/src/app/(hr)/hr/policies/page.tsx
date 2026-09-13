"use client";

import * as React from "react";
import { toast } from "sonner";

import {
  usePolicies, useCreatePolicy, useUpdatePolicy, useDeletePolicy, usePolicyAcks, useHRCan,
} from "@/hooks/use-hr";
import type { HRPolicy } from "@/lib/types";
import { PageHeader } from "@/components/page-header";
import { ErrorState, EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const CATEGORIES = [
  ["safeguarding", "Safeguarding / Child Protection"],
  ["code_of_conduct", "Code of Conduct"],
  ["hr", "HR / Employment"],
  ["health_safety", "Health & Safety"],
  ["it", "IT / Acceptable Use"],
  ["finance", "Finance / Procurement"],
  ["other", "Other"],
] as const;

export default function PoliciesPage() {
  const canManage = useHRCan("hr.settings.manage");
  const [showInactive, setShowInactive] = React.useState(false);
  const params: Record<string, string> = {};
  if (!showInactive) params.active = "true";
  const { data, isLoading, isError, refetch } = usePolicies(params);
  const rows = data?.results ?? [];
  const [acksFor, setAcksFor] = React.useState<HRPolicy | null>(null);

  return (
    <>
      <PageHeader
        title="Policies"
        description="Publish policies and track staff acknowledgements."
        actions={canManage ? <NewPolicyDialog /> : null}
      />

      <label className="flex items-center gap-2 text-sm text-muted-foreground">
        <input type="checkbox" checked={showInactive}
          onChange={(e) => setShowInactive(e.target.checked)} />
        Show inactive
      </label>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-72" />
      ) : rows.length === 0 ? (
        <EmptyState title="No policies" description="Publish a policy to get started." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Policy</TableHead><TableHead>Category</TableHead>
              <TableHead>Version</TableHead><TableHead>Acknowledged</TableHead>
              <TableHead>Status</TableHead><TableHead></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium">
                    {p.file_url ? (
                      <a href={p.file_url} target="_blank" rel="noreferrer" className="hover:underline">
                        {p.title}
                      </a>
                    ) : p.title}
                  </TableCell>
                  <TableCell>{p.category_label}</TableCell>
                  <TableCell>{p.version || "—"}</TableCell>
                  <TableCell>
                    {p.requires_acknowledgement && p.ack_summary
                      ? `${p.ack_summary.acknowledged}/${p.ack_summary.eligible} (${p.ack_summary.percent}%)`
                      : "Not required"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={p.is_active ? "outline" : "secondary"}>
                      {p.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="ghost" onClick={() => setAcksFor(p)}>
                        Who acknowledged
                      </Button>
                      {canManage ? <PolicyRowActions policy={p} /> : null}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <AcksSheet policy={acksFor} onClose={() => setAcksFor(null)} />
    </>
  );
}

function PolicyRowActions({ policy }: { policy: HRPolicy }) {
  const update = useUpdatePolicy();
  const del = useDeletePolicy();
  return (
    <>
      <Button
        size="sm"
        variant="ghost"
        disabled={update.isPending}
        onClick={() =>
          update.mutate(
            { id: policy.id, body: { is_active: !policy.is_active } },
            { onError: (e: unknown) => toast.error((e as Error).message) },
          )
        }
      >
        {policy.is_active ? "Deactivate" : "Activate"}
      </Button>
      <Button
        size="sm"
        variant="ghost"
        className="text-destructive"
        disabled={del.isPending}
        onClick={() => {
          if (confirm(`Delete "${policy.title}"? This removes all its acknowledgements.`)) {
            del.mutate(policy.id, {
              onSuccess: () => toast.success("Policy deleted"),
              onError: (e: unknown) => toast.error((e as Error).message),
            });
          }
        }}
      >
        Delete
      </Button>
    </>
  );
}

function NewPolicyDialog() {
  const create = useCreatePolicy();
  const [open, setOpen] = React.useState(false);
  const [f, setF] = React.useState({
    title: "", category: "hr", version: "", effective_date: "",
    description: "", requires_acknowledgement: true,
  });
  const [file, setFile] = React.useState<File | null>(null);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button>Publish policy</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Publish a policy</DialogTitle></DialogHeader>
        <form
          className="grid gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const fd = new FormData();
            fd.append("title", f.title);
            fd.append("category", f.category);
            if (f.version) fd.append("version", f.version);
            if (f.effective_date) fd.append("effective_date", f.effective_date);
            if (f.description) fd.append("description", f.description);
            fd.append("requires_acknowledgement", String(f.requires_acknowledgement));
            if (file) fd.append("file", file);
            create.mutate(fd, {
              onSuccess: () => { setOpen(false); toast.success("Policy published"); },
              onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
            });
          }}
        >
          <div className="space-y-1">
            <Label>Title</Label>
            <Input required value={f.title}
              onChange={(e) => setF((p) => ({ ...p, title: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Category</Label>
              <Select value={f.category} onValueChange={(v) => setF((p) => ({ ...p, category: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Version</Label>
              <Input value={f.version} placeholder="e.g. 2.1"
                onChange={(e) => setF((p) => ({ ...p, version: e.target.value }))} />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Effective date</Label>
            <Input type="date" value={f.effective_date}
              onChange={(e) => setF((p) => ({ ...p, effective_date: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Document (PDF)</Label>
            <Input type="file" accept="application/pdf,.doc,.docx"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </div>
          <div className="space-y-1">
            <Label>Description</Label>
            <Textarea value={f.description}
              onChange={(e) => setF((p) => ({ ...p, description: e.target.value }))} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={f.requires_acknowledgement}
              onChange={(e) => setF((p) => ({ ...p, requires_acknowledgement: e.target.checked }))} />
            Staff must acknowledge this policy
          </label>
          <DialogFooter>
            <Button type="submit" disabled={create.isPending || !f.title}>Publish</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function AcksSheet({ policy, onClose }: { policy: HRPolicy | null; onClose: () => void }) {
  const { data, isLoading } = usePolicyAcks(policy?.id);
  return (
    <Sheet open={!!policy} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {policy ? (
          <>
            <div className="space-y-1"><SheetTitle>{policy.title}</SheetTitle></div>
            {isLoading || !data ? (
              <Skeleton className="mt-4 h-64" />
            ) : (
              <Table className="mt-4">
                <TableHeader><TableRow>
                  <TableHead>Employee</TableHead><TableHead>Dept</TableHead>
                  <TableHead>Acknowledged</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {data.rows.map((r) => (
                    <TableRow key={r.employee_id}>
                      <TableCell>{r.name}</TableCell>
                      <TableCell className="text-muted-foreground">{r.department ?? "—"}</TableCell>
                      <TableCell>
                        {r.acknowledged_at
                          ? <span className="text-success">{r.acknowledged_at.slice(0, 10)}</span>
                          : <span className="text-muted-foreground">Pending</span>}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
