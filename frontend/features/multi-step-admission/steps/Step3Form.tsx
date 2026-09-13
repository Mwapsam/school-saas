'use client';

import { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, TextField, Alert, MenuItem } from '@mui/material';
import { step3Schema, type Step3FormData } from '../schemas';
import { useFormPersistence } from '../hooks/useFormPersistence';
import { FormSection, FormActions, FormGrid, FileUploadField } from '@/components/forms';

interface Step3FormProps {
  applicationId: string;
  initialData?: any;
  onSubmit: (data: Step3FormData) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onNext?: () => void;
}

export function Step3Form({ applicationId, initialData, onSubmit, isLoading, error, onNext }: Step3FormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
    watch,
    control,
    setValue,
    getValues,
  } = useForm<Step3FormData>({
    resolver: zodResolver(step3Schema),
    mode: 'onChange',
    defaultValues: initialData || undefined,
  });

  const { saveToLocalStorage, clearPersistence } = useFormPersistence(applicationId, 3, setValue, getValues);

  useEffect(() => {
    const subscription = watch(() => {
      saveToLocalStorage();
    });
    return () => subscription.unsubscribe();
  }, [watch, saveToLocalStorage]);

  const hasMedicalProblems = watch('has_medical_problems');
  const hasHospitalization = watch('recent_hospitalization');
  const hasAllergies = watch('has_allergies');

  const handleFormSubmit = async (data: Step3FormData) => {
    try {
      await onSubmit(data);
      clearPersistence();
    } catch (err) {
      console.error('Failed to save step 3:', err);
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit(handleFormSubmit)} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <FormSection title="Child's Name">
        <FormGrid>
          <TextField
            fullWidth
            label="First Name *"
            {...register('first_name')}
            error={!!errors.first_name}
            helperText={errors.first_name?.message}
            disabled={isLoading}
            required
          />

          <TextField
            fullWidth
            label="Middle Name"
            {...register('middle_name')}
            disabled={isLoading}
          />

          <TextField
            fullWidth
            label="Last Name *"
            {...register('last_name')}
            error={!!errors.last_name}
            helperText={errors.last_name?.message}
            disabled={isLoading}
            required
          />
        </FormGrid>
      </FormSection>

      <FormSection title="Basic Information">
        <FormGrid>
          <TextField
            fullWidth
            label="Date of Birth *"
            type="date"
            {...register('date_of_birth')}
            error={!!errors.date_of_birth}
            helperText={errors.date_of_birth?.message}
            InputLabelProps={{ shrink: true }}
            disabled={isLoading}
            required
          />

          <TextField
            fullWidth
            select
            label="Gender *"
            {...register('gender')}
            error={!!errors.gender}
            helperText={errors.gender?.message}
            disabled={isLoading}
            required
          >
            <MenuItem value="male">Male</MenuItem>
            <MenuItem value="female">Female</MenuItem>
            <MenuItem value="other">Other</MenuItem>
          </TextField>

          <TextField
            fullWidth
            label="Nationality *"
            {...register('nationality')}
            error={!!errors.nationality}
            helperText={errors.nationality?.message}
            disabled={isLoading}
            required
          />

          <TextField
            fullWidth
            label="Religion"
            {...register('religion')}
            disabled={isLoading}
          />

          <TextField
            fullWidth
            label="Birth Place"
            {...register('birth_place')}
            disabled={isLoading}
          />
        </FormGrid>
      </FormSection>

      <FormSection title="School-Specific Information">
        <FormGrid>
          <TextField
            fullWidth
            label="Preferred Name"
            {...register('preferred_name')}
            disabled={isLoading}
          />

          <TextField
            fullWidth
            label="Home Language"
            {...register('home_language')}
            disabled={isLoading}
          />
        </FormGrid>
      </FormSection>

      <FormSection title="Contact & Pickup Information">
        <FormGrid>
          <TextField
            fullWidth
            label="Email"
            type="email"
            {...register('email')}
            error={!!errors.email}
            helperText={errors.email?.message}
            disabled={isLoading}
          />

          <Box sx={{ gridColumn: { md: '1 / -1' } }}>
            <TextField
              fullWidth
              label="Authorized Pickup Persons"
              multiline
              rows={2}
              {...register('authorized_pickup_persons')}
              disabled={isLoading}
              helperText="Please notify us immediately of any changes"
            />
          </Box>

          <Box sx={{ gridColumn: { md: '1 / -1' } }}>
            <Controller
              name="student_photo"
              control={control}
              render={({ field: { value, onChange } }) => (
                <FileUploadField
                  label="Student Photo"
                  accept="image/*"
                  onChange={onChange}
                  value={value}
                  disabled={isLoading}
                  error={!!errors.student_photo}
                  helperText={errors.student_photo?.message}
                />
              )}
            />
          </Box>
        </FormGrid>
      </FormSection>

      <FormSection title="Health Information">
        <FormGrid columns={1}>
          <TextField
            fullWidth
            label="Any ongoing medical problems?"
            select
            {...register('has_medical_problems')}
            disabled={isLoading}
          >
            <MenuItem value="">-- Select --</MenuItem>
            <MenuItem value="yes">Yes</MenuItem>
            <MenuItem value="no">No</MenuItem>
          </TextField>

          <TextField
            fullWidth
            label="Been in hospital recently?"
            select
            {...register('recent_hospitalization')}
            disabled={isLoading}
          >
            <MenuItem value="">-- Select --</MenuItem>
            <MenuItem value="yes">Yes</MenuItem>
            <MenuItem value="no">No</MenuItem>
          </TextField>

          <TextField
            fullWidth
            label="Any allergies?"
            select
            {...register('has_allergies')}
            disabled={isLoading}
          >
            <MenuItem value="">-- Select --</MenuItem>
            <MenuItem value="yes">Yes</MenuItem>
            <MenuItem value="no">No</MenuItem>
          </TextField>

          {(hasMedicalProblems || hasHospitalization || hasAllergies) && (
            <TextField
              fullWidth
              label="Medical Details *"
              multiline
              rows={2}
              {...register('medical_details')}
              error={!!errors.medical_details}
              helperText={errors.medical_details?.message || 'Please provide details'}
              disabled={isLoading}
              required
            />
          )}
        </FormGrid>
      </FormSection>

      <FormActions
        submitLabel="Continue to Step 4"
        isSubmitting={isLoading}
        isDirty={isValid}
      />
    </Box>
  );
}
