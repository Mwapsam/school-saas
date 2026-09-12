'use client';

import { Paper, Box, Typography, type PaperOwnProps } from '@mui/material';
import { spacing, radius } from '@/design-system/tokens';

interface SectionCardProps extends Omit<PaperOwnProps, 'component'> {
  /** Section title, displayed as heading */
  title?: React.ReactNode;
  /** Description text below title */
  description?: React.ReactNode;
  /** Right-aligned actions (buttons, menus, etc.) */
  actions?: React.ReactNode;
  /** Content inside the card */
  children: React.ReactNode;
  /** Padding level: "default" (16px) or "card" (20px) */
  padding?: 'default' | 'card';
  /** Opt-in variant for clickable/interactive sections */
  variant?: 'interactive' | 'elevation' | 'outlined';
}

/**
 * SectionCard: Reusable wrapper for grouped content sections.
 *
 * Combines Paper with consistent heading, description, and action layouts.
 * Default padding is spacing.component (16px); use padding="card" (20px) for
 * sections needing more breathing room (e.g. wrapping data tables).
 *
 * Use variant="interactive" only when the entire section is clickable/actionable.
 *
 * Usage:
 *   <SectionCard
 *     title="Personal Information"
 *     description="Basic student details"
 *     padding="default"
 *   >
 *     <TextField label="First Name" />
 *     <TextField label="Last Name" />
 *   </SectionCard>
 *
 *   <SectionCard
 *     title="Invoices"
 *     actions={<Button>Export</Button>}
 *     padding="card"
 *   >
 *     <DataTable columns={columns} rows={invoices} />
 *   </SectionCard>
 *
 *   <SectionCard title="Summary" variant="interactive" component={Link} href="/details">
 *     <Typography>Click to see details</Typography>
 *   </SectionCard>
 */
export function SectionCard({
  title,
  description,
  actions,
  children,
  padding = 'default',
  variant,
  sx,
  ...props
}: SectionCardProps) {
  const paddingValue = padding === 'card' ? spacing.card : spacing.component;

  return (
    <Paper
      variant={variant}
      {...props}
      sx={{
        borderRadius: radius.lg,
        p: paddingValue,
        ...sx,
      }}
    >
      {(title || actions) && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: spacing.component,
            mb: title || description ? spacing.component : 0,
          }}
        >
          <Box sx={{ flex: 1 }}>
            {title && (
              <Typography variant="h3" sx={{ mb: description ? spacing.element : 0 }}>
                {title}
              </Typography>
            )}
            {description && (
              <Typography variant="body2" color="text.secondary">
                {description}
              </Typography>
            )}
          </Box>
          {actions && <Box sx={{ flexShrink: 0 }}>{actions}</Box>}
        </Box>
      )}

      {children}
    </Paper>
  );
}
