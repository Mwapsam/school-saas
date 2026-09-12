'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Grid, TextField, Button, CircularProgress, Alert, Typography } from '@mui/material';
import { step4Schema, type Step4FormData } from '../schemas';

interface Step4FormProps {
  applicationId: string;
  initialData?: any;
  onSubmit: (data: Step4FormData) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onNext?: () => void;
}

export function Step4Form({ applicationId, initialData, onSubmit, isLoading, error, onNext }: Step4FormProps) {
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

  return (
    <Box component="form" onSubmit={handleSubmit(handleFormSubmit)} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Grid container spacing={2}>
        {/* Guardian 1 */}
        <Grid item xs={12}>
          <Typography variant="h6">Guardian 1 Information *</Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="First Name *"
            {...register('guardian1_first_name')}
            error={!!errors.guardian1_first_name}
            helperText={errors.guardian1_first_name?.message}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Last Name *"
            {...register('guardian1_last_name')}
            error={!!errors.guardian1_last_name}
            helperText={errors.guardian1_last_name?.message}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Relation *"
            {...register('guardian1_relation')}
            error={!!errors.guardian1_relation}
            helperText={errors.guardian1_relation?.message}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Occupation"
            {...register('guardian1_occupation')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Office Address Line 1"
            {...register('guardian1_office_address_line1')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Office City"
            {...register('guardian1_office_city')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Office Phone 1"
            {...register('guardian1_office_phone1')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Mobile *"
            {...register('guardian1_mobile')}
            error={!!errors.guardian1_mobile}
            helperText={errors.guardian1_mobile?.message}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Email"
            type="email"
            {...register('guardian1_email')}
            error={!!errors.guardian1_email}
            helperText={errors.guardian1_email?.message}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="House/Plot No"
            {...register('guardian1_house_plot_no')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Road Name"
            {...register('guardian1_road_name')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Area/Location"
            {...register('guardian1_area_location')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Flat/Block Name"
            {...register('guardian1_flat_block_name')}
            disabled={isLoading}
          />
        </Grid>

        {/* Guardian 2 */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ mt: 2 }}>Guardian 2 Information (Optional)</Typography>
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
            label="Relation"
            {...register('guardian2_relation')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Mobile"
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

        {/* Emergency Contact */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ mt: 2 }}>Emergency Contact (Optional)</Typography>
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
            label="Relation"
            {...register('emergency_contact_relation')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Mobile"
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
            {isLoading ? 'Saving...' : 'Continue to Step 5'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
