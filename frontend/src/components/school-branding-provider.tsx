"use client";

import { useEffect } from "react";
import { useSchoolConfig } from "@/hooks/useSchoolConfig";
import { useAuthStore } from "@/lib/auth-store";

/**
 * SchoolBrandingProvider injects school-specific branding into the app.
 *
 * It:
 * - Fetches school config from the backend
 * - Injects CSS variables for school colors (--school-primary, --school-secondary)
 * - Updates the page title to include school name
 * - Stores the school code in auth state for multi-tenant support
 */
export function SchoolBrandingProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: schoolConfig, isLoading, error } = useSchoolConfig();
  const setSchoolCode = useAuthStore((s) => s.setSchoolCode);

  useEffect(() => {
    if (!schoolConfig) return;

    // Update school code in auth store for multi-tenant localStorage namespacing
    if (schoolConfig.code) {
      setSchoolCode(schoolConfig.code);
    }

    // Inject CSS variables for school colors
    const root = document.documentElement;
    if (schoolConfig.primary_color) {
      root.style.setProperty("--school-primary", schoolConfig.primary_color);
    }
    if (schoolConfig.secondary_color) {
      root.style.setProperty(
        "--school-secondary",
        schoolConfig.secondary_color
      );
    }

    // Update page title to include school name (runtime, after hydration)
    // Note: Static metadata is set in layout.tsx; this updates the title dynamically
    const baseTitle = schoolConfig.name || "School Portal";
    document.title = baseTitle;
  }, [schoolConfig, setSchoolCode]);

  return <>{children}</>;
}
