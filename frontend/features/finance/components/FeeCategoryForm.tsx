/**
 * Fee category form component for create and edit.
 *
 * Reused for both:
 * - Create new fee category
 * - Edit existing fee category
 */

'use client';

import {
  Box,
  Button,
  TextField,
  CircularProgress,
  Alert,
  Grid,
} from '@mui/material';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { FeeCategory, CreateFeeCategoryInput, UpdateFeeCategoryInput } from '../hooks';
import { feeCategorySchema, FeeCategoryFormValues } from '../schemas';

export interface FeeCategoryFormProps {
  feeCategory?: FeeCategory;
  error?: string | null;
  onSubmit: (data: CreateFeeCategoryInput | UpdateFeeCategoryInput) => Promise<void>;
  onCancel?: () => void;
}

export function FeeCategoryForm({
  feeCategory,
  error,
  onSubmit,
  onCancel,
}: FeeCategoryFormProps) {
  const isCreate = !feeCategory;

  const form = useForm<FeeCategoryFormValues>({
    resolver: zodResolver(feeCategorySchema),
    defaultValues: {
      name: feeCategory?.name || '',
      description: feeCategory?.description || '',
      academic_year: feeCategory?.academic_year || '',
    },
  });

  const { control, formState } = form;
  const { errors, isSubmitting } = formState;

  const submitHandler = form.handleSubmit(async (data) => {
    await onSubmit(data as CreateFeeCategoryInput | UpdateFeeCategoryInput);
  });

  return (
    <Box component="form" onSubmit={submitHandler} sx={{ maxWidth: 600 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        <Grid item xs={12}>
          <Controller
            name="name"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Name"
                required
                disabled={isSubmitting}
                error={!!errors.name}
                helperText={errors.name?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12}>
          <Controller
            name="description"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Description"
                multiline
                rows={3}
                disabled={isSubmitting}
                error={!!errors.description}
                helperText={errors.description?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
          {onCancel && (
            <Button onClick={onCancel} disabled={isSubmitting}>
              Cancel
            </Button>
          )}
          <Button
            type="submit"
            variant="contained"
            disabled={isSubmitting}
            sx={{ minWidth: 120 }}
          >
            {isSubmitting ? <CircularProgress size={24} /> : isCreate ? 'Create' : 'Save'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
