'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Grid, TextField, Button, CircularProgress, Alert, MenuItem } from '@mui/material';
import { step2Schema, type Step2FormData } from '../schemas';
import { useGetStudentCategories } from '../hooks';

interface Step2FormProps {
  applicationId: string;
  initialData?: any;
  onSubmit: (data: Step2FormData) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onNext?: () => void;
}

export function Step2Form({ applicationId, initialData, onSubmit, isLoading, error, onNext }: Step2FormProps) {
  const { data: categoriesData } = useGetStudentCategories();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Step2FormData>({
    resolver: zodResolver(step2Schema),
    defaultValues: initialData || undefined,
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
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="First Name *"
            {...register('first_name')}
            error={!!errors.first_name}
            helperText={errors.first_name?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Middle Name"
            {...register('middle_name')}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Last Name *"
            {...register('last_name')}
            error={!!errors.last_name}
            helperText={errors.last_name?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Date of Birth *"
            type="date"
            {...register('date_of_birth')}
            error={!!errors.date_of_birth}
            helperText={errors.date_of_birth?.message}
            InputLabelProps={{ shrink: true }}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            select
            label="Gender *"
            {...register('gender')}
            error={!!errors.gender}
            helperText={errors.gender?.message}
            disabled={isLoading}
          >
            <MenuItem value="male">Male</MenuItem>
            <MenuItem value="female">Female</MenuItem>
            <MenuItem value="other">Other</MenuItem>
          </TextField>
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Nationality *"
            {...register('nationality')}
            error={!!errors.nationality}
            helperText={errors.nationality?.message}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            select
            label="Student Category"
            {...register('student_category')}
            disabled={isLoading}
          >
            {categoriesData?.results.map((cat) => (
              <MenuItem key={cat.id} value={cat.id}>{cat.name}</MenuItem>
            ))}
          </TextField>
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Religion"
            {...register('religion')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Birth Place"
            {...register('birth_place')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Mother Tongue"
            {...register('mother_tongue')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Preferred Name"
            {...register('preferred_name')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Home Language"
            {...register('home_language')}
            disabled={isLoading}
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Authorized Pickup Persons"
            multiline
            rows={2}
            {...register('authorized_pickup_persons')}
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
            {isLoading ? 'Saving...' : 'Continue to Step 3'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
