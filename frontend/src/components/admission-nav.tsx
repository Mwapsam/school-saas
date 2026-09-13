"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";

const LINKS = [
  { href: "/admission", label: "Home" },
  { href: "/admission/apply", label: "Apply" },
  { href: "/admission/enquiry", label: "Enquire" },
  { href: "/admission/status", label: "Track Application" },
  { href: "/login", label: "Staff Login", isButton: true },
];

export function AdmissionNav() {
  const [open, setOpen] = React.useState(false);
  const pathname = usePathname();

  // Close the drawer whenever the route changes
  React.useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <>
      {/* ── Desktop nav (hidden on xs, shown on sm+) ───────────────── */}
      <nav className="hidden items-center gap-4 text-sm sm:flex">
        {LINKS.map((link) =>
          link.isButton ? (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-md border border-primary-foreground/30 px-3 py-1.5 text-xs opacity-80 hover:opacity-100"
            >
              {link.label}
            </Link>
          ) : (
            <Link
              key={link.href}
              href={link.href}
              className="opacity-80 hover:opacity-100"
            >
              {link.label}
            </Link>
          ),
        )}
      </nav>

      {/* ── Mobile hamburger (shown only on xs) ────────────────────── */}
      <button
        className="flex h-9 w-9 items-center justify-center rounded-md sm:hidden"
        aria-label={open ? "Close menu" : "Open menu"}
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {/* ── Mobile dropdown panel ───────────────────────────────────── */}
      {open && (
        <div className="absolute left-0 right-0 top-full z-50 border-b bg-primary px-4 pb-4 pt-2 sm:hidden">
          {LINKS.map((link) =>
            link.isButton ? (
              <Link
                key={link.href}
                href={link.href}
                className="mt-2 flex w-full items-center justify-center rounded-md border border-primary-foreground/30 py-2 text-sm text-primary-foreground opacity-80 hover:opacity-100"
              >
                {link.label}
              </Link>
            ) : (
              <Link
                key={link.href}
                href={link.href}
                className="block py-2 text-sm text-primary-foreground opacity-80 hover:opacity-100"
              >
                {link.label}
              </Link>
            ),
          )}
        </div>
      )}
    </>
  );
}
