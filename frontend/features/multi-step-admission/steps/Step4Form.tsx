'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, TextField, Alert } from '@mui/material';
import { step4Schema, type Step4FormData } from '../schemas';
import { FormSection, FormActions, FormGrid } from '@/components/forms';

interface Step4FormProps {
  initialData?: any;
  onSubmit: (data: Step4FormData) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onNext?: () => void;
}

export function Step4Form({ initialData, onSubmit, isLoading, error, onNext }: Step4FormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Step4FormData>({
    resolver: zodResolver(step4Schema),
    defaultValues: initialData || undefined,
  });

  const handleFormSubmit = async (data: Step4FormData) => {
    try {
      await onSubmit(data);
      onNext?.();
    } catch (err) {
      console.error('Failed to save step 4:', err);
    }
  };

  const computedValidity = !errors.guardian1_first_name && !errors.guardian1_last_name && !errors.guardian1_relation && !errors.guardian1_mobile;

  return (
    <Box component="form" onSubmit={handleSubmit(handleFormSubmit)} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <FormSection title="Guardian 1 — Personal Information">
        <FormGrid>
          <TextField
            fullWidth
            label="First Name *"
            {...register('guardian1_first_name')}
            error={!!errors.guardian1_first_name}
            helperText={errors.guardian1_first_name?.message}
            disabled={isLoading}
            required
          />

          <TextField
            fullWidth
            label="Last Name *"
            {...register('guardian1_last_name')}
            error={!!errors.guardian1_last_name}
            helperText={errors.guardian1_last_name?.message}
            disabled={isLoading}
            required
          />

          <TextField
            fullWidth
            label="Relationship to Child *"
            {...register('guardian1_relation')}
            error={!!errors.guardian1_relation}
            helperText={errors.guardian1_relation?.message}
            disabled={isLoading}
            required
          />

          <TextField
            fullWidth
            label="Mobile Phone *"
            {...register('guardian1_mobile')}
            error={!!errors.guardian1_mobile}
            helperText={errors.guardian1_mobile?.message}
            disabled={isLoading}
            required
          />

          <Box sx={{ gridColumn: { md: '1 / -1' } }}>
            <TextField
              fullWidth
              label="Email"
              type="email"
              {...register('guardian1_email')}
              error={!!errors.guardian1_email}
              helperText={errors.guardian1_email?.message}
              disabled={isLoading}
            />
          </Box>
        </FormGrid>
      </FormSection>

      <FormSection title="Guardian 1 — Professional Information">
        <FormGrid>
          <TextField
            fullWidth
            label="Occupation"
            {...register('guardian1_occupation')}
            disabled={isLoading}
          />

          <TextField
            fullWidth
            label="Office Phone"
            {...register('guardian1_office_phone1')}
            disabled={isLoading}
          />

          <Box sx={{ gridColumn: { md: '1 / -1' } }}>
            <TextField
              fullWidth
              label="Office Address"
              {...register('guardian1_office_address_line1')}
              disabled={isLoading}
            />
          </Box>

          <TextField
            fullWidth
            label="City"
            {...register('guardian1_city')}
            disabled={isLoading}
          />
        </FormGrid>
      </FormSection>

      <FormSection title="Guardian 1 — Residential Address">
        <FormGrid>
          <TextField
            fullWidth
            label="House/Plot No"
            {...register('guardian1_house_plot_no')}
            disabled={isLoading}
          />

          <TextField
            fullWidth
            label="Road Name"
            {...register('guardian1_road_name')}
            disabled={isLoading}
          />

          <TextField
            fullWidth
            label="Area/Location"
            {...register('guardian1_area_location')}
            disabled={isLoading}
          />

          <TextField
            fullWidth
            label="Flat/Block Name"
            {...register('guardian1_flat_block_name')}
            disabled={isLoading}
          />
        </FormGrid>
      </FormSection>

      <FormActions
        submitLabel="Continue to Step 5"
        isSubmitting={isLoading}
        isDirty={computedValidity}
      />
    </Box>
  );
}
