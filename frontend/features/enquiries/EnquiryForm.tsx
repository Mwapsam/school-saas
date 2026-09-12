'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Grid, TextField, Button, CircularProgress, Alert } from '@mui/material';
import { enquiryFormSchema, type EnquiryFormData } from './schemas';
import { ApplicantEnquiry } from './hooks';

interface EnquiryFormProps {
  initialData?: ApplicantEnquiry;
  onSubmit: (data: any) => Promise<any>;
  isLoading?: boolean;
  error?: string | null;
}

export function EnquiryForm({ initialData, onSubmit, isLoading, error }: EnquiryFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<EnquiryFormData>({
    resolver: zodResolver(enquiryFormSchema),
    defaultValues: initialData
      ? {
          first_name: initialData.first_name,
          last_name: initialData.last_name,
          date_of_birth: initialData.date_of_birth || undefined,
          email: initialData.email || undefined,
          phone: initialData.phone || undefined,
          address_line1: initialData.address_line1 || undefined,
          address_line2: initialData.address_line2 || undefined,
          city: initialData.city || undefined,
          state: initialData.state || undefined,
          postal_code: initialData.postal_code || undefined,
          guardian_first_name: initialData.guardian_first_name || undefined,
          guardian_last_name: initialData.guardian_last_name || undefined,
          guardian_relation: initialData.guardian_relation || undefined,
          guardian_email: initialData.guardian_email || undefined,
          guardian_phone: initialData.guardian_phone || undefined,
          guardian_address_line1: initialData.guardian_address_line1 || undefined,
          guardian_address_line2: initialData.guardian_address_line2 || undefined,
          guardian_occupation: initialData.guardian_occupation || undefined,
          guardian_income: initialData.guardian_income || undefined,
          guardian_education: initialData.guardian_education || undefined,
          remarks: initialData.remarks || undefined,
        }
      : undefined,
  });

  return (
    <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Grid container spacing={2}>
        {/* Student Information */}
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="First Name"
            {...register('first_name')}
            error={!!errors.first_name}
            helperText={errors.first_name?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Last Name"
            {...register('last_name')}
            error={!!errors.last_name}
            helperText={errors.last_name?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Date of Birth"
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
            label="Phone"
            {...register('phone')}
            error={!!errors.phone}
            helperText={errors.phone?.message}
            disabled={isLoading}
          />
        </Grid>

        {/* Address */}
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
            error={!!errors.address_line2}
            helperText={errors.address_line2?.message}
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
            label="State"
            {...register('state')}
            error={!!errors.state}
            helperText={errors.state?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Postal Code"
            {...register('postal_code')}
            error={!!errors.postal_code}
            helperText={errors.postal_code?.message}
            disabled={isLoading}
          />
        </Grid>

        {/* Guardian Information */}
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Guardian First Name"
            {...register('guardian_first_name')}
            error={!!errors.guardian_first_name}
            helperText={errors.guardian_first_name?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Guardian Last Name"
            {...register('guardian_last_name')}
            error={!!errors.guardian_last_name}
            helperText={errors.guardian_last_name?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Relation to Student"
            {...register('guardian_relation')}
            error={!!errors.guardian_relation}
            helperText={errors.guardian_relation?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Guardian Email"
            type="email"
            {...register('guardian_email')}
            error={!!errors.guardian_email}
            helperText={errors.guardian_email?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Guardian Phone"
            {...register('guardian_phone')}
            error={!!errors.guardian_phone}
            helperText={errors.guardian_phone?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Guardian Address Line 1"
            {...register('guardian_address_line1')}
            error={!!errors.guardian_address_line1}
            helperText={errors.guardian_address_line1?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Guardian Address Line 2"
            {...register('guardian_address_line2')}
            error={!!errors.guardian_address_line2}
            helperText={errors.guardian_address_line2?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Guardian Occupation"
            {...register('guardian_occupation')}
            error={!!errors.guardian_occupation}
            helperText={errors.guardian_occupation?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Guardian Income"
            {...register('guardian_income')}
            error={!!errors.guardian_income}
            helperText={errors.guardian_income?.message}
            disabled={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Guardian Education"
            {...register('guardian_education')}
            error={!!errors.guardian_education}
            helperText={errors.guardian_education?.message}
            disabled={isLoading}
          />
        </Grid>

        {/* Additional Information */}
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Remarks"
            multiline
            rows={4}
            {...register('remarks')}
            error={!!errors.remarks}
            helperText={errors.remarks?.message}
            disabled={isLoading}
          />
        </Grid>

        {/* Submit Button */}
        <Grid item xs={12}>
          <Button
            type="submit"
            variant="contained"
            disabled={isLoading}
            startIcon={isLoading && <CircularProgress size={20} />}
          >
            {isLoading ? 'Saving...' : 'Save Enquiry'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
