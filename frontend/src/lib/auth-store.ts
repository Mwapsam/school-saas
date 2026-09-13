import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Role, UserProfile } from "./types";

interface AuthState {
  access: string | null;
  refresh: string | null;
  user: UserProfile | null;
  /** Which of the user's roles is currently in focus (role/module switcher). */
  activeRole: Role | null;
  /** School code to detect when user switches schools (multi-tenant support) */
  schoolCode: string | null;
  setSession: (session: {
    access: string;
    refresh: string;
    user: UserProfile;
    schoolCode?: string;
  }) => void;
  setTokens: (tokens: { access: string; refresh?: string }) => void;
  setUser: (user: UserProfile) => void;
  setActiveRole: (role: Role) => void;
  setSchoolCode: (code: string) => void;
  clear: () => void;
}

/** Roles held by a profile, tolerant of older sessions that only had `role`. */
export function rolesOf(user: UserProfile | null): Role[] {
  if (!user) return [];
  if (user.roles && user.roles.length) return user.roles;
  return user.role ? [user.role] : [];
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      access: null,
      refresh: null,
      user: null,
      activeRole: null,
      schoolCode: null,
      setSession: ({ access, refresh, user, schoolCode }) =>
        set({
          access,
          refresh,
          user,
          schoolCode: schoolCode ?? null,
          activeRole: rolesOf(user)[0] ?? null,
        }),
      setTokens: ({ access, refresh }) =>
        set((s) => ({ access, refresh: refresh ?? s.refresh })),
      setUser: (user) =>
        set((s) => ({
          user,
          activeRole:
            s.activeRole && rolesOf(user).includes(s.activeRole)
              ? s.activeRole
              : rolesOf(user)[0] ?? null,
        })),
      setActiveRole: (role) =>
        set((s) =>
          rolesOf(s.user).includes(role) ? { activeRole: role } : s,
        ),
      setSchoolCode: (code) =>
        set({ schoolCode: code }),
      clear: () =>
        set({ access: null, refresh: null, user: null, activeRole: null, schoolCode: null }),
    }),
    {
      name: "school-portal-auth",
      partialize: (s) => ({
        access: s.access,
        refresh: s.refresh,
        user: s.user,
        activeRole: s.activeRole,
        schoolCode: s.schoolCode,
      }),
    },
  ),
);

export function currentRole(): Role | null {
  return useAuthStore.getState().user?.role ?? null;
}

export function currentRoles(): Role[] {
  return rolesOf(useAuthStore.getState().user);
}
