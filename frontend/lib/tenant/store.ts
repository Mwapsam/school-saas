/**
 * Global tenant state store (Zustand).
 *
 * Holds:
 * - Bootstrap data (branding, user, capabilities, terminology, modules)
 * - Theme (generated from bootstrap colors)
 * - Permission checks
 */

import { create } from 'zustand';
import type { BootstrapData } from './bootstrap';

interface TenantStore {
  bootstrap: BootstrapData | null;
  loading: boolean;
  error: string | null;

  setBootstrap: (data: BootstrapData) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  // Derived helpers
  can: (capability: string) => boolean;
  isModuleEnabled: (module: string) => boolean;
  getTerminology: (key: string, fallback: string) => string;
}

export const useTenantStore = create<TenantStore>((set, get) => ({
  bootstrap: null,
  loading: false,
  error: null,

  setBootstrap: (data) => set({ bootstrap: data, error: null }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),

  can: (capability) => {
    const { bootstrap } = get();
    if (!bootstrap) return false;
    return bootstrap.capabilities.includes(capability);
  },

  isModuleEnabled: (module) => {
    const { bootstrap } = get();
    if (!bootstrap) return false;
    return bootstrap.modules[module] === true;
  },

  getTerminology: (key, fallback) => {
    const { bootstrap } = get();
    if (!bootstrap) return fallback;
    return bootstrap.terminology[key] || fallback;
  },
}));
