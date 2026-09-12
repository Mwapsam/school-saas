'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Grid, TextField, Button, CircularProgress, Alert, Typography } from '@mui/material';
import { step6Schema, type Step6FormData } from '../schemas';
import { useGetAdditionalFields } from '../hooks';

interface Step6FormProps {
  applicationId: string;
  initialData?: any;
  onSubmit: (data: Step6FormData) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onNext?: () => void;
}

export function Step6Form({ applicationId, initialData, onSubmit, isLoading, error, onNext }: Step6FormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Step6FormData>({
    resolver: zodResolver(step6Schema),
    defaultValues: initialData
      ? {
          address_line1: initialData.address_line1 || '',
          address_line2: initialData.address_line2 || '',
          city: initialData.city || '',
          country: initialData.country?.id || '',
          phone: initialData.phone || '',
          mobile: initialData.mobile || '',
          previous_school_name: initialData.previous_school_name || '',
          previous_school_address: initialData.previous_school_address || '',
          previous_school_phone: initialData.previous_school_phone || '',
          previous_school_email: initialData.previous_school_email || '',
          expected_start_date: initialData.expected_start_date || '',
          religious_observances: initialData.religious_observances || '',
          background_information: initialData.background_information || '',
        }
      : undefined,
  });

  const { data: additionalFieldsData } = useGetAdditionalFields();

  const handleFormSubmit = async (data: Step6FormData) => {
    try {
      await onSubmit(data);
      onNext?.();
    } catch (err) {
      console.error('Failed to save step 6:', err);
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit(handleFormSubmit)} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Grid container spacing={2}>
        {/* Student Address */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1 }}>Student Address</Typography>
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Address Line 1"
            {...register('address_line1')}
            error={!!errors.address_line1}
            helperText={errors.address_line1?.message}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Address Line 2"
            {...register('address_line2')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="City"
            {...register('city')}
            error={!!errors.city}
            helperText={errors.city?.message}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Country"
            {...register('country')}
            error={!!errors.country}
            helperText={errors.country?.message}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Phone"
            {...register('phone')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Mobile"
            {...register('mobile')}
            disabled={isLoading}
          />
        </Grid>

        {/* Previous School */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1 }}>Previous School</Typography>
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="School Name"
            {...register('previous_school_name')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="School Address"
            multiline
            rows={2}
            {...register('previous_school_address')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="School Phone"
            {...register('previous_school_phone')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="School Email"
            type="email"
            {...register('previous_school_email')}
            error={!!errors.previous_school_email}
            helperText={errors.previous_school_email?.message}
            disabled={isLoading}
          />
        </Grid>

        {/* Additional Information */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1 }}>Additional Information</Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Expected Start Date"
            type="date"
            {...register('expected_start_date')}
            error={!!errors.expected_start_date}
            helperText={errors.expected_start_date?.message}
            InputLabelProps={{ shrink: true }}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Religious Observances"
            multiline
            rows={2}
            {...register('religious_observances')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Background Information"
            multiline
            rows={3}
            {...register('background_information')}
            disabled={isLoading}
          />
        </Grid>

        {/* Dynamic Additional Fields */}
        {additionalFieldsData && additionalFieldsData.length > 0 && (
          <>
            <Grid item xs={12}>
              <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1 }}>Additional School Information</Typography>
            </Grid>
            {additionalFieldsData.map((field) => (
              <Grid item xs={12} key={field.id}>
                <TextField
                  fullWidth
                  label={field.name}
                  disabled={isLoading}
                  required={field.is_mandatory}
                />
              </Grid>
            ))}
          </>
        )}

        <Grid item xs={12}>
          <Button
            type="submit"
            variant="contained"
            disabled={isLoading}
            startIcon={isLoading && <CircularProgress size={20} />}
          >
            {isLoading ? 'Saving...' : 'Continue to Step 7'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
