"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";

import {
  usePayrollCategories, useSavePayrollCategory,
  usePayrollGroups, useSavePayrollGroup, usePayrollGroupComponents,
  useHRCan,
} from "@/hooks/use-hr";
import type { PayrollCategory, PayrollGroup } from "@/lib/types";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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

export default function PayrollSettingsPage() {
  const canManage = useHRCan("hr.payroll.manage");
  return (
    <>
      <PageHeader
        title="Payroll settings"
        description="Pay components and payroll groups used when generating payslips."
        actions={<Button variant="ghost" asChild><Link href="/hr/payroll">Back to payroll</Link></Button>}
      />
      <Tabs defaultValue="categories">
        <TabsList>
          <TabsTrigger value="categories">Pay components</TabsTrigger>
          <TabsTrigger value="groups">Payroll groups</TabsTrigger>
        </TabsList>
        <TabsContent value="categories" className="pt-4"><CategoriesPanel canManage={canManage} /></TabsContent>
        <TabsContent value="groups" className="pt-4"><GroupsPanel canManage={canManage} /></TabsContent>
      </Tabs>
    </>
  );
}

function CategoriesPanel({ canManage }: { canManage: boolean }) {
  const { data, isLoading, isError, refetch } = usePayrollCategories();
  const save = useSavePayrollCategory();
  const [f, setF] = React.useState({
    name: "", category_type: "earning", calculation_type: "fixed",
    default_amount: "", default_percentage: "", is_basic_pay: false,
  });
  const set = (k: string, v: string | boolean) => setF((p) => ({ ...p, [k]: v }));

  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (isLoading) return <Skeleton className="h-64" />;
  const rows = data ?? [];

  return (
    <div className="space-y-4">
      {canManage && (
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate(
              {
                body: {
                  name: f.name,
                  category_type: f.category_type,
                  calculation_type: f.calculation_type,
                  default_amount: f.default_amount ? Number(f.default_amount) : null,
                  default_percentage: f.default_percentage ? Number(f.default_percentage) : null,
                  is_basic_pay: f.is_basic_pay,
                  status: true,
                },
              },
              {
                onSuccess: () => {
                  setF({ name: "", category_type: "earning", calculation_type: "fixed", default_amount: "", default_percentage: "", is_basic_pay: false });
                  toast.success("Saved");
                },
                onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
              },
            );
          }}
        >
          <div className="space-y-1"><Label>Name</Label>
            <Input required value={f.name} onChange={(e) => set("name", e.target.value)} /></div>
          <div className="space-y-1"><Label>Type</Label>
            <Select value={f.category_type} onValueChange={(v) => set("category_type", v)}>
              <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="earning">Earning</SelectItem>
                <SelectItem value="deduction">Deduction</SelectItem>
              </SelectContent>
            </Select></div>
          <div className="space-y-1"><Label>Calculation</Label>
            <Select value={f.calculation_type} onValueChange={(v) => set("calculation_type", v)}>
              <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="fixed">Fixed amount</SelectItem>
                <SelectItem value="percentage">% of basic pay</SelectItem>
              </SelectContent>
            </Select></div>
          <div className="space-y-1"><Label>Amount</Label>
            <Input type="number" className="w-28" value={f.default_amount}
              onChange={(e) => set("default_amount", e.target.value)} /></div>
          <div className="space-y-1"><Label>%</Label>
            <Input type="number" className="w-20" value={f.default_percentage}
              onChange={(e) => set("default_percentage", e.target.value)} /></div>
          <label className="flex items-center gap-2 pb-1 text-sm">
            <Checkbox
              checked={f.is_basic_pay}
              onCheckedChange={(v) => set("is_basic_pay", v === true)}
            />
            Basic pay
          </label>
          <Button type="submit" disabled={save.isPending}>Add</Button>
        </form>
      )}

      <p className="text-xs text-muted-foreground">
        Exactly one earning component must be flagged <strong>Basic pay</strong> — it carries each
        employee&apos;s <em>basic pay</em> amount onto the payslip. Add that component (and the others)
        to a payroll group under the Payroll groups tab, then generate. Without it, gross pay is 0.
      </p>

      <div className="rounded-lg border">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Name</TableHead><TableHead>Type</TableHead>
            <TableHead>Calculation</TableHead><TableHead>Default</TableHead>
            <TableHead>Basic pay?</TableHead><TableHead>Status</TableHead>
            {canManage && <TableHead className="w-32" />}
          </TableRow></TableHeader>
          <TableBody>
            {rows.map((c: PayrollCategory) => (
              <TableRow key={c.id}>
                <TableCell className="font-medium">{c.name}</TableCell>
                <TableCell>{c.category_type}</TableCell>
                <TableCell>{c.calculation_type}</TableCell>
                <TableCell>
                  {c.calculation_type === "percentage"
                    ? `${c.default_percentage ?? 0}%`
                    : (c.default_amount ?? "—")}
                </TableCell>
                <TableCell>{c.is_basic_pay ? "Yes" : "—"}</TableCell>
                <TableCell>
                  <Badge variant={c.status === false ? "outline" : "default"}>
                    {c.status === false ? "Inactive" : "Active"}
                  </Badge>
                </TableCell>
                {canManage && (
                  <TableCell>
                    {c.category_type === "earning" && !c.is_basic_pay && (
                      <Button
                        variant="ghost" size="sm"
                        onClick={() =>
                          save.mutate(
                            { id: c.id, body: { is_basic_pay: true } },
                            {
                              onSuccess: () => toast.success(`"${c.name}" is now the basic-pay component`),
                              onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
                            },
                          )
                        }
                      >
                        Set basic pay
                      </Button>
                    )}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function GroupsPanel({ canManage }: { canManage: boolean }) {
  const { data, isLoading, isError, refetch } = usePayrollGroups();
  const saveGroup = useSavePayrollGroup();
  const categories = usePayrollCategories().data ?? [];
  const comps = usePayrollGroupComponents();
  const [name, setName] = React.useState("");

  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (isLoading) return <Skeleton className="h-64" />;
  const groups = data ?? [];

  return (
    <div className="space-y-6">
      {canManage && (
        <form
          className="flex items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            saveGroup.mutate(
              { body: { name, status: true } },
              { onSuccess: () => { setName(""); toast.success("Group added"); } },
            );
          }}
        >
          <div className="space-y-1"><Label>New group name</Label>
            <Input required value={name} onChange={(e) => setName(e.target.value)} /></div>
          <Button type="submit" disabled={saveGroup.isPending}>Add group</Button>
        </form>
      )}

      {groups.map((g: PayrollGroup) => (
        <div key={g.id} className="rounded-lg border p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-medium">{g.name}</h3>
            <Badge variant={g.status === false ? "outline" : "default"}>
              {g.status === false ? "Inactive" : "Active"}
            </Badge>
          </div>
          <Table>
            <TableHeader><TableRow>
              <TableHead>Component</TableHead><TableHead>Type</TableHead>
              <TableHead>Override</TableHead>
              {canManage && <TableHead className="w-16" />}
            </TableRow></TableHeader>
            <TableBody>
              {g.components.length === 0 ? (
                <TableRow><TableCell colSpan={4} className="text-sm text-muted-foreground">
                  No components yet.
                </TableCell></TableRow>
              ) : g.components.map((c) => (
                <TableRow key={c.id}>
                  <TableCell>{c.category_name}</TableCell>
                  <TableCell>{c.category_type}</TableCell>
                  <TableCell>{c.override_amount ?? c.override_percentage ?? "—"}</TableCell>
                  {canManage && (
                    <TableCell>
                      <Button variant="ghost" size="sm"
                        onClick={() => comps.remove.mutate({ groupId: g.id, componentId: c.id })}>
                        Remove
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {canManage && (
            <div className="mt-3 flex items-center gap-2">
              <Select
                onValueChange={(catId) =>
                  comps.add.mutate(
                    { groupId: g.id, body: { payroll_category_id: catId } },
                    { onError: (err: unknown) => toast.error((err as Error).message ?? "Failed") },
                  )
                }
              >
                <SelectTrigger className="w-64"><SelectValue placeholder="Add a component…" /></SelectTrigger>
                <SelectContent>
                  {categories.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
