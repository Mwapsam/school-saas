/**
 * Admission application form component for create.
 */

'use client';

import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, TextField, CircularProgress, Alert, Grid } from '@mui/material';
import { CreateAdmissionApplicationInput } from '../hooks';
import { createAdmissionApplicationSchema, CreateAdmissionApplicationFormValues } from '../schemas';

export interface AdmissionFormProps {
  error?: string | null;
  onSubmit: (data: CreateAdmissionApplicationInput) => Promise<void>;
  onCancel?: () => void;
}

export function AdmissionForm({ error, onSubmit, onCancel }: AdmissionFormProps) {
  const {
    control,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<CreateAdmissionApplicationFormValues>({
    resolver: zodResolver(createAdmissionApplicationSchema),
    defaultValues: {
      student_name: '',
      email: '',
      phone: '',
      notes: '',
    },
  });

  const submitting = isSubmitting;

  const onValid = async (data: CreateAdmissionApplicationFormValues) => {
    await onSubmit(data as CreateAdmissionApplicationInput);
  };

  return (
    <Box component="form" onSubmit={handleSubmit(onValid)} sx={{ maxWidth: 600 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        <Grid item xs={12}>
          <Controller
            name="student_name"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Student Name"
                required
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="email"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Email"
                type="email"
                required
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="phone"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Phone"
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12}>
          <Controller
            name="notes"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Notes"
                multiline
                minRows={3}
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
          {onCancel && (
            <Button onClick={onCancel} disabled={submitting}>
              Cancel
            </Button>
          )}
          <Button type="submit" variant="contained" disabled={submitting} sx={{ minWidth: 120 }}>
            {submitting ? <CircularProgress size={24} /> : 'Submit'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
