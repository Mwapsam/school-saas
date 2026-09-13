"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { useAuth, useHydrated } from "@/hooks/use-auth";
import { homeForRoles } from "@/lib/navigation";
import { Spinner } from "@/components/ui/spinner";

export default function IndexPage() {
  const router = useRouter();
  const hydrated = useHydrated();
  const { isAuthenticated, roles, activeRole } = useAuth();

  React.useEffect(() => {
    if (!hydrated) return;
    if (isAuthenticated && roles.length) {
      router.replace(homeForRoles(roles, activeRole));
    } else {
      router.replace("/login");
    }
  }, [hydrated, isAuthenticated, roles, activeRole, router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner className="h-6 w-6 text-primary" />
    </div>
  );
}
