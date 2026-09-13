"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { config, API } from "@/lib/config";
import type { AdmissionCourse, AdmissionFormData } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { CheckCircle2, ChevronLeft, ChevronRight, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { useAdmissionConfig } from "@/hooks/useAdmissionConfig";

// ── Step definitions ──────────────────────────────────────────────────────────

const STEPS = [
  "Terms & Conditions",
  "Academic Info",
  "Student Details",
  "Guardian 1",
  "Guardian 2 & Address",
  "Previous School & Health",
  "Documents",
  "Declaration",
];

// ── Form state ────────────────────────────────────────────────────────────────

interface FormState extends AdmissionFormData {
  // step 1
  terms_agreement: boolean;
  // step 2
  academic_year: string;
  middle_name: string;
  // step 3
  religion: string;
  birth_place: string;
  mother_tongue: string;
  // step 4 - guardian 2
  guardian2_first_name: string;
  guardian2_last_name: string;
  guardian2_relation: string;
  guardian2_occupation: string;
  guardian2_mobile: string;
  guardian2_email: string;
  // student address
  address_line1: string;
  address_line2: string;
  city: string;
  country: string;
  mobile: string;
  // prev school
  previous_school_name: string;
  last_attendance_year: string;
  previous_school_address: string;
  previous_school_phone: string;
  previous_school_email: string;
  // health
  has_medical_problems: string;
  recent_hospitalization: string;
  has_allergies: string;
  medical_details: string;
  religious_observances: string;
  background_information: string;
  // declaration
  declaration_agreement: boolean;
  declaration_date: string;
  // guardian 1 extras
  guardian1_occupation: string;
  guardian1_office_phone1: string;
}

const EMPTY: FormState = {
  terms_agreement: false,
  course_applied: "",
  academic_year: "",
  first_name: "",
  middle_name: "",
  last_name: "",
  date_of_birth: "",
  gender: "",
  nationality: "",
  religion: "",
  birth_place: "",
  mother_tongue: "",
  preferred_name: "",
  home_language: "",
  authorized_pickup_persons: "",
  expected_start_date: "",
  email: "",
  phone: "",
  mobile: "",
  address: "",
  address_line1: "",
  address_line2: "",
  city: "",
  country: "",
  guardian1_first_name: "",
  guardian1_last_name: "",
  guardian1_relation: "",
  guardian1_occupation: "",
  guardian1_office_phone1: "",
  guardian1_mobile: "",
  guardian1_email: "",
  guardian1_house_plot_no: "",
  guardian1_road_name: "",
  guardian1_area_location: "",
  guardian1_flat_block_name: "",
  guardian2_first_name: "",
  guardian2_last_name: "",
  guardian2_relation: "",
  guardian2_occupation: "",
  guardian2_mobile: "",
  guardian2_email: "",
  guardian2_house_plot_no: "",
  guardian2_road_name: "",
  guardian2_area_location: "",
  guardian2_flat_block_name: "",
  emergency_contact_name: "",
  emergency_contact_relation: "",
  emergency_contact_mobile: "",
  emergency_contact_address: "",
  previous_school_name: "",
  last_attendance_year: "",
  previous_school_address: "",
  previous_school_phone: "",
  previous_school_email: "",
  has_medical_problems: "",
  recent_hospitalization: "",
  has_allergies: "",
  medical_details: "",
  religious_observances: "",
  background_information: "",
  declaration_agreement: false,
  declaration_date: new Date().toISOString().slice(0, 10),
  declaration_signature_name: "",
};

// ── API helpers ───────────────────────────────────────────────────────────────

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

const REQUIRED_DOCS: { key: string; label: string }[] = [
  { key: "immunization_record", label: "Under 5-card (Immunisation Record)" },
  { key: "birth_certificate",   label: "Birth Certificate" },
  { key: "passport_photo_1",    label: "Passport Photo 1" },
  { key: "passport_photo_2",    label: "Passport Photo 2" },
  { key: "utility_bill",        label: "Utility Bill" },
  { key: "parent1_id",          label: "NRC – Parent 1" },
  { key: "parent2_id",          label: "NRC – Parent 2" },
];

async function submitApplication(form: FormState, files: Record<string, File>, schoolId?: string) {
  const fd = new FormData();
  // Append all form fields
  const skip = new Set(["terms_agreement", "declaration_agreement"]);
  for (const [k, v] of Object.entries(form)) {
    if (skip.has(k)) {
      fd.append(k, v ? "true" : "false");
    } else if (v !== "" && v !== null && v !== undefined) {
      fd.append(k, String(v));
    }
  }
  fd.append("address", form.address_line1);
  // Include school_id in form data if provided
  if (schoolId) {
    fd.append("school_id", schoolId);
  }
  // Append files
  for (const [key, file] of Object.entries(files)) {
    fd.append(key, file, file.name);
  }
  let url = API.admissionApply;
  if (schoolId) {
    url += `?school_id=${encodeURIComponent(schoolId)}`;
  }
  const res = await fetch(url, {
    method: "POST",
    body: fd,
    // No Content-Type header — browser sets it with boundary for multipart
  });
  const data = await res.json();
  if (!res.ok) throw new Error((data as { error?: string }).error ?? "Submission failed");
  return data as { application_number: string };
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function AdmissionApplyPage() {
  const router = useRouter();
  const { data: admissionConfig, isLoading: loadingConfig } = useAdmissionConfig();
  const searchParams = React.useMemo(() => new URLSearchParams(typeof window !== "undefined" ? window.location.search : ""), []);
  const schoolId = searchParams.get("school_id") || undefined;

  const [step, setStep] = React.useState(0);
  const [form, setForm] = React.useState<FormState>(EMPTY);
  const [files, setFiles] = React.useState<Record<string, File>>({});
  const [courses, setCourses] = React.useState<AdmissionCourse[]>([]);
  const [loadingCourses, setLoadingCourses] = React.useState(true);
  const [submitting, setSubmitting] = React.useState(false);

  // Check if admissions are enabled
  if (loadingConfig) {
    return (
      <div className="mx-auto max-w-3xl">
        <div className="flex items-center justify-center py-20">
          <Spinner />
        </div>
      </div>
    );
  }

  if (!admissionConfig?.enabled) {
    return (
      <div className="mx-auto max-w-3xl">
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-8 text-center text-amber-900">
          <AlertCircle className="mx-auto mb-3 h-8 w-8" />
          <h1 className="mb-2 text-lg font-semibold">Admissions Currently Closed</h1>
          <p className="mb-4 text-sm">
            Thank you for your interest. The admissions process is not currently open.
          </p>
          <Button variant="outline" onClick={() => router.push("/admission")}>
            Back to Admissions
          </Button>
        </div>
      </div>
    );
  }

  React.useEffect(() => {
    fetchCourses(schoolId)
      .then(setCourses)
      .catch(() => toast.error("Could not load courses. Please refresh."))
      .finally(() => setLoadingCourses(false));
  }, [schoolId]);

  function set<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function validateStep(): string | null {
    switch (step) {
      case 0:
        if (!form.terms_agreement)
          return "You must agree to the terms and conditions to proceed.";
        break;
      case 1:
        if (!form.course_applied) return "Please select a grade.";
        if (!form.first_name.trim()) return "First name is required.";
        if (!form.last_name.trim()) return "Last name is required.";
        break;
      case 2:
        if (!form.date_of_birth) return "Date of birth is required.";
        if (!form.gender) return "Gender is required.";
        if (!form.nationality.trim()) return "Nationality is required.";
        break;
      case 3:
        if (!form.guardian1_first_name.trim()) return "Guardian first name is required.";
        if (!form.guardian1_last_name.trim()) return "Guardian last name is required.";
        if (!form.guardian1_relation) return "Guardian relationship is required.";
        if (!form.guardian1_mobile.trim()) return "Guardian mobile number is required.";
        break;
      case 4:
        if (!form.address_line1.trim()) return "Address line 1 is required.";
        if (!form.city.trim()) return "City is required.";
        if (!form.country) return "Country is required.";
        break;
      case 6: {
        const missingDocs = REQUIRED_DOCS.filter((d) => !files[d.key]);
        if (missingDocs.length > 0)
          return `Please upload all required documents: ${missingDocs.map((d) => d.label).join(", ")}`;
        break;
      }
      case 7:
        if (!form.declaration_agreement)
          return "You must sign the declaration to submit.";
        if (!form.declaration_date) return "Declaration date is required.";
        if (!form.declaration_signature_name.trim())
          return "Please type your full name as your signature.";
        break;
    }
    return null;
  }

  function next() {
    const err = validateStep();
    if (err) { toast.error(err); return; }
    setStep((s) => s + 1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function back() {
    setStep((s) => s - 1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSubmit() {
    const err = validateStep();
    if (err) { toast.error(err); return; }
    setSubmitting(true);
    try {
      const result = await submitApplication(form, files, schoolId);
      router.push(`/admission/success?app=${result.application_number}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Submission failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const COUNTRIES = [
    "Zambia", "Zimbabwe", "South Africa", "Malawi", "Tanzania",
    "Mozambique", "Botswana", "Namibia", "Kenya", "Uganda", "Other",
  ];

  const RELATIONSHIPS = [
    "father", "mother", "guardian", "stepfather", "stepmother",
    "grandfather", "grandmother", "uncle", "aunt", "other",
  ];
  const REL_LABEL: Record<string, string> = {
    father: "Father", mother: "Mother", guardian: "Legal Guardian",
    stepfather: "Stepfather", stepmother: "Stepmother",
    grandfather: "Grandfather", grandmother: "Grandmother",
    uncle: "Uncle", aunt: "Aunt", other: "Other",
  };

  const selectedCourse = courses.find((c) => c.id === form.course_applied);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Student Admission Registration</h1>
        <p className="text-sm text-muted-foreground">
          Complete all steps to submit your child&apos;s admission application.
        </p>
      </div>

      {/* Step indicator — compact on mobile, full stepper on sm+ */}
      <div className="sm:hidden">
        <div className="flex items-center gap-3 rounded-lg border bg-background px-4 py-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
            {step < STEPS.length - 1 && step < step ? <CheckCircle2 className="h-4 w-4" /> : step + 1}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{STEPS[step]}</p>
            <p className="text-xs text-muted-foreground">Step {step + 1} of {STEPS.length}</p>
          </div>
          <div className="ml-auto h-1.5 w-24 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
            />
          </div>
        </div>
      </div>

      <div className="hidden overflow-x-auto sm:block">
        <div className="flex min-w-max items-center gap-1 pb-1">
          {STEPS.map((label, i) => (
            <React.Fragment key={label}>
              <div className="flex flex-col items-center gap-1">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
                    i < step
                      ? "bg-primary text-primary-foreground"
                      : i === step
                      ? "border-2 border-primary bg-background text-primary"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {i < step ? <CheckCircle2 className="h-4 w-4" /> : i + 1}
                </div>
                <span className="w-16 text-center text-[9px] leading-tight text-muted-foreground">
                  {label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`mb-4 h-0.5 w-6 shrink-0 ${i < step ? "bg-primary" : "bg-muted"}`} />
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
              {step + 1}
            </span>
            {STEPS[step]}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">

          {/* ── Step 0: Terms & Conditions ── */}
          {step === 0 && (
            <div className="space-y-4">
              <div className="h-96 overflow-y-auto rounded-lg border bg-muted/30 p-5 text-sm leading-relaxed">
                <h4 className="mb-4 text-center font-bold uppercase tracking-wide">
                  CONDITIONS FOR ADMISSION
                </h4>

                <p className="mb-3">
                  <strong><u>1. Admission</u></strong>
                </p>
                <p className="mb-4">
                  Upon receipt of a completed registration form accompanied by the registration fee, the child&apos;s name will be entered on the waiting list. Where appropriate, a placement test will be given to determine the most suitable level for the child, after which a place will be offered. The place will be secured by payment of one term&apos;s fees, which{" "}
                  <strong>must be paid in full before admission to class. Failure to pay fees on time may lead to loss of the place.</strong>
                </p>

                <p className="mb-3">
                  <strong><u>2. Fees</u></strong>
                </p>
                <p className="mb-4">
                  Fees are payable termly before the term starts, with a penalty being charged for payments made after the given deadline. Refunds for whatever reason, e.g., illness or holiday, will not be possible.
                </p>

                <p className="mb-3">
                  <strong><u>3. Withdrawal</u></strong>
                </p>
                <p className="mb-2">
                  In the event of you wishing to withdraw your child at the end of a term, you must give at least 30 days&apos; notice in writing to the school. Failure to do so will result in payment of fees for the following term regardless of whether your child attends or not. If you withdraw your child during the term, you will be liable for the fees for the remainder of that term.
                </p>
                <p className="mb-4">
                  The school reserves the right to discontinue any child who persistently behaves in a manner considered harmful to the general learning environment. This includes the persistent and wilful damage to school property.
                </p>

                <p className="mb-3">
                  <strong><u>4. Calendar and Timetable</u></strong>
                </p>
                <p className="mb-4">
                  Exact term dates will be announced before the end of the preceding term. Classes will normally run from Monday to Friday starting at 7:45 and ending at 12:30 (preschool), and primary classes (grades 1 to 7) end at 13:00. Children should be delivered at the school before 7:30 hours, and it is expected that all children should be collected by 13:30 hours at the latest unless they are attending afternoon activities. Persistent late collection of children will be charged to cover the cost of supervision.
                </p>

                <p className="mb-3">
                  <strong><u>5. Illness and Accidents</u></strong>
                </p>
                <p className="mb-2">
                  In case of emergencies, every effort will be made to contact parents/guardians. You are therefore requested to inform the school promptly of any change of address or telephone numbers at home or at work. In the event that you cannot be contacted, the school will automatically seek further medical advice if deemed necessary.
                </p>
                <p className="mb-2">
                  If the child contracts or comes into contact with any infectious disease, parents must inform the school immediately. A doctor&apos;s confirmation of fitness may be required before readmission.
                </p>
                <p className="mb-4">
                  Whilst every effort will be made to avoid accidents, and supervision will be provided as far as possible at all times, the school will not accept liability for any accidents that may occur on the school premises, including all car parking areas.
                </p>

                <p className="mb-3">
                  <strong><u>6. Losses</u></strong>
                </p>
                <p className="mb-4">
                  The school cannot take responsibility for loss or damage to any of the child&apos;s personal property or the property belonging to anyone within the school premises, including all car parking areas. However, every effort will be made to prevent any losses from occurring.
                </p>

                <p className="mb-3">
                  <strong><u>7. Clothing and Equipment</u></strong>
                </p>
                <p>
                  Children in the Reception and Primary classes must wear school uniforms at all times unless otherwise instructed. Children in the nursery should dress in clothes suitable for the rough and tumble of pre-school activities. Requirements for any special clothing, e.g., P.E. kit will be announced when required. Younger children must carry a spare set of essential clothes in case of emergency. All clothes and items carried by the child should be clearly labelled.
                </p>
              </div>

              <div className="flex items-start gap-3 rounded-lg border p-4">
                <Checkbox
                  id="terms"
                  checked={form.terms_agreement}
                  onCheckedChange={(v) => set("terms_agreement", !!v)}
                />
                <Label htmlFor="terms" className="cursor-pointer text-sm leading-snug">
                  <strong>I have read the terms/conditions and agree to abide by them.</strong>
                </Label>
              </div>
            </div>
          )}

          {/* ── Step 1: Academic & Basic Student Info ── */}
          {step === 1 && (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Class Applied For" required>
                  {loadingCourses ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Loading…</div>
                  ) : (
                    <Select value={form.course_applied} onValueChange={(v) => set("course_applied", v)}>
                      <SelectTrigger><SelectValue placeholder="Select Class" /></SelectTrigger>
                      <SelectContent>
                        {courses.map((c) => (
                          <SelectItem key={c.id} value={c.id}>{c.course_name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="First Name" required>
                  <Input value={form.first_name} onChange={(e) => set("first_name", e.target.value)} />
                </Field>
                <Field label="Middle Name">
                  <Input value={form.middle_name} onChange={(e) => set("middle_name", e.target.value)} />
                </Field>
                <Field label="Last Name" required>
                  <Input value={form.last_name} onChange={(e) => set("last_name", e.target.value)} />
                </Field>
              </div>
            </div>
          )}

          {/* ── Step 2: Student Details ── */}
          {step === 2 && (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Date of Birth" required>
                  <Input type="date" value={form.date_of_birth} onChange={(e) => set("date_of_birth", e.target.value)} />
                </Field>
                <Field label="Gender" required>
                  <Select value={form.gender} onValueChange={(v) => set("gender", v)}>
                    <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="male">Male</SelectItem>
                      <SelectItem value="female">Female</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Nationality" required>
                  <Input value={form.nationality} onChange={(e) => set("nationality", e.target.value)} />
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Religion">
                  <Input value={form.religion} onChange={(e) => set("religion", e.target.value)} />
                </Field>
                <Field label="Birth Place">
                  <Input value={form.birth_place} onChange={(e) => set("birth_place", e.target.value)} />
                </Field>
                <Field label="Mother Tongue">
                  <Input value={form.mother_tongue} onChange={(e) => set("mother_tongue", e.target.value)} />
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="E-mail">
                  <Input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Name by which child should be addressed in school">
                  <Input value={form.preferred_name} onChange={(e) => set("preferred_name", e.target.value)} />
                </Field>
                <Field label="Language most commonly spoken in child's home">
                  <Input value={form.home_language} onChange={(e) => set("home_language", e.target.value)} />
                </Field>
              </div>
              <Field label="Person(s) authorised to collect child(ren) from school">
                <textarea
                  className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  rows={2}
                  placeholder="Please notify us immediately of any changes. No child will be released to an unauthorised person."
                  value={form.authorized_pickup_persons}
                  onChange={(e) => set("authorized_pickup_persons", e.target.value)}
                />
              </Field>
            </div>
          )}

          {/* ── Step 3: Guardian 1 ── */}
          {step === 3 && (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="First Name" required>
                  <Input value={form.guardian1_first_name} onChange={(e) => set("guardian1_first_name", e.target.value)} />
                </Field>
                <Field label="Last Name" required>
                  <Input value={form.guardian1_last_name} onChange={(e) => set("guardian1_last_name", e.target.value)} />
                </Field>
                <Field label="Relation" required>
                  <Select value={form.guardian1_relation} onValueChange={(v) => set("guardian1_relation", v)}>
                    <SelectTrigger><SelectValue placeholder="Select Relationship" /></SelectTrigger>
                    <SelectContent>
                      {RELATIONSHIPS.map((r) => (
                        <SelectItem key={r} value={r}>{REL_LABEL[r]}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Occupation">
                  <Input value={form.guardian1_occupation} onChange={(e) => set("guardian1_occupation", e.target.value)} />
                </Field>
                <Field label="Office Phone">
                  <Input value={form.guardian1_office_phone1} onChange={(e) => set("guardian1_office_phone1", e.target.value)} placeholder="+260-123-456789" />
                </Field>
                <Field label="Mobile" required>
                  <Input value={form.guardian1_mobile} onChange={(e) => set("guardian1_mobile", e.target.value)} placeholder="+260-123-456789" />
                </Field>
              </div>
              <Field label="E-mail">
                <Input type="email" value={form.guardian1_email} onChange={(e) => set("guardian1_email", e.target.value)} />
              </Field>

              <hr className="my-2" />
              <p className="text-sm font-semibold text-primary">Residential Address <span className="font-normal text-muted-foreground">(if different from the child&apos;s)</span></p>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="House/Plot No.">
                  <Input value={form.guardian1_house_plot_no} onChange={(e) => set("guardian1_house_plot_no", e.target.value)} />
                </Field>
                <Field label="Road Name">
                  <Input value={form.guardian1_road_name} onChange={(e) => set("guardian1_road_name", e.target.value)} />
                </Field>
                <Field label="Area/Location">
                  <Input value={form.guardian1_area_location} onChange={(e) => set("guardian1_area_location", e.target.value)} />
                </Field>
              </div>
              <Field label="Flat/Block No. and Name">
                <Input value={form.guardian1_flat_block_name} onChange={(e) => set("guardian1_flat_block_name", e.target.value)} placeholder="If residing in flats" />
              </Field>
            </div>
          )}

          {/* ── Step 4: Guardian 2 & Address ── */}
          {step === 4 && (
            <div className="space-y-4">
              <p className="text-sm font-semibold text-primary">Guardian 2 (Optional)</p>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="First Name">
                  <Input value={form.guardian2_first_name} onChange={(e) => set("guardian2_first_name", e.target.value)} />
                </Field>
                <Field label="Last Name">
                  <Input value={form.guardian2_last_name} onChange={(e) => set("guardian2_last_name", e.target.value)} />
                </Field>
                <Field label="Relation">
                  <Select value={form.guardian2_relation} onValueChange={(v) => set("guardian2_relation", v)}>
                    <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      {RELATIONSHIPS.map((r) => (
                        <SelectItem key={r} value={r}>{REL_LABEL[r]}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Occupation">
                  <Input value={form.guardian2_occupation} onChange={(e) => set("guardian2_occupation", e.target.value)} />
                </Field>
                <Field label="Mobile">
                  <Input value={form.guardian2_mobile} onChange={(e) => set("guardian2_mobile", e.target.value)} />
                </Field>
                <Field label="E-mail">
                  <Input type="email" value={form.guardian2_email} onChange={(e) => set("guardian2_email", e.target.value)} />
                </Field>
              </div>

              <hr className="my-2" />
              <p className="text-sm font-semibold text-primary">Guardian 2 Residential Address <span className="font-normal text-muted-foreground">(if different from the child&apos;s)</span></p>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="House/Plot No.">
                  <Input value={form.guardian2_house_plot_no} onChange={(e) => set("guardian2_house_plot_no", e.target.value)} />
                </Field>
                <Field label="Road Name">
                  <Input value={form.guardian2_road_name} onChange={(e) => set("guardian2_road_name", e.target.value)} />
                </Field>
                <Field label="Area/Location">
                  <Input value={form.guardian2_area_location} onChange={(e) => set("guardian2_area_location", e.target.value)} />
                </Field>
              </div>
              <Field label="Flat/Block No. and Name">
                <Input value={form.guardian2_flat_block_name} onChange={(e) => set("guardian2_flat_block_name", e.target.value)} placeholder="If residing in flats" />
              </Field>

              <hr className="my-2" />
              <p className="text-sm font-semibold text-primary">Alternative Emergency Contact <span className="font-normal text-muted-foreground">(if nobody can be reached above during school hours)</span></p>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Name">
                  <Input value={form.emergency_contact_name} onChange={(e) => set("emergency_contact_name", e.target.value)} />
                </Field>
                <Field label="Relation to child">
                  <Input value={form.emergency_contact_relation} onChange={(e) => set("emergency_contact_relation", e.target.value)} />
                </Field>
                <Field label="Mobile">
                  <Input value={form.emergency_contact_mobile} onChange={(e) => set("emergency_contact_mobile", e.target.value)} placeholder="+260-123-456789" />
                </Field>
              </div>
              <Field label="Residential address">
                <Input value={form.emergency_contact_address} onChange={(e) => set("emergency_contact_address", e.target.value)} />
              </Field>

              <hr className="my-2" />
              <p className="text-sm font-semibold text-primary">Student Address</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Address Line 1" required>
                  <Input value={form.address_line1} onChange={(e) => set("address_line1", e.target.value)} placeholder="Street address, P.O. Box, etc." />
                </Field>
                <Field label="Address Line 2">
                  <Input value={form.address_line2} onChange={(e) => set("address_line2", e.target.value)} placeholder="Apartment, suite, etc." />
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="City" required>
                  <Input value={form.city} onChange={(e) => set("city", e.target.value)} />
                </Field>
                <Field label="Country" required>
                  <Select value={form.country} onValueChange={(v) => set("country", v)}>
                    <SelectTrigger><SelectValue placeholder="Select Country" /></SelectTrigger>
                    <SelectContent>
                      {COUNTRIES.map((c) => (
                        <SelectItem key={c} value={c}>{c}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Phone">
                  <Input value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="+260-123-456789" />
                </Field>
              </div>
              <Field label="Mobile">
                <Input value={form.mobile} onChange={(e) => set("mobile", e.target.value)} placeholder="Student mobile number" />
              </Field>
            </div>
          )}

          {/* ── Step 5: Previous School & Health ── */}
          {step === 5 && (
            <div className="space-y-4">
              <p className="text-sm font-semibold text-primary">Previous School Attended</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Name of school previously attended">
                  <Input value={form.previous_school_name} onChange={(e) => set("previous_school_name", e.target.value)} />
                </Field>
                <Field label="Last attendance year">
                  <Input type="number" min={1990} max={2030} placeholder="e.g. 2023" value={form.last_attendance_year} onChange={(e) => set("last_attendance_year", e.target.value)} />
                </Field>
              </div>
              <Field label="Address">
                <Input value={form.previous_school_address} onChange={(e) => set("previous_school_address", e.target.value)} />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Phone No">
                  <Input value={form.previous_school_phone} onChange={(e) => set("previous_school_phone", e.target.value)} />
                </Field>
                <Field label="Email">
                  <Input type="email" value={form.previous_school_email} onChange={(e) => set("previous_school_email", e.target.value)} />
                </Field>
              </div>
              <Field label="When do you expect the child to begin primary school?">
                <Input type="date" value={form.expected_start_date} onChange={(e) => set("expected_start_date", e.target.value)} className="max-w-[220px]" />
              </Field>

              <hr className="my-2" />
              <p className="text-sm font-semibold text-primary">Health Information</p>
              <div className="grid gap-4 sm:grid-cols-3">
                <RadioField label="Medical problems?" name="has_medical_problems" value={form.has_medical_problems} onChange={(v) => set("has_medical_problems", v)} />
                <RadioField label="Recent hospitalization?" name="recent_hospitalization" value={form.recent_hospitalization} onChange={(v) => set("recent_hospitalization", v)} />
                <RadioField label="Any allergies?" name="has_allergies" value={form.has_allergies} onChange={(v) => set("has_allergies", v)} />
              </div>
              <Field label="Medical details (if any of above is YES)">
                <textarea
                  className="flex min-h-[72px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  rows={2}
                  placeholder="Provide details if you answered YES above"
                  value={form.medical_details}
                  onChange={(e) => set("medical_details", e.target.value)}
                />
              </Field>
              <Field label="Religious observances requirements">
                <textarea
                  className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  rows={1}
                  value={form.religious_observances}
                  onChange={(e) => set("religious_observances", e.target.value)}
                />
              </Field>
              <Field label="Background information on the child">
                <textarea
                  className="flex min-h-[72px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  rows={2}
                  placeholder="Any additional background information helpful for the school"
                  value={form.background_information}
                  onChange={(e) => set("background_information", e.target.value)}
                />
              </Field>
            </div>
          )}

          {/* ── Step 6: Documents ── */}
          {step === 6 && (
            <div className="space-y-4">
              <div className="rounded-lg border bg-muted/40 p-4 text-sm text-muted-foreground">
                <p className="mb-2 font-semibold text-foreground">Required Documents</p>
                <p className="mb-2">
                  All documents below are <strong>required</strong> to complete your application. Please upload clear, readable copies (PDF, JPG, PNG – max 5 MB each).
                </p>
              </div>
              {REQUIRED_DOCS.map((doc) => (
                <UploadField
                  key={doc.key}
                  label={doc.label}
                  name={doc.key}
                  required
                  file={files[doc.key]}
                  onFileChange={(f) =>
                    setFiles((prev) => ({ ...prev, [doc.key]: f }))
                  }
                />
              ))}
            </div>
          )}

          {/* ── Step 7: Declaration ── */}
          {step === 7 && (
            <div className="space-y-5">
              {/* Summary */}
              <div className="rounded-lg border bg-muted/30 p-4">
                <p className="mb-3 font-semibold">Application Summary</p>
                <dl className="grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
                  <ReviewRow label="Grade" value={selectedCourse?.course_name} />
                  <ReviewRow label="Student Name" value={`${form.first_name} ${form.middle_name} ${form.last_name}`.trim()} />
                  <ReviewRow label="Date of Birth" value={form.date_of_birth} />
                  <ReviewRow label="Gender" value={form.gender} />
                  <ReviewRow label="Nationality" value={form.nationality} />
                  <ReviewRow label="Guardian" value={`${form.guardian1_first_name} ${form.guardian1_last_name}`} />
                  <ReviewRow label="Guardian Mobile" value={form.guardian1_mobile} />
                  <ReviewRow label="Address" value={`${form.address_line1}, ${form.city}, ${form.country}`} />
                </dl>
              </div>

              <div className="flex items-start gap-3 rounded-lg border p-4">
                <Checkbox
                  id="declaration"
                  checked={form.declaration_agreement}
                  onCheckedChange={(v) => set("declaration_agreement", !!v)}
                />
                <Label htmlFor="declaration" className="cursor-pointer text-sm leading-snug">
                  <strong>
                    I hereby declare that all the information provided in this application is true and complete to the best of my knowledge. I understand that any false information may result in the rejection of this application.
                  </strong>
                </Label>
              </div>

              <Field label="Date" required>
                <Input
                  type="date"
                  value={form.declaration_date}
                  onChange={(e) => set("declaration_date", e.target.value)}
                  className="max-w-[200px]"
                />
              </Field>

              <Field label="Signature of Parent/Guardian" required>
                <Input
                  value={form.declaration_signature_name}
                  onChange={(e) => set("declaration_signature_name", e.target.value)}
                  placeholder="Type your full name as your signature"
                />
              </Field>
            </div>
          )}

          {/* Navigation */}
          <div className="flex flex-col gap-2 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
            <Button variant="outline" onClick={back} disabled={step === 0} className="w-full sm:w-auto">
              <ChevronLeft className="mr-1 h-4 w-4" /> Previous
            </Button>
            {step < STEPS.length - 1 ? (
              <Button onClick={next} className="w-full sm:w-auto">
                Next <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            ) : (
              <Button onClick={handleSubmit} disabled={submitting} className="w-full sm:w-auto">
                {submitting ? <Spinner /> : null}
                Submit Application
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Small helper components ───────────────────────────────────────────────────

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs font-medium">
        {label}
        {required && <span className="ml-0.5 text-destructive">*</span>}
      </Label>
      {children}
    </div>
  );
}

function RadioField({ label, name, value, onChange }: { label: string; name: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs font-medium">{label}</Label>
      <div className="flex gap-4 text-sm">
        {["yes", "no"].map((v) => (
          <label key={v} className="flex cursor-pointer items-center gap-1.5">
            <input
              type="radio"
              name={name}
              value={v}
              checked={value === v}
              onChange={() => onChange(v)}
              className="accent-primary"
            />
            {v.charAt(0).toUpperCase() + v.slice(1)}
          </label>
        ))}
      </div>
    </div>
  );
}

function UploadField({
  label,
  name,
  required,
  file,
  onFileChange,
}: {
  label: string;
  name: string;
  required?: boolean;
  file?: File;
  onFileChange?: (f: File) => void;
}) {
  const uploaded = !!file;
  return (
    <div className="space-y-1">
      <Label className="text-xs font-medium">
        {label}
        {required && <span className="ml-0.5 text-destructive">*</span>}
      </Label>
      <label
        htmlFor={name}
        className={`flex cursor-pointer items-center gap-3 rounded-lg border border-dashed px-4 py-3 text-sm transition-colors ${
          uploaded
            ? "border-primary bg-primary/5 text-primary"
            : "text-muted-foreground hover:border-primary hover:text-primary"
        }`}
      >
        <span className="text-lg">{uploaded ? "✅" : "📎"}</span>
        <span className="flex-1 truncate">
          {file?.name ?? `Click to upload (PDF, JPG, PNG – max 5 MB)${required ? "" : " – Optional"}`}
        </span>
        {uploaded && (
          <span className="shrink-0 text-xs text-muted-foreground">
            {(file!.size / 1024 / 1024).toFixed(2)} MB
          </span>
        )}
        <input
          id={name}
          name={name}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFileChange?.(f);
          }}
        />
      </label>
    </div>
  );
}

function ReviewRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="sm:contents">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium sm:mt-0">{value || "—"}</dd>
    </div>
  );
}
