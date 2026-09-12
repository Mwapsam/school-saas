'use client';

import { Chip, type ChipProps } from '@mui/material';
import { colors } from '@/design-system/tokens';

export type StatusType = 'success' | 'warning' | 'error' | 'info' | 'pending' | 'default';

interface StatusBadgeProps extends Omit<ChipProps, 'label' | 'variant'> {
  status: StatusType;
  label?: string;
}

/**
 * Status badge component.
 *
 * Displays a semantic status indicator using the design system's status colors.
 * Used in tables, lists, and detail views to show the state of an item.
 *
 * Usage:
 *   <StatusBadge status="active" label="Active" />
 *   <StatusBadge status="pending" label="Pending" />
 *   <StatusBadge status="error" label="Failed" />
 */
export function StatusBadge({ status, label, ...props }: StatusBadgeProps) {
  const statusConfig: Record<StatusType, { color: string; backgroundColor: string }> = {
    success: {
      color: colors.status.success,
      backgroundColor: colors.status.successLight,
    },
    warning: {
      color: colors.status.warning,
      backgroundColor: colors.status.warningLight,
    },
    error: {
      color: colors.status.error,
      backgroundColor: colors.status.errorLight,
    },
    info: {
      color: colors.status.info,
      backgroundColor: colors.status.infoLight,
    },
    pending: {
      color: colors.status.pending,
      backgroundColor: colors.status.pendingLight,
    },
    default: {
      color: colors.text.secondary,
      backgroundColor: colors.background.default,
    },
  };

  const config = statusConfig[status];

  return (
    <Chip
      label={label || status}
      variant="filled"
      size="small"
      sx={{
        backgroundColor: config.backgroundColor,
        color: config.color,
        fontWeight: 600,
        fontSize: 12,
      }}
      {...props}
    />
  );
}
