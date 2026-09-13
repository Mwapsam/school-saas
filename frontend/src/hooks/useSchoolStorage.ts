/**
 * Hook to access school-namespaced localStorage.
 *
 * Enables sharing a browser across multiple schools without data collision.
 * All keys are automatically prefixed with the school code.
 *
 * Usage:
 *   const storage = useSchoolStorage();
 *   storage.setItem("preferences", JSON.stringify({...}));
 *   const prefs = JSON.parse(storage.getItem("preferences") ?? "{}");
 */

import { useAuthStore } from "@/lib/auth-store";
import { useSchoolConfig } from "./useSchoolConfig";

export function useSchoolStorage() {
  const schoolCode = useAuthStore((s) => s.schoolCode);
  const { data: schoolConfig } = useSchoolConfig();

  // Use schoolCode from auth store (set during login), or fall back to school config code
  const code = schoolCode || schoolConfig?.code || "unknown";

  const getKey = (key: string) => `${code}:${key}`;

  return {
    getItem: (key: string): string | null => {
      try {
        return localStorage.getItem(getKey(key));
      } catch {
        return null;
      }
    },

    setItem: (key: string, value: string): void => {
      try {
        localStorage.setItem(getKey(key), value);
      } catch (error) {
        console.error("Error setting school storage:", error);
      }
    },

    removeItem: (key: string): void => {
      try {
        localStorage.removeItem(getKey(key));
      } catch (error) {
        console.error("Error removing school storage:", error);
      }
    },

    clear: (): void => {
      try {
        const prefix = `${code}:`;
        for (let i = localStorage.length - 1; i >= 0; i--) {
          const key = localStorage.key(i);
          if (key?.startsWith(prefix)) {
            localStorage.removeItem(key);
          }
        }
      } catch (error) {
        console.error("Error clearing school storage:", error);
      }
    },
  };
}
