'use client';

import { Box, Typography, Tooltip, type BoxProps } from '@mui/material';
import { spacing } from '@/design-system/tokens';

interface DetailFieldProps extends Omit<BoxProps, 'children'> {
  /** Label text displayed in the left column */
  label: React.ReactNode;
  /** Value content displayed in the right column */
  value: React.ReactNode;
  /** Width of the label column (default: '120px') */
  labelWidth?: string | number;
  /** Enable text truncation with tooltip on hover */
  truncate?: boolean;
  /** Custom spacing between label and value (default: spacing.component = 16px) */
  gap?: number | string;
}

/**
 * DetailField: Read-only label-value row for detail pages.
 *
 * Renders a consistent label + value layout across all detail pages.
 * Replaces the hand-rolled `gridTemplateColumns: '150px 1fr'` pattern.
 *
 * Default behavior: label wraps freely, value wraps freely.
 * With `truncate`: value truncates with ellipsis, full text in tooltip on hover.
 *
 * Usage:
 *   <DetailField label="Email" value={student.email} truncate />
 *   <DetailField label="Phone" value={student.phone || '-'} />
 *   <DetailField label="Date" value={formatDate(student.created)} labelWidth="100px" />
 */
export function DetailField({
  label,
  value,
  labelWidth = '120px',
  truncate = false,
  gap = spacing.component,
  sx,
  ...props
}: DetailFieldProps) {
  const displayValue = value || '-';
  const valueText = typeof displayValue === 'string' ? displayValue : null;

  const valueElement = (
    <Typography
      variant="body2"
      sx={{
        flex: 1,
        ...(truncate && {
          textOverflow: 'ellipsis',
          overflow: 'hidden',
          whiteSpace: 'nowrap',
        }),
      }}
    >
      {displayValue}
    </Typography>
  );

  return (
    <Box
      sx={{
        display: 'flex',
        gap,
        py: spacing.element,
        ...sx,
      }}
      {...props}
    >
      <Typography
        variant="body2"
        sx={{
          fontWeight: 500,
          color: 'text.secondary',
          width: labelWidth,
          flexShrink: 0,
        }}
      >
        {label}
      </Typography>

      {truncate && valueText ? (
        <Tooltip title={valueText} arrow>
          {valueElement}
        </Tooltip>
      ) : (
        valueElement
      )}
    </Box>
  );
}
