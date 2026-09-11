/**
 * Bootstrap endpoint integration.
 *
 * Fetches tenant configuration once per session:
 * - Tenant branding (name, logo, colors)
 * - User info (name, email, role)
 * - Capabilities (permission strings for UI gating)
 * - Terminology (per-tenant noun customization)
 * - Modules (enabled/disabled product areas)
 */

import { apiClient } from '@/lib/api/client';

export interface TenantBranding {
  id: string;
  name: string;
  code: string;
  logo_url: string;
  primary_color?: string;
  secondary_color?: string;
  footer_quote?: string;
  website?: string;
  phone?: string;
  email?: string;
  address_line1?: string;
  address_line2?: string;
}

export interface UserInfo {
  id: string;
  username: string;
  full_name: string;
  email: string;
}

export interface BootstrapData {
  tenant: TenantBranding;
  user: UserInfo;
  capabilities: string[]; // e.g., ["students.view", "finance.invoices.create", ...]
  terminology: Record<string, string>; // e.g., { "student": "Pupil", "course": "Subject", ... }
  modules: Record<string, boolean>; // e.g., { "finance": true, "library": false, ... }
}

/**
 * Fetch bootstrap data for current tenant/user.
 * Called once per session to populate app state.
 */
export async function fetchBootstrap(): Promise<BootstrapData> {
  try {
    const data = await apiClient.get<BootstrapData>('/bootstrap/');
    return data;
  } catch (error) {
    console.error('Failed to fetch bootstrap:', error);
    throw error;
  }
}

/**
 * Check if a capability is granted (for UI gating only).
 * Backend always enforces every permission regardless of frontend checks.
 */
export function hasCapability(capabilities: string[], capability: string): boolean {
  return capabilities.includes(capability);
}

/**
 * Check if a module is enabled.
 */
export function isModuleEnabled(modules: Record<string, boolean>, module: string): boolean {
  return modules[module] === true;
}

/**
 * Get terminology override for a key, fallback to English.
 */
export function getTerminology(terminology: Record<string, string>, key: string, fallback: string): string {
  return terminology[key] || fallback;
}
