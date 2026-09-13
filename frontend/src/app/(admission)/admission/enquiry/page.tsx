"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { config, API } from "@/lib/config";
import type { AdmissionCourse, EnquiryFormData } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Send } from "lucide-react";
import { toast } from "sonner";

const EMPTY: EnquiryFormData = {
  course: "",
  first_name: "",
  last_name: "",
  date_of_birth: "",
  email: "",
  phone: "",
  guardian_first_name: "",
  guardian_last_name: "",
  guardian_relation: "",
  guardian_phone: "",
  guardian_email: "",
  source_of_info: "",
  remarks: "",
};

async function fetchCourses(schoolId?: string): Promise<AdmissionCourse[]> {
  let url = API.admissionCourses;
  if (schoolId) {
    url += `?school_id=${encodeURIComponent(schoolId)}`;
  }
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to load courses (${res.status}): ${text}`);
  }
  return ((await res.json()) as { courses: AdmissionCourse[] }).courses;
}

async function submitEnquiry(form: EnquiryFormData, schoolId?: string) {
  let url = API.enquirySubmit;
  if (schoolId) {
    url += `?school_id=${encodeURIComponent(schoolId)}`;
  }
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(form),
  });
  const data = await res.json();
  if (!res.ok) throw new Error((data as { error?: string }).error ?? "Submission failed");
  return data as { enquiry_number: string };
}

export default function EnquiryPage() {
  const router = useRouter();
  const searchParams = React.useMemo(
    () => new URLSearchParams(typeof window !== "undefined" ? window.location.search : ""),
    [],
  );
  const schoolId = searchParams.get("school_id") || undefined;

  const [form, setForm] = React.useState<EnquiryFormData>(EMPTY);
  const [courses, setCourses] = React.useState<AdmissionCourse[]>([]);
  const [loadingCourses, setLoadingCourses] = React.useState(true);
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    fetchCourses(schoolId)
      .then(setCourses)
      .catch(() => toast.error("Could not load courses. Please refresh."))
      .finally(() => setLoadingCourses(false));
  }, [schoolId]);

  function set<K extends keyof EnquiryFormData>(field: K, value: EnquiryFormData[K]) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!form.first_name.trim() || !form.last_name.trim()) {
      toast.error("Please enter the student's first and last name.");
      return;
    }
    if (!form.email.trim() && !form.phone.trim()) {
      toast.error("Please provide either an email address or a phone number.");
      return;
    }

    setSubmitting(true);
    try {
      const { enquiry_number } = await submitEnquiry(form, schoolId);
      router.push(`/admission/enquiry/success?enq=${encodeURIComponent(enquiry_number)}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Make an Enquiry</h1>
        <p className="text-sm text-muted-foreground">
          Interested in Pinewood? Tell us a bit about your child and we&apos;ll get in touch.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Student Information</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="first_name">First Name *</Label>
              <Input
                id="first_name"
                value={form.first_name}
                onChange={(e) => set("first_name", e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="last_name">Last Name *</Label>
              <Input
                id="last_name"
                value={form.last_name}
                onChange={(e) => set("last_name", e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="date_of_birth">Date of Birth</Label>
              <Input
                id="date_of_birth"
                type="date"
                value={form.date_of_birth}
                onChange={(e) => set("date_of_birth", e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label>Course of Interest</Label>
              <Select value={form.course} onValueChange={(v) => set("course", v)}>
                <SelectTrigger>
                  <SelectValue placeholder={loadingCourses ? "Loading..." : "Select a course"} />
                </SelectTrigger>
                <SelectContent>
                  {courses.map((c) => (
                    <SelectItem key={c.id} value={c.id}>{c.course_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={form.email}
                onChange={(e) => set("email", e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                value={form.phone}
                onChange={(e) => set("phone", e.target.value)}
              />
            </div>
            <p className="text-xs text-muted-foreground sm:col-span-2">
              Please provide at least an email address or a phone number.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Guardian Information (optional)</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="guardian_first_name">First Name</Label>
              <Input
                id="guardian_first_name"
                value={form.guardian_first_name}
                onChange={(e) => set("guardian_first_name", e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="guardian_last_name">Last Name</Label>
              <Input
                id="guardian_last_name"
                value={form.guardian_last_name}
                onChange={(e) => set("guardian_last_name", e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="guardian_relation">Relationship to Student</Label>
              <Input
                id="guardian_relation"
                placeholder="e.g. Mother, Father, Guardian"
                value={form.guardian_relation}
                onChange={(e) => set("guardian_relation", e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="guardian_phone">Phone</Label>
              <Input
                id="guardian_phone"
                value={form.guardian_phone}
                onChange={(e) => set("guardian_phone", e.target.value)}
              />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label htmlFor="guardian_email">Email</Label>
              <Input
                id="guardian_email"
                type="email"
                value={form.guardian_email}
                onChange={(e) => set("guardian_email", e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Additional Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="source_of_info">How did you hear about us?</Label>
              <Input
                id="source_of_info"
                placeholder="e.g. Friend, Social Media, Website"
                value={form.source_of_info}
                onChange={(e) => set("source_of_info", e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="remarks">Message</Label>
              <Textarea
                id="remarks"
                rows={4}
                placeholder="Anything you'd like us to know?"
                value={form.remarks}
                onChange={(e) => set("remarks", e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        <Button type="submit" size="lg" className="w-full" disabled={submitting}>
          {submitting ? <Spinner /> : <Send className="mr-2 h-4 w-4" />}
          Submit Enquiry
        </Button>
      </form>
    </div>
  );
}
