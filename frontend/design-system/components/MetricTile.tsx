'use client';

import { Paper, Box, Typography } from '@mui/material';
import { spacing } from '@/design-system/tokens';

interface MetricTileProps {
  /** Large numeric or text value to display prominently */
  value: React.ReactNode;
  /** Descriptive label below the value */
  label: React.ReactNode;
  /** Optional smaller text below label */
  caption?: React.ReactNode;
}

/**
 * MetricTile: A compact card for displaying a single metric/KPI.
 *
 * Used in dashboards, summaries, and attendance/enrollment snapshots
 * to show a single number (or short text) with its label.
 *
 * Usage:
 *   <MetricTile value="24" label="Present Days" />
 *   <MetricTile value="92%" label="Attendance" caption="This term" />
 */
export function MetricTile({ value, label, caption }: MetricTileProps) {
  return (
    <Paper
      sx={{
        p: spacing.component,
        textAlign: 'center',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
      }}
    >
      <Box sx={{ mb: spacing.element }}>
        <Typography variant="h6" component="div" sx={{ fontWeight: 600 }}>
          {value}
        </Typography>
      </Box>

      <Typography variant="caption" color="textSecondary" sx={{ mb: caption ? spacing.element : 0 }}>
        {label}
      </Typography>

      {caption && (
        <Typography variant="caption" color="textSecondary" sx={{ fontSize: '0.7rem' }}>
          {caption}
        </Typography>
      )}
    </Paper>
  );
}
