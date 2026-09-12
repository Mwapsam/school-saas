'use client';

import { Box } from '@mui/material';
import type { ReactNode } from 'react';
import { spacing } from '@/design-system/tokens';

interface FormGridProps {
  /** Number of columns on desktop (md breakpoint). Collapses to 1 on mobile. */
  columns?: number;
  children: ReactNode;
}

/**
 * Responsive CSS-grid wrapper for form field layouts.
 *
 * Used only for field-input layouts (TextFields, selects, radios, checkboxes).
 * Complex controls such as lists, tables, document upload rows, and status
 * displays should keep their native MUI layout (List, Table, custom rows).
 *
 * To span a field across both columns on desktop:
 *   Box sx={{ gridColumn: { md: '1 / -1' } }} with the field inside
 *
 * @param columns - Number of columns on desktop (default 2). Collapses to 1 on mobile.
 */
export function FormGrid({ columns = 2, children }: FormGridProps) {
  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: {
          xs: '1fr',
          md: `repeat(${columns}, minmax(0, 1fr))`,
        },
        gap: spacing.element,
      }}
    >
      {children}
    </Box>
  );
}
