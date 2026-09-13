"use client";

import * as React from "react";
import { toast } from "sonner";

import { useMyHRProfile, useUpdateMyHRProfile, useMyContracts } from "@/hooks/use-hr";
import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";

const EDITABLE = [
  ["mobile_phone", "Mobile"],
  ["email", "Email"],
  ["home_address_line1", "Address line 1"],
  ["home_city", "City"],
  ["emergency_contact_name", "Emergency contact name"],
  ["emergency_contact_phone", "Emergency contact phone"],
  ["next_of_kin_name", "Next of kin name"],
  ["next_of_kin_phone", "Next of kin phone"],
] as const;

export default function MyHRProfilePage() {
  const { data, isLoading, isError, refetch } = useMyHRProfile();
  const { data: contracts } = useMyContracts();
  const update = useUpdateMyHRProfile();
  const [form, setForm] = React.useState<Record<string, string>>({});

  React.useEffect(() => {
    if (data) {
      const rec = data as unknown as Record<string, unknown>;
      setForm(Object.fromEntries(EDITABLE.map(([k]) => [k, (rec[k] as string) ?? ""])));
    }
  }, [data]);

  if (isError) {
    return (<><PageHeader title="My Profile" /><ErrorState onRetry={() => refetch()} /></>);
  }

  return (
    <>
      <PageHeader title="My Profile" description="Your HR record. Some fields you can update yourself." />
      {isLoading || !data ? (
        <Skeleton className="h-80" />
      ) : (
        <>
          <Card><CardContent className="grid gap-4 p-6 sm:grid-cols-2">
            <div><p className="text-xs text-muted-foreground">Name</p><p>{data.full_name}</p></div>
            <div><p className="text-xs text-muted-foreground">Employee number</p><p>{data.employee_number}</p></div>
            <div><p className="text-xs text-muted-foreground">Department</p><p>{data.department ?? "—"}</p></div>
            <div><p className="text-xs text-muted-foreground">Job title</p><p>{data.job_title ?? "—"}</p></div>
            <div><p className="text-xs text-muted-foreground">Date joined</p><p>{data.joining_date ?? "—"}</p></div>
            <div><p className="text-xs text-muted-foreground">Status</p><p>{data.employment_status.replace("_", " ")}</p></div>
          </CardContent></Card>

          <form
            className="grid gap-4 sm:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault();
              update.mutate(form, {
                onSuccess: () => toast.success("Saved"),
                onError: (err: unknown) => toast.error((err as Error).message ?? "Failed"),
              });
            }}
          >
            {EDITABLE.map(([key, label]) => (
              <div key={key} className="space-y-1">
                <Label htmlFor={key}>{label}</Label>
                <Input
                  id={key}
                  value={form[key] ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                />
              </div>
            ))}
            <div className="sm:col-span-2">
              <Button type="submit" disabled={update.isPending}>Save changes</Button>
            </div>
          </form>

          {contracts?.length ? (
            <div>
              <h2 className="mb-2 text-sm font-semibold">My contracts</h2>
              <ul className="space-y-1 text-sm text-muted-foreground">
                {contracts.map((c) => (
                  <li key={c.id}>
                    {c.contract_type_label}: {c.start_date} → {c.end_date ?? "open-ended"} ({c.renewal_status.replace("_", " ")})
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      )}
    </>
  );
}
