"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { useAuth, useHydrated } from "@/hooks/use-auth";
import { homeForRoles } from "@/lib/navigation";
import type { Role } from "@/lib/types";
import { Spinner } from "@/components/ui/spinner";

function FullScreenLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner className="h-6 w-6 text-primary" />
    </div>
  );
}

/**
 * Client-side route guard. Waits for the persisted auth store to hydrate, then:
 *  - redirects unauthenticated users to /login
 *  - enforces the required role (sends users to their own home if mismatched)
 *
 * When a session expires mid-session (token cleared by apiFetch after a failed
 * refresh), the guard cancels all in-flight queries and shows a toast before
 * redirecting so the user understands why they were logged out.
 */
export function AuthGuard({
  role,
  children,
}: {
  role: Role;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const hydrated = useHydrated();
  const { isAuthenticated, roles, activeRole } = useAuth();
  const hasRole = roles.includes(role);

  // Track whether the user was ever authenticated in this session so we can
  // distinguish a genuine logout/expiry from "never logged in".
  const wasAuthenticated = React.useRef(false);

  React.useEffect(() => {
    if (!hydrated) return;

    if (!isAuthenticated) {
      // Cancel and discard all cached queries so no stale 401-retries fire
      // after the token has been cleared.
      queryClient.clear();

      if (wasAuthenticated.current) {
        toast.warning("Your session has expired. Please log in again.");
      }

      router.replace("/login");
      return;
    }

    if (roles.length && !hasRole) {
      router.replace(homeForRoles(roles, activeRole));
      return;
    }

    wasAuthenticated.current = true;
  }, [hydrated, isAuthenticated, roles, hasRole, activeRole, role, router, queryClient]);

  if (!hydrated || !isAuthenticated || !hasRole) {
    return <FullScreenLoader />;
  }
  return <>{children}</>;
}
