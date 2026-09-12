'use client';

import { Box, Typography } from '@mui/material';
import type { ReactNode } from 'react';

interface FormFieldProps {
  /** Field label (displayed above the control). */
  label: string;
  /** Optional hint text (displayed between label and control). */
  hint?: string;
  /** Error message (displayed below the control in error color). */
  error?: string;
  /** Whether the field is required (adds ' *' to label). */
  required?: boolean;
  /** The input control (RadioGroup, CheckboxGroup, file input, etc.). */
  children: ReactNode;
}

/**
 * Label/hint/error wrapper for non-TextField form controls.
 *
 * Used for RadioGroup, CheckboxGroup, file inputs, and other custom controls
 * where MUI's built-in label slot (TextField) isn't available.
 *
 * For plain TextFields, use MUI's built-in label/helperText/error props instead
 * to avoid redundant wrapping.
 *
 * FormField is presentation-only. React Hook Form / Zod determines validity;
 * this component only displays the error string it's handed.
 */
export function FormField({
  label,
  hint,
  error,
  required,
  children,
}: FormFieldProps) {
  return (
    <Box>
      <Typography
        component="div"
        variant="body2"
        sx={{
          fontWeight: 600,
          mb: 0.75,
        }}
      >
        {label}
        {required && ' *'}
      </Typography>

      {hint && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mb: 1 }}
        >
          {hint}
        </Typography>
      )}

      {children}

      {error && (
        <Typography
          variant="caption"
          color="error"
          sx={{ display: 'block', mt: 0.5 }}
        >
          {error}
        </Typography>
      )}
    </Box>
  );
}
