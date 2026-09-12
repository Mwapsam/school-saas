'use client';

import { Box, Typography, Button, Stack, Alert } from '@mui/material';
import { AlertTriangle, RotateCw } from 'lucide-react';
import { colors, spacing, typography } from '@/design-system/tokens';

interface ErrorStateProps {
  title?: string;
  description?: string;
  error?: Error | string;
  onRetry?: () => void;
}

/**
 * Error state component.
 *
 * Shown when data loading or processing fails.
 * Provides error details and a retry action.
 *
 * Usage:
 *   {error ? (
 *     <ErrorState
 *       title="Failed to load students"
 *       description="Please try again or contact support."
 *       error={error}
 *       onRetry={() => refetch()}
 *     />
 *   ) : (
 *     <DataTable rows={students} columns={columns} />
 *   )}
 */
export function ErrorState({
  title = 'Something went wrong',
  description = 'An unexpected error occurred while loading this content.',
  error,
  onRetry,
}: ErrorStateProps) {
  const errorMessage =
    typeof error === 'string'
      ? error
      : error?.message || 'Unknown error';

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
      <Box
        sx={{
          mb: spacing.component,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: colors.status.error,
        }}
      >
        <AlertTriangle size={48} />
      </Box>

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

      {/* Error details */}
      {errorMessage && (
        <Alert
          severity="error"
          sx={{
            mb: spacing.section,
            maxWidth: 400,
            textAlign: 'left',
            fontSize: 12,
          }}
        >
          {errorMessage}
        </Alert>
      )}

      {/* Retry button */}
      {onRetry && (
        <Button
          variant="contained"
          startIcon={<RotateCw size={16} />}
          onClick={onRetry}
        >
          Try again
        </Button>
      )}
    </Box>
  );
}
