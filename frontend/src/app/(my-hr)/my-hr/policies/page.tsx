"use client";

import { toast } from "sonner";

import { useMyPolicies, useAcknowledgePolicy } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function MyPoliciesPage() {
  const { data, isLoading } = useMyPolicies();
  const ack = useAcknowledgePolicy();

  return (
    <>
      <PageHeader
        title="My Policies"
        description="Policies you are required to read and acknowledge."
      />

      {isLoading || !data ? (
        <Skeleton className="h-56" />
      ) : (
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Awaiting acknowledgement</CardTitle></CardHeader>
            <CardContent>
              {data.outstanding.length === 0 ? (
                <EmptyState title="All caught up" description="You have acknowledged every current policy." />
              ) : (
                <div className="space-y-3">
                  {data.outstanding.map((p) => (
                    <div key={p.id} className="flex items-start justify-between gap-4 rounded-md border p-3">
                      <div className="space-y-1">
                        <div className="font-medium">
                          {p.file_url ? (
                            <a href={p.file_url} target="_blank" rel="noreferrer" className="hover:underline">
                              {p.title}
                            </a>
                          ) : p.title}
                          {p.version ? <span className="ml-2 text-xs text-muted-foreground">v{p.version}</span> : null}
                        </div>
                        <Badge variant="outline">{p.category_label}</Badge>
                        {p.description ? (
                          <p className="max-w-prose text-sm text-muted-foreground">{p.description}</p>
                        ) : null}
                      </div>
                      <Button
                        size="sm"
                        disabled={ack.isPending}
                        onClick={() =>
                          ack.mutate(p.id, {
                            onSuccess: () => toast.success("Acknowledged"),
                            onError: (e: unknown) => toast.error((e as Error).message),
                          })
                        }
                      >
                        I acknowledge
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {data.acknowledged.length > 0 ? (
            <Card>
              <CardHeader><CardTitle>Acknowledged</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader><TableRow>
                    <TableHead>Policy</TableHead><TableHead>Version</TableHead>
                    <TableHead>Acknowledged</TableHead>
                  </TableRow></TableHeader>
                  <TableBody>
                    {data.acknowledged.map((a) => (
                      <TableRow key={a.policy_id}>
                        <TableCell>{a.title}</TableCell>
                        <TableCell>{a.version || "—"}</TableCell>
                        <TableCell>{a.acknowledged_at.slice(0, 10)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ) : null}
        </div>
      )}
    </>
  );
}
