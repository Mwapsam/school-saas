"use client";

import { useQuery } from "@tanstack/react-query";
import { config } from "@/lib/config";
import {
  SchoolConfig,
  normalizeSchoolConfig,
  getFallbackConfig,
} from "@/lib/school-config-schema";

/**
 * Fetch school configuration from the backend.
 * Called at app startup to load school-specific branding and settings.
 */
async function fetchSchoolConfig(): Promise<SchoolConfig> {
  const url = `${config.apiBaseUrl}/api/school/config/`;

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      // Don't send auth headers — this endpoint is public (called before login)
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch school config: ${response.status}`);
    }

    const data = await response.json();
    return normalizeSchoolConfig(data);
  } catch (error) {
    console.error("Error fetching school config:", error);
    // Return fallback config so the app remains functional
    return getFallbackConfig();
  }
}

/**
 * Hook to access school configuration throughout the app.
 *
 * Usage:
 *   const { data: schoolConfig, isLoading, error } = useSchoolConfig();
 *   return <h1>{schoolConfig.name}</h1>;
 *
 * Features:
 *   - Fetches config on first use
 *   - Cached for 1 hour (stale time) before refetching
 *   - Falls back to generic config if API fails
 *   - Namespaced by school code to support multiple schools in same browser
 */
export function useSchoolConfig() {
  return useQuery<SchoolConfig>({
    queryKey: ["schoolConfig"],
    queryFn: fetchSchoolConfig,
    // Cache for 1 hour before refetching in the background
    staleTime: 60 * 60 * 1000,
    // Keep the last successful response even if refetch fails
    gcTime: 24 * 60 * 60 * 1000, // 24 hours
    // Don't retry infinitely; if it fails, it fails
    retry: 1,
    // Don't throw errors — we have a fallback
    throwOnError: false,
  });
}

/**
 * Utility to get school config synchronously (after it's loaded).
 * Useful for components that need the config before rendering.
 *
 * Warning: This can return undefined if the config hasn't loaded yet.
 * Only use this in components that have access to the query state.
 */
export function useSchoolConfigValue(): SchoolConfig | undefined {
  const { data } = useSchoolConfig();
  return data;
}

/**
 * Get the localStorage key for this school.
 * Allows multiple schools to share a browser without overwriting each other's data.
 */
export function getSchoolStorageKey(schoolCode: string, key: string): string {
  return `${schoolCode}:${key}`;
}
