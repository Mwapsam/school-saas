"use client";

import * as React from "react";
import { Search } from "lucide-react";
import { config, API } from "@/lib/config";
import type { AdmissionStatusResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  submitted: "default",
  under_review: "secondary",
  approved: "default",
  rejected: "destructive",
  admitted: "default",
  waitlisted: "outline",
  draft: "outline",
};

const STATUS_LABEL: Record<string, string> = {
  submitted: "Submitted",
  under_review: "Under Review",
  approved: "Approved",
  rejected: "Rejected",
  admitted: "Admitted",
  waitlisted: "Waitlisted",
  draft: "Draft",
};

async function checkStatus(appNumber: string): Promise<AdmissionStatusResponse> {
  const url = `${config.apiBaseUrl}${API.admissionStatus}?app_number=${encodeURIComponent(appNumber)}`;
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error ?? "Not found");
  return data as AdmissionStatusResponse;
}

export default function AdmissionStatusPage() {
  const [appNumber, setAppNumber] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState<AdmissionStatusResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  async function handleCheck() {
    if (!appNumber.trim()) return;
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const data = await checkStatus(appNumber.trim());
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Not found");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Track Your Application</h1>
        <p className="text-sm text-muted-foreground">
          Enter your application number to see the current status.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Application Number</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="appNum">Application Number</Label>
            <Input
              id="appNum"
              placeholder="e.g. APP-2025-001"
              value={appNumber}
              onChange={(e) => setAppNumber(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCheck()}
            />
          </div>
          <Button onClick={handleCheck} disabled={loading || !appNumber.trim()} className="w-full">
            {loading ? <Spinner /> : <Search className="mr-2 h-4 w-4" />}
            Check Status
          </Button>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-lg border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {result && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">{result.application_number}</CardTitle>
            <Badge variant={STATUS_VARIANT[result.status] ?? "outline"}>
              {STATUS_LABEL[result.status] ?? result.status}
            </Badge>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              <Row label="Student Name" value={result.student_name} />
              <Row label="Grade Applied" value={result.course_applied} />
              <Row label="Applied On" value={result.application_date} />
              {result.remarks && <Row label="Remarks" value={result.remarks} />}
            </dl>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-3">
      <dt className="w-32 shrink-0 text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value || "—"}</dd>
    </div>
  );
}
