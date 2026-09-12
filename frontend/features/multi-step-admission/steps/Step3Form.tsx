'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Grid, TextField, Button, CircularProgress, Alert, MenuItem, FormControlLabel, Checkbox, Typography, Paper } from '@mui/material';
import { step3Schema, type Step3FormData } from '../schemas';

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
    formState: { errors },
    watch,
  } = useForm<Step3FormData>({
    resolver: zodResolver(step3Schema),
    defaultValues: initialData || undefined,
  });

  const hasMedicalProblems = watch('has_medical_problems');
  const hasHospitalization = watch('recent_hospitalization');
  const hasAllergies = watch('has_allergies');

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
        {/* Child's Name Section */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1 }}>Child's Name</Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="First Name *"
            {...register('first_name')}
            error={!!errors.first_name}
            helperText={errors.first_name?.message}
            disabled={isLoading}
            required
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
            required
          />
        </Grid>

        {/* Basic Information */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1 }}>Basic Information</Typography>
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
            required
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
            required
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
            required
          />
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

        {/* School-Specific Information */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1 }}>School-Specific Information</Typography>
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

        {/* Contact Information */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1 }}>Contact & Pickup Information</Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
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

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Student Photo"
            type="file"
            {...register('student_photo')}
            disabled={isLoading}
            inputProps={{ accept: 'image/*' }}
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
            helperText="Please notify us immediately of any changes"
          />
        </Grid>

        {/* Health Information */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1 }}>Health Information</Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
          <FormControlLabel
            control={
              <Checkbox
                {...register('has_medical_problems')}
                disabled={isLoading}
              />
            }
            label="Any ongoing medical problems?"
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
            label="Been in hospital recently?"
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
            label="Any allergies?"
          />
        </Grid>

        {(hasMedicalProblems || hasHospitalization || hasAllergies) && (
          <Grid item xs={12}>
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
          </Grid>
        )}

        <Grid item xs={12}>
          <Button
            type="submit"
            variant="contained"
            disabled={isLoading || !!errors.first_name || !!errors.last_name || !!errors.date_of_birth || !!errors.gender || !!errors.nationality}
            startIcon={isLoading && <CircularProgress size={20} />}
          >
            {isLoading ? 'Saving...' : 'Continue to Step 4'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
