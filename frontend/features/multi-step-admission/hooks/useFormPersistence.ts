import { useEffect, useCallback, useRef } from 'react';
import { UseFormSetValue, UseFormGetValues } from 'react-hook-form';

const STORAGE_KEY_PREFIX = 'admission_form_step_';

/**
 * Hook to persist form data to localStorage
 * Saves form data as user types and restores on page reload
 */
export function useFormPersistence<T extends Record<string, any>>(
  applicationId: string,
  stepNumber: number,
  setValue: UseFormSetValue<T>,
  getValues: UseFormGetValues<T>,
) {
  const storageKey = `${STORAGE_KEY_PREFIX}${applicationId}_step_${stepNumber}`;
  const timeoutRef = useRef<NodeJS.Timeout>();
  const hasRestoredRef = useRef(false);

  // Restore from localStorage on mount (only once)
  useEffect(() => {
    if (hasRestoredRef.current) {
      console.log(`[Step ${stepNumber}] Skipping restore (already restored once)`);
      return;
    }
    hasRestoredRef.current = true;

    try {
      console.log(`[Step ${stepNumber}] Attempting to restore from localStorage (key: ${storageKey})`);
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const data = JSON.parse(saved);
        console.log(`✓ Restored Step ${stepNumber} data:`, data);
        let fieldsRestored = 0;
        Object.entries(data).forEach(([key, value]) => {
          setValue(key as keyof T, value as any, { shouldValidate: true });
          fieldsRestored++;
        });
        console.log(`✓ Restored ${fieldsRestored} fields for Step ${stepNumber}`);
      } else {
        console.log(`[Step ${stepNumber}] No saved data found in localStorage`);
      }
    } catch (error: any) {
      console.error(`✗ Failed to restore Step ${stepNumber} form data:`, {
        error: error.message,
        name: error.name,
        storageKey,
      });
      // Clear invalid data from storage
      try {
        localStorage.removeItem(storageKey);
        console.log(`[Step ${stepNumber}] Cleared invalid data from localStorage`);
      } catch (e) {
        console.error(`[Step ${stepNumber}] Failed to clear invalid data:`, e);
      }
    }
  }, [storageKey, stepNumber, setValue]);

  // Debounced auto-save to localStorage
  const saveToLocalStorage = useCallback(() => {
    // Clear previous timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Set new timeout - save after 500ms of inactivity
    timeoutRef.current = setTimeout(() => {
      try {
        const data = getValues();
        console.log(`[Step ${stepNumber}] About to save data:`, data);
        const serialized = JSON.stringify(data);
        console.log(`[Step ${stepNumber}] Serialized size:`, serialized.length, 'bytes');
        localStorage.setItem(storageKey, serialized);
        console.log(`✓ Saved Step ${stepNumber} data to localStorage (key: ${storageKey})`);
      } catch (error: any) {
        console.error(`✗ Failed to save Step ${stepNumber} form data:`, {
          error: error.message,
          name: error.name,
          storageKey,
          localStorage_available: typeof localStorage !== 'undefined',
        });
      }
    }, 500);
  }, [getValues, storageKey, stepNumber]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // Clear localStorage after successful submission
  const clearPersistence = useCallback(() => {
    try {
      localStorage.removeItem(storageKey);
      console.log(`✓ Cleared Step ${stepNumber} localStorage data (key: ${storageKey})`);
    } catch (error: any) {
      console.error(`✗ Failed to clear Step ${stepNumber} form data:`, {
        error: error.message,
        storageKey,
      });
    }
  }, [storageKey, stepNumber]);

  return { saveToLocalStorage, clearPersistence };
}

/**
 * Clear all persisted form data for an application
 */
export function clearApplicationFormData(applicationId: string) {
  try {
    for (let i = 1; i <= 8; i++) {
      const key = `${STORAGE_KEY_PREFIX}${applicationId}_step_${i}`;
      localStorage.removeItem(key);
    }
  } catch (error) {
    console.error('Failed to clear application form data:', error);
  }
}
