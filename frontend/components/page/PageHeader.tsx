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
        direction="row"
        justifyContent="space-between"
        alignItems="flex-start"
        spacing={spacing.component}
        sx={{ mb: description ? spacing.element : 0 }}
      >
        <Box>
          <Typography
            variant="h1"
            component="h1"
            sx={{
              fontSize: typography.h1.fontSize,
              lineHeight: typography.h1.lineHeight / typography.h1.fontSize,
              fontWeight: typography.h1.fontWeight,
              mb: 0,
            }}
          >
            {title}
          </Typography>
        </Box>

        {/* Actions - typically buttons */}
        {actions && (
          <Box sx={{ display: 'flex', gap: spacing.element }}>
            {actions}
          </Box>
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
