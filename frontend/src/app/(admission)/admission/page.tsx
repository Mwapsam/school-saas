"use client";

import Link from "next/link";
import { FileText, Search, Mail, MessageCircleQuestion, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAdmissionConfig } from "@/hooks/useAdmissionConfig";
import { Spinner } from "@/components/ui/spinner";

export default function AdmissionLandingPage() {
  const { data: admissionConfig, isLoading } = useAdmissionConfig();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner />
      </div>
    );
  }

  if (!admissionConfig?.enabled) {
    return (
      <div className="space-y-6">
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-center text-amber-900">
          <AlertCircle className="mx-auto mb-3 h-8 w-8" />
          <h1 className="mb-2 text-lg font-semibold">Admissions Currently Closed</h1>
          <p className="text-sm">
            Thank you for your interest. The admissions process is not currently open.
            Please contact the school for more information.
          </p>
          {admissionConfig?.contactEmail && (
            <a
              href={`mailto:${admissionConfig.contactEmail}`}
              className="mt-3 inline-block text-sm font-medium text-amber-700 underline hover:text-amber-800"
            >
              {admissionConfig.contactEmail}
            </a>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {/* Hero */}
      <div className="rounded-xl bg-primary px-8 py-12 text-center text-primary-foreground">
        <h1 className="mb-3 text-3xl font-bold">Welcome to Our Admissions Portal</h1>
        <p className="mx-auto mb-6 max-w-xl text-sm opacity-90">
          {admissionConfig.heading || "Apply for a place at our school. Complete our online form and track your application every step of the way."}
        </p>
        <Button asChild size="lg" variant="secondary">
          <Link href="/admission/apply">{admissionConfig.ctaText || "Start Application"}</Link>
        </Button>
      </div>

      {/* Cards */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader>
            <FileText className="mb-1 h-6 w-6 text-primary" />
            <CardTitle className="text-base">New Application</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>
              Complete the online admission form for your child. The process
              takes about 10 minutes.
            </p>
            <Button asChild className="w-full" size="sm">
              <Link href="/admission/apply">Apply Now</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <MessageCircleQuestion className="mb-1 h-6 w-6 text-primary" />
            <CardTitle className="text-base">Make an Enquiry</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>
              Not ready to apply yet? Send us an enquiry and our admissions
              team will reach out to you.
            </p>
            <Button asChild variant="outline" className="w-full" size="sm">
              <Link href="/admission/enquiry">Enquire Now</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <Search className="mb-1 h-6 w-6 text-primary" />
            <CardTitle className="text-base">Track Application</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>
              Already applied? Check the current status of your application
              using your application number.
            </p>
            <Button asChild variant="outline" className="w-full" size="sm">
              <Link href="/admission/status">Check Status</Link>
            </Button>
          </CardContent>
        </Card>

        {admissionConfig?.email && (
          <Card>
            <CardHeader>
              <Mail className="mb-1 h-6 w-6 text-primary" />
              <CardTitle className="text-base">Contact Admissions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>
                Questions about the admissions process? Our team is happy to help.
              </p>
              <Button asChild variant="outline" className="w-full" size="sm">
                <a href={`mailto:${admissionConfig.email}`}>Email Us</a>
              </Button>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Info */}
      {(admissionConfig?.contactEmail || admissionConfig?.contactPhone) && (
        <div className="rounded-lg border bg-card p-6 text-sm text-muted-foreground">
          <div className="grid gap-4 sm:grid-cols-2">
            {admissionConfig?.contactPhone && (
              <div>
                <p className="font-semibold text-foreground">Telephone</p>
                <p>{admissionConfig.contactPhone}</p>
              </div>
            )}
            {admissionConfig?.contactEmail && (
              <div>
                <p className="font-semibold text-foreground">Email</p>
                <a
                  href={`mailto:${admissionConfig.contactEmail}`}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  {admissionConfig.contactEmail}
                </a>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
