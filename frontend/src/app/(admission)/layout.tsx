import Link from "next/link";
import Image from "next/image";
import { AdmissionNav } from "@/components/admission-nav";

export default function AdmissionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
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
                src="/logo.png"
                alt="Pinewood Preparatory School"
                width={34}
                height={34}
                className="object-contain"
                priority
              />
            </div>
            <span className="text-sm sm:text-base">Pinewood Preparatory School</span>
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
        &copy; {new Date().getFullYear()} Pinewood Preparatory School &mdash;
        office@pinewoodschoolzambia.com &mdash; 0211 291167
      </footer>
    </div>
  );
}
