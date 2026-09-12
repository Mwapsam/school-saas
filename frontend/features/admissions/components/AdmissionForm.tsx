/**
 * Admission application form component for create.
 */

'use client';

import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, TextField, CircularProgress, Alert, Grid, MenuItem } from '@mui/material';
import { CreateAdmissionApplicationInput, useCourseOptions } from '../hooks';
import { createAdmissionApplicationSchema, CreateAdmissionApplicationFormValues } from '../schemas';

export interface AdmissionFormProps {
  error?: string | null;
  onSubmit: (data: CreateAdmissionApplicationInput) => Promise<void>;
  onCancel?: () => void;
}

export function AdmissionForm({ error, onSubmit, onCancel }: AdmissionFormProps) {
  const { data: courseOptions } = useCourseOptions();
  const {
    control,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<CreateAdmissionApplicationFormValues>({
    resolver: zodResolver(createAdmissionApplicationSchema),
    defaultValues: {
      first_name: '',
      middle_name: '',
      last_name: '',
      date_of_birth: '',
      gender: 'male',
      course_applied: '',
      guardian_name: '',
      guardian_phone: '',
      guardian_email: '',
      address: '',
      remarks: '',
    },
  });

  const submitting = isSubmitting;

  const onValid = async (data: CreateAdmissionApplicationFormValues) => {
    await onSubmit(data as CreateAdmissionApplicationInput);
  };

  return (
    <Box component="form" onSubmit={handleSubmit(onValid)} sx={{ maxWidth: 700 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        <Grid item xs={12} sm={4}>
          <Controller
            name="first_name"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="First Name"
                required
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={4}>
          <Controller
            name="middle_name"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Middle Name"
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={4}>
          <Controller
            name="last_name"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Last Name"
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
            name="date_of_birth"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Date of Birth"
                type="date"
                required
                InputLabelProps={{ shrink: true }}
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="gender"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                select
                fullWidth
                label="Gender"
                required
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              >
                <MenuItem value="male">Male</MenuItem>
                <MenuItem value="female">Female</MenuItem>
                <MenuItem value="other">Other</MenuItem>
              </TextField>
            )}
          />
        </Grid>

        <Grid item xs={12}>
          <Controller
            name="course_applied"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                select
                fullWidth
                label="Course Applied For"
                required
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              >
                {(courseOptions?.results ?? []).map((course) => (
                  <MenuItem key={course.id} value={course.id}>
                    {course.course_name}
                  </MenuItem>
                ))}
              </TextField>
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="guardian_name"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Guardian Name"
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
            name="guardian_phone"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Guardian Phone"
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
            name="guardian_email"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Guardian Email"
                type="email"
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12}>
          <Controller
            name="address"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Address"
                required
                multiline
                minRows={2}
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12}>
          <Controller
            name="remarks"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Remarks"
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
