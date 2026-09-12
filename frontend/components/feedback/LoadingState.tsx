'use client';

import { Box, CircularProgress, Typography, Skeleton, Stack } from '@mui/material';
import { colors, spacing, typography } from '@/design-system/tokens';

interface LoadingStateProps {
  /** Type of loading state to show */
  variant?: 'spinner' | 'skeleton';
  /** Optional message while loading */
  message?: string;
  /** Minimum height of the container */
  minHeight?: number;
}

/**
 * Loading state component.
 *
 * Shown while data is being fetched or processed.
 * Supports two variants: spinner (for full-page loads) and skeleton (for inline content).
 *
 * Usage:
 *   {loading ? (
 *     <LoadingState message="Loading students..." />
 *   ) : (
 *     <DataTable rows={students} columns={columns} />
 *   )}
 */
export function LoadingState({
  variant = 'spinner',
  message,
  minHeight = 300,
}: LoadingStateProps) {
  if (variant === 'skeleton') {
    return (
      <Stack spacing={spacing.component / 4}>
        <Skeleton variant="text" height={40} />
        <Skeleton variant="rectangular" height={300} />
        <Skeleton variant="text" height={24} />
      </Stack>
    );
  }

  // spinner variant (default)
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight,
        gap: spacing.component,
      }}
    >
      <CircularProgress />

      {message && (
        <Typography
          variant="body2"
          sx={{
            color: colors.text.secondary,
            fontSize: typography.body.fontSize,
            lineHeight: typography.body.lineHeight / typography.body.fontSize,
          }}
        >
          {message}
        </Typography>
      )}
    </Box>
  );
}
