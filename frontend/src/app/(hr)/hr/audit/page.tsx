"use client";

import * as React from "react";

import { useAuditLog } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { ErrorState, EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const ACTION_PREFIXES = [
  ["all", "All activity"],
  ["employee", "Employee changes"],
  ["contract", "Contracts"],
  ["disciplinary", "Disciplinary"],
  ["grievance", "Grievances"],
  ["exit", "Exits"],
];

export default function AuditPage() {
  const [action, setAction] = React.useState("all");
  const [targetId, setTargetId] = React.useState("");
  const params: Record<string, string> = {};
  if (action !== "all") params.action = action;
  if (targetId.trim()) params.target_id = targetId.trim();
  const { data, isLoading, isError, refetch } = useAuditLog(params);
  const rows = data?.results ?? [];

  return (
    <>
      <PageHeader
        title="Audit Trail"
        description="Every HR record change, with actor and timestamp."
      />

      <div className="flex flex-wrap items-center gap-2">
        <Select value={action} onValueChange={setAction}>
          <SelectTrigger className="w-52"><SelectValue /></SelectTrigger>
          <SelectContent>
            {ACTION_PREFIXES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
        <Input
          placeholder="Filter by target ID"
          value={targetId}
          onChange={(e) => setTargetId(e.target.value)}
          className="w-72"
        />
      </div>

      {isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-80" />
      ) : rows.length === 0 ? (
        <EmptyState title="No entries" description="No audit entries match." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>When</TableHead><TableHead>Actor</TableHead>
              <TableHead>Action</TableHead><TableHead>Target</TableHead>
              <TableHead>Change</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="whitespace-nowrap text-muted-foreground">
                    {new Date(e.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell>{e.actor_label || "—"}</TableCell>
                  <TableCell><Badge variant="outline">{e.action}</Badge></TableCell>
                  <TableCell className="text-muted-foreground">
                    {e.target_type}
                    {e.field ? ` · ${e.field}` : ""}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {e.old_value || e.new_value
                      ? `${e.old_value || "∅"} → ${e.new_value || "∅"}`
                      : "—"}
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
