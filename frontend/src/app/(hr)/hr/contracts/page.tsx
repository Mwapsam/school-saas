"use client";

import * as React from "react";
import Link from "next/link";

import { toast } from "sonner";

import { useContracts, useRenewContract, useContractDecision, useHRCan } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { ErrorState, EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function HRContractsPage() {
  const [status, setStatus] = React.useState("all");
  const [page, setPage] = React.useState(1);
  const params: Record<string, string> = { page: String(page) };
  if (status !== "all") params.status = status;
  const { data, isLoading, isError, refetch } = useContracts(params);
  const canManage = useHRCan("hr.contract.manage");
  const rows = data?.results ?? [];

  return (
    <>
      <PageHeader title="Contracts" description="Every contract, with time to expiry." />
      <Select value={status} onValueChange={(v) => { setStatus(v); setPage(1); }}>
        <SelectTrigger className="w-52"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All statuses</SelectItem>
          <SelectItem value="active">Active</SelectItem>
          <SelectItem value="expiring_soon">Expiring soon</SelectItem>
          <SelectItem value="renewal_pending">Renewal pending</SelectItem>
          <SelectItem value="renewed">Renewed</SelectItem>
          <SelectItem value="not_renewed">Not renewed</SelectItem>
          <SelectItem value="expired">Expired</SelectItem>
        </SelectContent>
      </Select>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-96" />
      ) : rows.length === 0 ? (
        <EmptyState title="No contracts" description="No contracts match this filter." />
      ) : (
        <>
          <div className="rounded-lg border">
            <Table>
              <TableHeader><TableRow>
                <TableHead>Employee</TableHead><TableHead>Type</TableHead>
                <TableHead>Start</TableHead><TableHead>End</TableHead>
                <TableHead>Days left</TableHead><TableHead>Status</TableHead>
                {canManage ? <TableHead className="text-right">Actions</TableHead> : null}
              </TableRow></TableHeader>
              <TableBody>
                {rows.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>
                      <Link href={`/hr/employees/${c.employee_id}`} className="font-medium hover:underline">
                        {c.employee_name}
                      </Link>
                      <span className="ml-2 font-mono text-xs text-muted-foreground">{c.employee_number}</span>
                    </TableCell>
                    <TableCell>{c.contract_type_label}</TableCell>
                    <TableCell>{c.start_date}</TableCell>
                    <TableCell>{c.end_date ?? "Open-ended"}</TableCell>
                    <TableCell>{c.days_remaining ?? "—"}</TableCell>
                    <TableCell><Badge variant="outline">{c.renewal_status.replace("_", " ")}</Badge></TableCell>
                    {canManage ? (
                      <TableCell className="text-right">
                        <ContractActions
                          contractId={c.id}
                          contractType={c.contract_type}
                        />
                      </TableCell>
                    ) : null}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" disabled={!data?.previous} onClick={() => setPage((p) => Math.max(1, p - 1))}>Previous</Button>
            <Button variant="outline" size="sm" disabled={!data?.next} onClick={() => setPage((p) => p + 1)}>Next</Button>
          </div>
        </>
      )}
    </>
  );
}

function ContractActions({ contractId, contractType }: { contractId: string; contractType: string }) {
  const renew = useRenewContract();
  const decision = useContractDecision();
  const [open, setOpen] = React.useState(false);
  const [f, setF] = React.useState({ new_start_date: "", new_end_date: "" });

  const setDecision = (d: string) =>
    decision.mutate(
      { id: contractId, decision: d },
      {
        onSuccess: () => toast.success("Updated"),
        onError: (e: unknown) => toast.error((e as Error).message ?? "Failed"),
      },
    );

  return (
    <div className="flex justify-end gap-1">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm">Decision</Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => setDecision("renewal_pending")}>Renewal pending</DropdownMenuItem>
          <DropdownMenuItem onClick={() => setDecision("not_renewed")}>Do not renew</DropdownMenuItem>
          <DropdownMenuItem onClick={() => setDecision("active")}>Mark active</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <Button variant="outline" size="sm">Renew</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader><DialogTitle>Renew contract</DialogTitle></DialogHeader>
          <form
            className="grid gap-3 sm:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault();
              renew.mutate(
                {
                  id: contractId,
                  body: {
                    new_start_date: f.new_start_date,
                    new_end_date: f.new_end_date || null,
                    contract_type: contractType,
                  },
                },
                {
                  onSuccess: () => { setOpen(false); toast.success("Contract renewed"); },
                  onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
                },
              );
            }}
          >
            <div className="space-y-1">
              <Label>New start date</Label>
              <Input type="date" required value={f.new_start_date}
                onChange={(e) => setF((p) => ({ ...p, new_start_date: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <Label>New end date</Label>
              <Input type="date" value={f.new_end_date}
                onChange={(e) => setF((p) => ({ ...p, new_end_date: e.target.value }))} />
            </div>
            <DialogFooter className="sm:col-span-2">
              <Button type="submit" disabled={renew.isPending}>Renew</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
