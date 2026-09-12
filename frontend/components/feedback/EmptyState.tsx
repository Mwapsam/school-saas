'use client';

import { Box, Typography, Button, Stack } from '@mui/material';
import { colors, spacing, typography } from '@/design-system/tokens';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

/**
 * Empty state component.
 *
 * Rendered when a table, list, or content area has no data.
 * Provides a friendly, actionable empty state rather than a blank screen.
 *
 * Usage:
 *   {students.length === 0 ? (
 *     <EmptyState
 *       title="No students yet"
 *       description="Get started by adding your first student."
 *       action={{
 *         label: 'Add Student',
 *         onClick: () => navigate('/students/create'),
 *       }}
 *     />
 *   ) : (
 *     <DataTable rows={students} columns={columns} />
 *   )}
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        py: spacing.section,
        px: spacing.component,
        textAlign: 'center',
        minHeight: 300,
      }}
    >
      {/* Icon */}
      {icon && (
        <Box
          sx={{
            mb: spacing.component,
            opacity: 0.5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {icon}
        </Box>
      )}

      {/* Title */}
      <Typography
        variant="h3"
        sx={{
          fontSize: typography.h3.fontSize,
          lineHeight: typography.h3.lineHeight / typography.h3.fontSize,
          fontWeight: typography.h3.fontWeight,
          mb: spacing.element,
          color: colors.text.primary,
        }}
      >
        {title}
      </Typography>

      {/* Description */}
      {description && (
        <Typography
          variant="body2"
          sx={{
            color: colors.text.secondary,
            mb: spacing.section,
            maxWidth: 400,
            fontSize: typography.body.fontSize,
            lineHeight: typography.body.lineHeight / typography.body.fontSize,
          }}
        >
          {description}
        </Typography>
      )}

      {/* Action button */}
      {action && (
        <Button
          variant="contained"
          onClick={action.onClick}
        >
          {action.label}
        </Button>
      )}
    </Box>
  );
}
