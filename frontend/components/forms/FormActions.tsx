'use client';

import { Box, Button, Stack } from '@mui/material';
import { spacing } from '@/design-system/tokens';

interface FormActionsProps {
  onCancel?: () => void;
  submitLabel?: string;
  cancelLabel?: string;
  isSubmitting?: boolean;
  isDirty?: boolean;
}

/**
 * Form actions component.
 *
 * Renders a consistent set of action buttons (Save/Cancel) at the bottom of forms.
 * Automatically disables submit button when form is not dirty or is submitting.
 *
 * Usage:
 *   <Form onSubmit={onSubmit}>
 *     <FormSection title="Basic Information">
 *       <TextField name="firstName" label="First Name" />
 *     </FormSection>
 *
 *     <FormActions
 *       onCancel={() => navigate('/students')}
 *       isSubmitting={isSubmitting}
 *       isDirty={isDirty}
 *     />
 *   </Form>
 */
export function FormActions({
  onCancel,
  submitLabel = 'Save',
  cancelLabel = 'Cancel',
  isSubmitting = false,
  isDirty = true,
}: FormActionsProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'flex-end',
        gap: spacing.element,
        mt: spacing.section,
        pt: spacing.section,
        borderTop: `1px solid rgba(0, 0, 0, 0.08)`,
      }}
    >
      {/* Cancel button */}
      {onCancel && (
        <Button
          variant="outlined"
          onClick={onCancel}
          disabled={isSubmitting}
        >
          {cancelLabel}
        </Button>
      )}

      {/* Submit button */}
      <Button
        type="submit"
        variant="contained"
        disabled={isSubmitting || !isDirty}
      >
        {submitLabel}
      </Button>
    </Box>
  );
}
