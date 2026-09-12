'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Grid, TextField, Button, CircularProgress, Alert, MenuItem } from '@mui/material';
import { step2Schema, type Step2FormData } from '../schemas';
import { useGetAcademicYears, useGetCourses } from '../hooks';

interface Step2FormProps {
  applicationId: string;
  initialData?: any;
  onSubmit: (data: Step2FormData) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onNext?: () => void;
}

export function Step2Form({ applicationId, initialData, onSubmit, isLoading, error, onNext }: Step2FormProps) {
  const { data: academicYearsData } = useGetAcademicYears();
  const { data: coursesData } = useGetCourses();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Step2FormData>({
    resolver: zodResolver(step2Schema),
    defaultValues: initialData
      ? {
          academic_year: initialData.academic_year?.id || '',
          course_applied: initialData.course_applied?.id || '',
        }
      : undefined,
  });

  const handleFormSubmit = async (data: Step2FormData) => {
    try {
      await onSubmit(data);
      onNext?.();
    } catch (err) {
      console.error('Failed to save step 2:', err);
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
            label="Academic Year *"
            {...register('academic_year')}
            error={!!errors.academic_year}
            helperText={errors.academic_year?.message}
            disabled={isLoading}
            required
          >
            {academicYearsData?.map((year) => (
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
            label="Course Applied *"
            {...register('course_applied')}
            error={!!errors.course_applied}
            helperText={errors.course_applied?.message}
            disabled={isLoading}
            required
          >
            {coursesData?.map((course) => (
              <MenuItem key={course.id} value={course.id}>
                {course.course_name} ({course.code})
              </MenuItem>
            ))}
          </TextField>
        </Grid>

        <Grid item xs={12}>
          <Button
            type="submit"
            variant="contained"
            disabled={isLoading || !!errors.academic_year || !!errors.course_applied}
            startIcon={isLoading && <CircularProgress size={20} />}
          >
            {isLoading ? 'Saving...' : 'Continue to Step 3'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
