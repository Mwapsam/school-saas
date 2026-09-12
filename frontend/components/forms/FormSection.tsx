'use client';

import { Box, Typography, Stack, type StackProps } from '@mui/material';
import { spacing, typography, colors } from '@/design-system/tokens';

interface FormSectionProps extends Omit<StackProps, 'children'> {
  /** Section heading */
  title?: string;
  /** Section description */
  description?: string;
  /** Form fields */
  children: React.ReactNode;
}

/**
 * Form section component.
 *
 * Groups related form fields with an optional heading and description.
 * Provides consistent spacing and visual hierarchy within forms.
 *
 * Usage:
 *   <Form onSubmit={onSubmit}>
 *     <FormSection title="Basic Information" description="Student name and date of birth.">
 *       <TextField name="firstName" label="First Name" />
 *       <TextField name="lastName" label="Last Name" />
 *       <TextField name="dateOfBirth" label="Date of Birth" type="date" />
 *     </FormSection>
 *
 *     <FormSection title="Enrollment">
 *       <Select name="class" label="Class" />
 *     </FormSection>
 *
 *     <FormActions />
 *   </Form>
 */
export function FormSection({
  title,
  description,
  children,
  ...stackProps
}: FormSectionProps) {
  return (
    <Box
      sx={{
        mb: spacing.section,
        pb: spacing.section,
        borderBottom: `1px solid ${colors.border.light}`,

        '&:last-of-type': {
          borderBottom: 'none',
        },
      }}
    >
      {/* Heading */}
      {title && (
        <Box sx={{ mb: spacing.component }}>
          <Typography
            variant="h5"
            sx={{
              fontSize: typography.h3.fontSize,
              lineHeight: typography.h3.lineHeight / typography.h3.fontSize,
              fontWeight: 650,
              color: colors.text.primary,
              mb: description ? spacing.element / 4 : 0,
            }}
          >
            {title}
          </Typography>

          {/* Description */}
          {description && (
            <Typography
              variant="body2"
              sx={{
                fontSize: typography.bodySmall.fontSize,
                lineHeight: typography.bodySmall.lineHeight / typography.bodySmall.fontSize,
                color: colors.text.secondary,
              }}
            >
              {description}
            </Typography>
          )}
        </Box>
      )}

      {/* Fields */}
      <Stack spacing={spacing.component / 4} {...stackProps}>
        {children}
      </Stack>
    </Box>
  );
}
