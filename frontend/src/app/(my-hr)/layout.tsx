"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { useAuth, useHydrated } from "@/hooks/use-auth";
import { AppShell } from "@/components/app-shell";
import { homeForRoles } from "@/lib/navigation";
import { Spinner } from "@/components/ui/spinner";

/**
 * "My HR" self-service is available to any authenticated user whose account is
 * linked to an active employee record — regardless of portal role. The shell
 * is rendered for their active (or primary) role so the rest of their portal
 * navigation stays intact.
 */
export default function MyHRLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const hydrated = useHydrated();
  const { isAuthenticated, user, roles, activeRole, role } = useAuth();

  React.useEffect(() => {
    if (!hydrated) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (user && !user.has_employee_profile) {
      router.replace(homeForRoles(roles, activeRole));
    }
  }, [hydrated, isAuthenticated, user, roles, activeRole, router]);

  if (!hydrated || !isAuthenticated || (user && !user.has_employee_profile)) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="h-6 w-6 text-primary" />
      </div>
    );
  }

  return <AppShell role={(activeRole ?? role ?? "teacher")}>{children}</AppShell>;
}
