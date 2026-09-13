/**
 * School configuration schema — returned by GET /api/school/config/
 *
 * This is the runtime configuration for the school, loaded dynamically
 * when the app initializes. It contains branding, feature flags, and
 * contact information that may vary per school.
 *
 * The backend endpoint must be unauthenticated or publicly readable since
 * it's called before the user logs in.
 */

export interface SchoolConfig {
  /** School's official name (e.g., "Pinewood Preparatory School") */
  name: string;

  /** School's short code (e.g., "pinewood") — used for namespacing localStorage */
  code: string;

  /** School's tagline or mission statement (optional) */
  description?: string;

  /** Logo URL — displayed in the brand section of the app shell */
  logo_url?: string;

  /** School's primary brand color (hex, e.g., "#1a7a3c")
   *  Used to generate the accent color throughout the UI */
  primary_color?: string;

  /** School's secondary brand color (hex) — optional */
  secondary_color?: string;

  /** School's official contact email */
  contact_email?: string;

  /** School's official contact phone number */
  contact_phone?: string;

  /** Whether the admission portal is enabled for this school */
  admission_enabled: boolean;

  /** Custom text for the admission portal (if enabled) */
  admission_heading?: string;

  /** Custom admission call-to-action button text */
  admission_cta_text?: string;

  /** Custom text describing the admission process */
  admission_description?: string;

  /** Email address where admission inquiries are sent */
  admission_email?: string;

  /** Website URL (if the school has a public website) */
  website_url?: string;

  /** Social media links (optional) */
  social_links?: {
    twitter?: string;
    facebook?: string;
    instagram?: string;
    linkedin?: string;
  };

  /** Feature flags — which modules/features are enabled for this school */
  features?: {
    parent_portal?: boolean;
    teacher_portal?: boolean;
    librarian_portal?: boolean;
    hr_portal?: boolean;
    admission_portal?: boolean;
    [key: string]: boolean | undefined;
  };
}

/**
 * Validate and normalize school config response from the backend.
 * Returns defaults for missing optional fields.
 */
export function normalizeSchoolConfig(data: unknown): SchoolConfig {
  if (!data || typeof data !== "object") {
    throw new Error("Invalid school config: expected object");
  }

  const config = data as Record<string, unknown>;

  // Required fields
  const name = String(config.name || "").trim();
  if (!name) {
    throw new Error("School config missing required field: name");
  }

  const code = String(config.code || "").trim();
  if (!code) {
    throw new Error("School config missing required field: code");
  }

  // Validate colors if provided
  if (config.primary_color && !isValidHexColor(String(config.primary_color))) {
    throw new Error(`Invalid primary_color: ${config.primary_color}`);
  }

  if (config.secondary_color && !isValidHexColor(String(config.secondary_color))) {
    throw new Error(`Invalid secondary_color: ${config.secondary_color}`);
  }

  return {
    name,
    code,
    description: config.description ? String(config.description) : undefined,
    logo_url: config.logo_url ? String(config.logo_url) : undefined,
    primary_color: config.primary_color ? String(config.primary_color) : undefined,
    secondary_color: config.secondary_color ? String(config.secondary_color) : undefined,
    contact_email: config.contact_email ? String(config.contact_email) : undefined,
    contact_phone: config.contact_phone ? String(config.contact_phone) : undefined,
    admission_enabled: Boolean(config.admission_enabled ?? false),
    admission_heading: config.admission_heading ? String(config.admission_heading) : undefined,
    admission_cta_text: config.admission_cta_text ? String(config.admission_cta_text) : undefined,
    admission_description: config.admission_description ? String(config.admission_description) : undefined,
    admission_email: config.admission_email ? String(config.admission_email) : undefined,
    website_url: config.website_url ? String(config.website_url) : undefined,
    social_links: isValidSocialLinks(config.social_links) ? (config.social_links as SchoolConfig["social_links"]) : undefined,
    features: isValidFeatures(config.features) ? (config.features as SchoolConfig["features"]) : {},
  };
}

function isValidHexColor(color: string): boolean {
  return /^#[0-9a-fA-F]{6}$/.test(color);
}

function isValidSocialLinks(obj: unknown): obj is Record<string, string> {
  if (!obj || typeof obj !== "object") return false;
  const valid = ["twitter", "facebook", "instagram", "linkedin"];
  return Object.keys(obj).every((key) => valid.includes(key));
}

function isValidFeatures(obj: unknown): obj is Record<string, boolean> {
  if (!obj || typeof obj !== "object") return false;
  return Object.values(obj).every((val) => typeof val === "boolean" || val === undefined);
}

/**
 * Safe fallback config when the API is unavailable.
 * Uses generic values that keep the app functional but don't assume
 * any school-specific branding.
 */
export function getFallbackConfig(): SchoolConfig {
  return {
    name: "School Portal",
    code: "unknown",
    description: "School Management System",
    admission_enabled: false,
    features: {
      parent_portal: true,
      teacher_portal: true,
      librarian_portal: true,
      hr_portal: true,
      admission_portal: false,
    },
  };
}
