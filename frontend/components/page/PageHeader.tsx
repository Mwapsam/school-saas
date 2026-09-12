'use client';

import { Box, Typography, Stack } from '@mui/material';
import { spacing, typography } from '@/design-system/tokens';

interface PageHeaderProps {
  /** Page title */
  title: string;
  /** Optional page description */
  description?: string;
  /** Optional right-side actions (typically buttons) */
  actions?: React.ReactNode;
  /** Optional breadcrumbs */
  breadcrumbs?: React.ReactNode;
}

/**
 * Page header component.
 *
 * Renders a consistent page title, optional description, and actions.
 * Replaces the copy-pasted header pattern found across all module pages.
 *
 * Usage:
 *   <PageHeader
 *     title="Students"
 *     description="Manage students enrolled at your school."
 *     actions={<Button>Add Student</Button>}
 *   />
 */
export function PageHeader({
  title,
  description,
  actions,
  breadcrumbs,
}: PageHeaderProps) {
  return (
    <Box sx={{ mb: spacing.section }}>
      {/* Breadcrumbs */}
      {breadcrumbs && (
        <Box sx={{ mb: spacing.component }}>
          {breadcrumbs}
        </Box>
      )}

      {/* Title and actions row */}
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', sm: 'center' }}
        gap={2}
        sx={{ mb: description ? spacing.element : 0 }}
      >
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography
            variant="h1"
            component="h1"
            sx={{
              fontSize: typography.h1.fontSize,
              lineHeight: typography.h1.lineHeight,
              fontWeight: typography.h1.fontWeight,
              mb: 0,
              overflowWrap: 'anywhere',
            }}
          >
            {title}
          </Typography>
        </Box>

        {/* Actions - typically buttons */}
        {actions && (
          <Stack direction="row" gap={1} flexWrap="wrap" sx={{ width: { xs: '100%', sm: 'auto' } }}>
            {actions}
          </Stack>
        )}
      </Stack>

      {/* Description */}
      {description && (
        <Typography
          variant="body2"
          sx={{
            color: 'text.secondary',
            fontSize: typography.body.fontSize,
            lineHeight: typography.body.lineHeight / typography.body.fontSize,
          }}
        >
          {description}
        </Typography>
      )}
    </Box>
  );
}
