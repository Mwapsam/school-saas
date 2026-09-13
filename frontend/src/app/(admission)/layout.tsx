"use client";

import Link from "next/link";
import Image from "next/image";
import { AdmissionNav } from "@/components/admission-nav";
import { useSchoolConfig } from "@/hooks/useSchoolConfig";

export default function AdmissionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: schoolConfig } = useSchoolConfig();

  const schoolName = schoolConfig?.name || "School Portal";
  const schoolLogo = schoolConfig?.logo_url || "/logo.png";
  const contactEmail = schoolConfig?.contact_email || "contact@school.example";
  const contactPhone = schoolConfig?.contact_phone || "";

  return (
    <div className="flex min-h-screen flex-col bg-muted/30">
      {/* Public header — relative so the mobile dropdown can anchor to it */}
      <header className="relative border-b bg-primary text-primary-foreground shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-2">
          <Link
            href="/admission"
            className="flex items-center gap-2.5 font-semibold"
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-md bg-white/15 p-0.5">
              <Image
                src={schoolLogo}
                alt={schoolName}
                width={34}
                height={34}
                className="object-contain"
                priority
                onError={(e) => {
                  (e.target as HTMLImageElement).src = "/logo.png";
                }}
              />
            </div>
            <span className="text-sm sm:text-base">{schoolName}</span>
          </Link>
          <AdmissionNav />
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 py-6 sm:py-8">
        <div className="mx-auto max-w-5xl px-4">{children}</div>
      </main>

      {/* Footer */}
      <footer className="border-t bg-background py-4 text-center text-xs text-muted-foreground">
        <div className="space-y-1">
          <div>&copy; {new Date().getFullYear()} {schoolName}</div>
          <div className="flex flex-wrap items-center justify-center gap-2 text-[11px]">
            {contactEmail && <a href={`mailto:${contactEmail}`} className="hover:text-foreground">{contactEmail}</a>}
            {contactEmail && contactPhone && <span>—</span>}
            {contactPhone && <span>{contactPhone}</span>}
          </div>
        </div>
      </footer>
    </div>
  );
}
