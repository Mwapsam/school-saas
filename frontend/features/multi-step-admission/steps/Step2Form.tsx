'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, TextField, Alert, MenuItem } from '@mui/material';
import { step2Schema, type Step2FormData } from '../schemas';
import { useGetAcademicYears, useGetCourses } from '../hooks';
import { FormSection, FormActions, FormGrid } from '@/components/forms';

interface Step2FormProps {
  initialData?: any;
  onSubmit: (data: Step2FormData) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onNext?: () => void;
}

export function Step2Form({ initialData, onSubmit, isLoading, error, onNext }: Step2FormProps) {
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

  const computedValidity = !errors.academic_year && !errors.course_applied;

  return (
    <Box component="form" onSubmit={handleSubmit(handleFormSubmit)} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <FormSection title="Academic & Admission Details">
        <FormGrid columns={1}>
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
        </FormGrid>
      </FormSection>

      <FormActions
        submitLabel="Continue to Step 3"
        isSubmitting={isLoading}
        isDirty={computedValidity}
      />
    </Box>
  );
}
