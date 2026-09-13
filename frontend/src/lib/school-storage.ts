/**
 * Custom Zustand storage adapter that namespaces all keys by school code.
 *
 * Enables multi-tenant support: when a user switches schools, their auth state
 * and preferences are kept separate in localStorage by using schoolCode as a prefix.
 *
 * Usage with Zustand:
 *   persist(
 *     (set) => ({...}),
 *     {
 *       name: "auth",
 *       storage: createSchoolStorage("school-code-field-name"),
 *     }
 *   )
 */

import type { StateStorage } from "zustand/middleware";

/**
 * Create a namespaced storage adapter that uses a field from the state as the namespace key.
 *
 * @param schoolCodeField - The field name in state that contains the school code (e.g., "schoolCode")
 * @param fallbackKey - Default namespace if schoolCode is null/undefined (default: "unknown")
 */
export function createSchoolStorage(
  schoolCodeField: string = "schoolCode",
  fallbackKey: string = "unknown",
): StateStorage {
  return {
    getItem: (key: string) => {
      try {
        // First, check if there's a legacy non-namespaced key we should migrate from
        // This allows smooth migration from old non-namespaced data
        const legacy = localStorage.getItem(key);
        if (legacy) {
          try {
            const data = JSON.parse(legacy);
            if (data && typeof data === "object" && schoolCodeField in data) {
              // Found legacy data with schoolCode; migrate it
              const schoolCode = (data as Record<string, unknown>)[schoolCodeField] || fallbackKey;
              const namespacedKey = `${schoolCode}:${key}`;
              localStorage.setItem(namespacedKey, legacy);
              localStorage.removeItem(key); // Clean up legacy
              return legacy;
            }
          } catch {
            // Not JSON or doesn't have schoolCode; use as-is
            return legacy;
          }
        }

        // Check for namespaced keys by reading all localStorage and finding one that matches
        // We need to scan because we don't know the schoolCode yet (it's being hydrated)
        const pattern = new RegExp(`^[^:]+:${key}$`);
        for (let i = 0; i < localStorage.length; i++) {
          const storedKey = localStorage.key(i);
          if (storedKey && pattern.test(storedKey)) {
            return localStorage.getItem(storedKey);
          }
        }

        return null;
      } catch (error) {
        console.error("Error reading from school storage:", error);
        return null;
      }
    },

    setItem: (key: string, value: string) => {
      try {
        // Parse the value to extract schoolCode
        const data = JSON.parse(value);
        const schoolCode =
          (data && typeof data === "object" && (data as Record<string, unknown>)[schoolCodeField]) ||
          fallbackKey;

        const namespacedKey = `${schoolCode}:${key}`;

        // If schoolCode changed, clean up old namespaced keys to avoid accumulation
        // This handles the case where a user logged out and logs in as a different user
        // at a different school within the same browser session
        const pattern = new RegExp(`^[^:]+:${key}$`);
        for (let i = localStorage.length - 1; i >= 0; i--) {
          const storedKey = localStorage.key(i);
          if (storedKey && pattern.test(storedKey) && storedKey !== namespacedKey) {
            localStorage.removeItem(storedKey);
          }
        }

        localStorage.setItem(namespacedKey, value);
      } catch (error) {
        console.error("Error writing to school storage:", error);
      }
    },

    removeItem: (key: string) => {
      try {
        // Remove all namespaced versions of this key
        const pattern = new RegExp(`^[^:]+:${key}$`);
        for (let i = localStorage.length - 1; i >= 0; i--) {
          const storedKey = localStorage.key(i);
          if (storedKey && pattern.test(storedKey)) {
            localStorage.removeItem(storedKey);
          }
        }

        // Also try removing legacy non-namespaced key
        localStorage.removeItem(key);
      } catch (error) {
        console.error("Error removing from school storage:", error);
      }
    },
  };
}
