"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import * as React from "react";

function SuccessContent() {
  const params = useSearchParams();
  const appNumber = params.get("app") ?? "";

  return (
    <div className="flex justify-center">
      <Card className="w-full max-w-md text-center">
        <CardContent className="space-y-4 py-10">
          <CheckCircle2 className="mx-auto h-14 w-14 text-primary" />
          <h1 className="text-2xl font-bold">Application Submitted!</h1>
          <p className="text-sm text-muted-foreground">
            Thank you. Your application has been received and is under review.
          </p>

          {appNumber && (
            <div className="rounded-lg border bg-muted px-6 py-4">
              <p className="text-xs text-muted-foreground">Application Number</p>
              <p className="mt-1 text-2xl font-bold tracking-wide">{appNumber}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Keep this number safe to track your application.
              </p>
            </div>
          )}

          <div className="flex flex-col gap-2 pt-2 sm:flex-row sm:justify-center">
            <Button asChild>
              <Link href="/admission/status">Track My Application</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/admission">Back to Portal</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function AdmissionSuccessPage() {
  return (
    <React.Suspense>
      <SuccessContent />
    </React.Suspense>
  );
}
