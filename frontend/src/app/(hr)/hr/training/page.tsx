"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";

import {
  useTrainingList, useTrainingCompliance, useCreateTraining,
  useHREmployees, useHRCan,
} from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { ErrorState, EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const CATEGORIES = [
  ["child_safeguarding", "Child Safeguarding"], ["first_aid", "First Aid"],
  ["fire_safety", "Fire / Safety"], ["curriculum", "Curriculum Training"],
  ["classroom_management", "Classroom Management"], ["ict", "ICT"],
  ["leadership", "Leadership"], ["professional_development", "Professional Development"],
  ["other", "Other"],
] as const;

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  valid: "outline", expiring: "secondary", expired: "destructive",
  planned: "outline", in_progress: "secondary", completed: "default", cancelled: "outline",
};

export default function TrainingPage() {
  const [category, setCategory] = React.useState("all");
  const params: Record<string, string> = {};
  if (category !== "all") params.category = category;
  const { data, isLoading, isError, refetch } = useTrainingList(params);
  const { data: compliance } = useTrainingCompliance();
  const rows = data?.results ?? [];

  return (
    <>
      <PageHeader
        title="Training & Development"
        description="CPD records and mandatory-training compliance."
        actions={<NewTrainingDialog />}
      />

      {compliance && (compliance.mandatory_gaps.length || compliance.expiring.length) ? (
        <Card><CardContent className="p-4 text-sm">
          <p className="font-medium">Compliance</p>
          {compliance.mandatory_gaps.length ? (
            <p className="mt-1 text-muted-foreground">
              {compliance.mandatory_gaps.length} employee(s) missing mandatory training
              ({compliance.mandatory_gaps.slice(0, 3).map((g) => g.name).join(", ")}
              {compliance.mandatory_gaps.length > 3 ? "…" : ""})
            </p>
          ) : null}
          {compliance.expiring.length ? (
            <p className="mt-1 text-muted-foreground">
              {compliance.expiring.length} certificate(s) expiring within 60 days
            </p>
          ) : null}
        </CardContent></Card>
      ) : null}

      <Select value={category} onValueChange={setCategory}>
        <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All categories</SelectItem>
          {CATEGORIES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
        </SelectContent>
      </Select>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-80" />
      ) : rows.length === 0 ? (
        <EmptyState title="No training records" description="Add a record to start tracking CPD." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Employee</TableHead><TableHead>Training</TableHead>
              <TableHead>Category</TableHead><TableHead>Date</TableHead>
              <TableHead>Expiry</TableHead><TableHead>Status</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((t) => (
                <TableRow key={t.id}>
                  <TableCell>
                    <Link href={`/hr/employees/${t.employee_id}`} className="font-medium hover:underline">
                      {t.employee_name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {t.name}
                    {t.is_mandatory ? <Badge variant="outline" className="ml-2">Mandatory</Badge> : null}
                  </TableCell>
                  <TableCell>{t.category_label}</TableCell>
                  <TableCell>{t.training_date ?? "—"}</TableCell>
                  <TableCell>{t.expiry_date ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[t.compliance_status] ?? "outline"}>
                      {t.compliance_status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}

function NewTrainingDialog() {
  const canManage = useHRCan("hr.training.manage");
  const create = useCreateTraining();
  const { data: employees } = useHREmployees({ page: "1", page_size: "200" });
  const [open, setOpen] = React.useState(false);
  const [f, setF] = React.useState({
    employee_id: "", name: "", category: "professional_development", provider: "",
    training_date: "", expiry_date: "", cost: "", is_mandatory: false,
  });

  if (!canManage) return null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button>Add training</Button></DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>New training record</DialogTitle></DialogHeader>
        <form
          className="grid gap-3 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate(
              {
                ...f,
                cost: f.cost ? Number(f.cost) : null,
                training_date: f.training_date || null,
                expiry_date: f.expiry_date || null,
                status: "completed",
              },
              {
                onSuccess: () => { setOpen(false); toast.success("Training recorded"); },
                onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
              },
            );
          }}
        >
          <div className="space-y-1 sm:col-span-2">
            <Label>Employee</Label>
            <Select value={f.employee_id} onValueChange={(v) => setF((p) => ({ ...p, employee_id: v }))}>
              <SelectTrigger><SelectValue placeholder="Choose employee" /></SelectTrigger>
              <SelectContent>
                {(employees?.results ?? []).map((e) => (
                  <SelectItem key={e.id} value={e.id}>{e.full_name} ({e.employee_number})</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Training name</Label>
            <Input required value={f.name} onChange={(e) => setF((p) => ({ ...p, name: e.target.value }))} />
          </div>
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
            <Label>Provider</Label>
            <Input value={f.provider} onChange={(e) => setF((p) => ({ ...p, provider: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Cost</Label>
            <Input type="number" value={f.cost} onChange={(e) => setF((p) => ({ ...p, cost: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Training date</Label>
            <Input type="date" value={f.training_date} onChange={(e) => setF((p) => ({ ...p, training_date: e.target.value }))} />
          </div>
          <div className="space-y-1">
            <Label>Expiry / renewal</Label>
            <Input type="date" value={f.expiry_date} onChange={(e) => setF((p) => ({ ...p, expiry_date: e.target.value }))} />
          </div>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <Checkbox checked={f.is_mandatory} onCheckedChange={(v) => setF((p) => ({ ...p, is_mandatory: Boolean(v) }))} />
            Mandatory training
          </label>
          <DialogFooter className="sm:col-span-2">
            <Button type="submit" disabled={create.isPending || !f.employee_id}>Add</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
