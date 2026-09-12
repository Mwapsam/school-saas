'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Grid, TextField, Button, CircularProgress, Alert, Typography } from '@mui/material';
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
  } = useForm<Step5FormData>({
    resolver: zodResolver(step5Schema),
    defaultValues: initialData || undefined,
  });

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
        {/* Guardian 2 */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1 }}>Guardian 2 (Optional)</Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="First Name"
            {...register('guardian2_first_name')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Last Name"
            {...register('guardian2_last_name')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Relationship to Child"
            {...register('guardian2_relation')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Mobile Phone"
            {...register('guardian2_mobile')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Email"
            type="email"
            {...register('guardian2_email')}
            error={!!errors.guardian2_email}
            helperText={errors.guardian2_email?.message}
            disabled={isLoading}
          />
        </Grid>

        {/* Guardian 2 Professional Information */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1 }}>Guardian 2 — Professional Information</Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Occupation"
            {...register('guardian2_occupation')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Office Phone"
            {...register('guardian2_office_phone1')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Office Address"
            {...register('guardian2_office_address_line1')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="City"
            {...register('guardian2_city')}
            disabled={isLoading}
          />
        </Grid>

        {/* Guardian 2 Residential Address */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1 }}>Guardian 2 — Residential Address</Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="House/Plot No"
            {...register('guardian2_house_plot_no')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Road Name"
            {...register('guardian2_road_name')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Area/Location"
            {...register('guardian2_area_location')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Flat/Block Name"
            {...register('guardian2_flat_block_name')}
            disabled={isLoading}
          />
        </Grid>

        {/* Emergency Contact */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1 }}>Emergency Contact (Optional)</Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Name"
            {...register('emergency_contact_name')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Relationship"
            {...register('emergency_contact_relation')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Mobile Phone"
            {...register('emergency_contact_mobile')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Address"
            multiline
            rows={2}
            {...register('emergency_contact_address')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12}>
          <Button
            type="submit"
            variant="contained"
            disabled={isLoading}
            startIcon={isLoading && <CircularProgress size={20} />}
          >
            {isLoading ? 'Saving...' : 'Continue to Step 6'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
