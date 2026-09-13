'use client';

import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, TextField, Alert } from '@mui/material';
import { step5Schema, type Step5FormData } from '../schemas';
import { useFormPersistence } from '../hooks/useFormPersistence';
import { FormSection, FormActions, FormGrid } from '@/components/forms';

interface Step5FormProps {
  applicationId: string;
  initialData?: any;
  onSubmit: (data: Step5FormData) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onNext?: () => void;
}

export function Step5Form({ applicationId, initialData, onSubmit, isLoading, error, onNext }: Step5FormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
    watch,
    setValue,
    getValues,
  } = useForm<Step5FormData>({
    resolver: zodResolver(step5Schema),
    mode: 'onChange',
    defaultValues: initialData || undefined,
  });

  const { saveToLocalStorage, clearPersistence } = useFormPersistence(applicationId, 5, setValue, getValues);

  useEffect(() => {
    const subscription = watch(() => {
      saveToLocalStorage();
    });
    return () => subscription.unsubscribe();
  }, [watch, saveToLocalStorage]);

  const handleFormSubmit = async (data: Step5FormData) => {
    try {
      await onSubmit(data);
      clearPersistence();
    } catch (err) {
      console.error('Failed to save step 5:', err);
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit(handleFormSubmit)} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <FormSection title="Guardian 2 (Optional)">
        <FormGrid>
          <TextField
            fullWidth
            label="First Name"
            {...register('guardian2_first_name')}
            disabled={isLoading}
          />

          <TextField
            fullWidth
            label="Last Name"
            {...register('guardian2_last_name')}
            disabled={isLoading}
          />

          <TextField
            fullWidth
            label="Relationship to Child"
            {...register('guardian2_relation')}
            disabled={isLoading}
          />

          <TextField
            fullWidth
            label="Mobile Phone"
            {...register('guardian2_mobile')}
            disabled={isLoading}
          />

          <Box sx={{ gridColumn: { md: '1 / -1' } }}>
            <TextField
              fullWidth
              label="Email"
              type="email"
              {...register('guardian2_email')}
              error={!!errors.guardian2_email}
              helperText={errors.guardian2_email?.message}
              disabled={isLoading}
            />
          </Box>

          <TextField
            fullWidth
            label="Occupation"
            {...register('guardian2_occupation')}
            disabled={isLoading}
          />

          <TextField
            fullWidth
            label="Office Phone"
            {...register('guardian2_office_phone1')}
            disabled={isLoading}
          />

          <Box sx={{ gridColumn: { md: '1 / -1' } }}>
            <TextField
              fullWidth
              label="Office Address"
              {...register('guardian2_office_address_line1')}
              disabled={isLoading}
            />
          </Box>

          <TextField
            fullWidth
            label="City"
            {...register('guardian2_city')}
            disabled={isLoading}
          />
        </FormGrid>
      </FormSection>

      <FormSection title="Emergency Contact (Optional)">
        <FormGrid>
          <TextField
            fullWidth
            label="Name"
            {...register('emergency_contact_name')}
            disabled={isLoading}
          />

          <TextField
            fullWidth
            label="Relationship"
            {...register('emergency_contact_relation')}
            disabled={isLoading}
          />

          <TextField
            fullWidth
            label="Mobile Phone"
            {...register('emergency_contact_mobile')}
            disabled={isLoading}
          />

          <Box sx={{ gridColumn: { md: '1 / -1' } }}>
            <TextField
              fullWidth
              label="Address"
              {...register('emergency_contact_address')}
              disabled={isLoading}
            />
          </Box>
        </FormGrid>
      </FormSection>

      <FormActions
        submitLabel="Continue to Step 6"
        isSubmitting={isLoading}
        isDirty={true}
      />
    </Box>
  );
}
