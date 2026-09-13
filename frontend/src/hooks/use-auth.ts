"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { API } from "@/lib/config";
import { useAuthStore, rolesOf } from "@/lib/auth-store";
import type { LoginResponse, ChangePasswordPayload } from "@/lib/types";

/** Track when the persisted zustand store has rehydrated on the client so we
 *  don't redirect before we know whether the user is logged in. */
export function useHydrated() {
  // Start false so SSR/prerender never touches the persist API or localStorage;
  // resolve the real value on the client after mount.
  const [hydrated, setHydrated] = React.useState(false);
  React.useEffect(() => {
    const persist = useAuthStore.persist;
    const unsub = persist?.onFinishHydration(() => setHydrated(true));
    if (persist?.hasHydrated()) setHydrated(true);
    return unsub;
  }, []);
  return hydrated;
}

export function useAuth() {
  const access = useAuthStore((s) => s.access);
  const user = useAuthStore((s) => s.user);
  const activeRole = useAuthStore((s) => s.activeRole);
  const roles = rolesOf(user);
  return {
    isAuthenticated: !!access,
    user,
    role: user?.role ?? null,
    roles,
    activeRole: activeRole ?? roles[0] ?? null,
  };
}

export function useLogin() {
  const setSession = useAuthStore((s) => s.setSession);
  return useMutation({
    mutationFn: (credentials: { username: string; password: string }) =>
      apiFetch<LoginResponse>(API.login, {
        method: "POST",
        anonymous: true,
        body: credentials,
      }),
    onSuccess: (data) => {
      setSession({ access: data.access, refresh: data.refresh, user: data.user });
    },
  });
}

export function useLogout() {
  const clear = useAuthStore((s) => s.clear);
  const queryClient = useQueryClient();
  return React.useCallback(() => {
    clear();
    queryClient.clear();
  }, [clear, queryClient]);
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (payload: ChangePasswordPayload) =>
      apiFetch<{ detail: string }>(API.passwordChange, {
        method: "POST",
        body: payload,
      }),
  });
}

export function usePasswordResetConfirm() {
  return useMutation({
    mutationFn: (payload: { token: string; new_password: string; confirm_password: string }) =>
      apiFetch<{ detail: string }>(API.passwordResetConfirm, {
        method: "POST",
        body: payload,
        anonymous: true,
      }),
  });
}

export function usePasswordResetRequest() {
  return useMutation({
    mutationFn: (payload: { email: string }) =>
      apiFetch<{ detail: string }>(API.passwordResetRequest, {
        method: "POST",
        body: payload,
        anonymous: true,
      }),
  });
}
