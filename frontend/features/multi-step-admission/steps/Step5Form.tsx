'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Grid, TextField, Button, CircularProgress, Alert, FormControlLabel, Checkbox, Typography } from '@mui/material';
import { step5Schema, type Step5FormData } from '../schemas';

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
    formState: { errors },
    watch,
  } = useForm<Step5FormData>({
    resolver: zodResolver(step5Schema),
    defaultValues: initialData || undefined,
  });

  const declarationAgreed = watch('declaration_agreement');
  const feeAcknowledged = watch('fee_acknowledgment');
  const hasMedical = watch('has_medical_problems');
  const hasHospitalization = watch('recent_hospitalization');
  const hasAllergies = watch('has_allergies');

  const handleFormSubmit = async (data: Step5FormData) => {
    try {
      await onSubmit(data);
      onNext?.();
    } catch (err) {
      console.error('Failed to save step 5:', err);
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit(handleFormSubmit)} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Grid container spacing={2}>
        {/* Previous School */}
        <Grid item xs={12}>
          <Typography variant="h6">Previous School Information</Typography>
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

        {/* Health Information */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ mt: 2 }}>Health Information</Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
          <FormControlLabel
            control={
              <Checkbox
                {...register('has_medical_problems')}
                disabled={isLoading}
              />
            }
            label="Has Medical Problems"
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <FormControlLabel
            control={
              <Checkbox
                {...register('recent_hospitalization')}
                disabled={isLoading}
              />
            }
            label="Recent Hospitalization"
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <FormControlLabel
            control={
              <Checkbox
                {...register('has_allergies')}
                disabled={isLoading}
              />
            }
            label="Has Allergies"
          />
        </Grid>

        {(hasMedical || hasHospitalization || hasAllergies) && (
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Medical Details *"
              multiline
              rows={3}
              {...register('medical_details')}
              error={!!errors.medical_details}
              helperText={errors.medical_details?.message || 'Required when health questions are answered Yes'}
              disabled={isLoading}
            />
          </Grid>
        )}

        {/* Additional Information */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ mt: 2 }}>Additional Information</Typography>
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

        {/* Declaration */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ mt: 2 }}>Declaration & Acknowledgment</Typography>
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Typed Full Name (Digital Signature)"
            {...register('declaration_signature_name')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Checkbox
                {...register('declaration_agreement')}
                disabled={isLoading}
              />
            }
            label="I agree to the declaration and terms"
          />
          {errors.declaration_agreement && (
            <Alert severity="error" sx={{ mt: 1 }}>{errors.declaration_agreement.message}</Alert>
          )}
        </Grid>

        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Checkbox
                {...register('fee_acknowledgment')}
                disabled={isLoading}
              />
            }
            label="I acknowledge the admission fee payment requirement"
          />
          {errors.fee_acknowledgment && (
            <Alert severity="error" sx={{ mt: 1 }}>{errors.fee_acknowledgment.message}</Alert>
          )}
        </Grid>

        <Grid item xs={12}>
          <Button
            type="submit"
            variant="contained"
            disabled={isLoading || !declarationAgreed || !feeAcknowledged}
            startIcon={isLoading && <CircularProgress size={20} />}
          >
            {isLoading ? 'Saving...' : 'Continue to Step 6 (Documents)'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
