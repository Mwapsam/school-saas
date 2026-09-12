'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Grid, TextField, Button, CircularProgress, Alert, FormControlLabel, Checkbox, MenuItem } from '@mui/material';
import { step1Schema, type Step1FormData } from '../schemas';
import { useGetAcademicYears, useGetCourses } from '../hooks';

interface Step1FormProps {
  applicationId: string;
  initialData?: any;
  onSubmit: (data: Step1FormData) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onNext?: () => void;
}

export function Step1Form({ applicationId, initialData, onSubmit, isLoading, error, onNext }: Step1FormProps) {
  const { data: academicYearsData } = useGetAcademicYears();
  const { data: coursesData } = useGetCourses();

  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
  } = useForm<Step1FormData>({
    resolver: zodResolver(step1Schema),
    defaultValues: initialData
      ? {
          academic_year: initialData.academic_year?.id || '',
          course_applied: initialData.course_applied?.id || '',
          terms_agreement: initialData.terms_agreement || false,
          preferred_start_date: initialData.preferred_start_date || undefined,
        }
      : undefined,
  });

  const termsAgreed = watch('terms_agreement');

  const handleFormSubmit = async (data: Step1FormData) => {
    try {
      await onSubmit(data);
      onNext?.();
    } catch (err) {
      console.error('Failed to save step 1:', err);
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit(handleFormSubmit)} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Grid container spacing={2}>
        <Grid item xs={12}>
          <TextField
            fullWidth
            select
            label="Academic Year"
            {...register('academic_year')}
            error={!!errors.academic_year}
            helperText={errors.academic_year?.message}
            disabled={isLoading}
          >
            {academicYearsData?.results.map((year) => (
              <MenuItem key={year.id} value={year.id}>
                {year.name}
              </MenuItem>
            ))}
          </TextField>
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            select
            label="Course Applied"
            {...register('course_applied')}
            error={!!errors.course_applied}
            helperText={errors.course_applied?.message}
            disabled={isLoading}
          >
            {coursesData?.results.map((course) => (
              <MenuItem key={course.id} value={course.id}>
                {course.course_name} ({course.code})
              </MenuItem>
            ))}
          </TextField>
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Preferred Start Date"
            type="date"
            {...register('preferred_start_date')}
            error={!!errors.preferred_start_date}
            helperText={errors.preferred_start_date?.message}
            InputLabelProps={{ shrink: true }}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Checkbox
                {...register('terms_agreement')}
                disabled={isLoading}
              />
            }
            label="I agree to the terms and conditions"
          />
          {errors.terms_agreement && (
            <Alert severity="error" sx={{ mt: 1 }}>{errors.terms_agreement.message}</Alert>
          )}
        </Grid>

        <Grid item xs={12}>
          <Button
            type="submit"
            variant="contained"
            disabled={isLoading || !termsAgreed}
            startIcon={isLoading && <CircularProgress size={20} />}
          >
            {isLoading ? 'Saving...' : 'Continue to Step 2'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
