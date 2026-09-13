import { useSchoolConfig } from "./useSchoolConfig";

/**
 * Hook to access admission-specific config from school settings.
 * Returns empty/false values if school has disabled admissions.
 */
export function useAdmissionConfig() {
  const { data: schoolConfig, ...rest } = useSchoolConfig();

  return {
    ...rest,
    data: schoolConfig
      ? {
          enabled: schoolConfig.admission_enabled ?? false,
          heading:
            schoolConfig.admission_heading ||
            "Apply for a place at our school",
          ctaText:
            schoolConfig.admission_cta_text ||
            "Start Application",
          description:
            schoolConfig.admission_description ||
            "Complete our online form and track your application every step of the way.",
          email: schoolConfig.admission_email || schoolConfig.contact_email,
          schoolName: schoolConfig.name || "School Portal",
          schoolLogo: schoolConfig.logo_url || "/logo.png",
          contactPhone: schoolConfig.contact_phone,
          contactEmail: schoolConfig.contact_email,
        }
      : null,
  };
}
