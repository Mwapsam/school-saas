'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Grid, TextField, Button, CircularProgress, Alert, MenuItem } from '@mui/material';
import { step3Schema, type Step3FormData } from '../schemas';
import { useGetCountries } from '../hooks';

interface Step3FormProps {
  applicationId: string;
  initialData?: any;
  onSubmit: (data: Step3FormData) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onNext?: () => void;
}

export function Step3Form({ applicationId, initialData, onSubmit, isLoading, error, onNext }: Step3FormProps) {
  const { data: countriesData } = useGetCountries();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Step3FormData>({
    resolver: zodResolver(step3Schema),
    defaultValues: initialData || undefined,
  });

  const handleFormSubmit = async (data: Step3FormData) => {
    try {
      await onSubmit(data);
      onNext?.();
    } catch (err) {
      console.error('Failed to save step 3:', err);
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit(handleFormSubmit)} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Grid container spacing={2}>
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Full Address"
            multiline
            rows={2}
            {...register('address')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Address Line 1 *"
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
            label="City *"
            {...register('city')}
            error={!!errors.city}
            helperText={errors.city?.message}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            select
            label="Country *"
            {...register('country')}
            error={!!errors.country}
            helperText={errors.country?.message}
            disabled={isLoading}
          >
            {countriesData?.results.map((country) => (
              <MenuItem key={country.id} value={country.id}>
                {country.name} ({country.code})
              </MenuItem>
            ))}
          </TextField>
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

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Email"
            type="email"
            {...register('email')}
            error={!!errors.email}
            helperText={errors.email?.message}
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
            {isLoading ? 'Saving...' : 'Continue to Step 4'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
