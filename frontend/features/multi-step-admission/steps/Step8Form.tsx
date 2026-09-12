'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Grid, TextField, Button, CircularProgress, Alert, FormControlLabel, Checkbox, Card, CardContent, Typography } from '@mui/material';
import { step8Schema, type Step8FormData } from '../schemas';

interface Step8FormProps {
  applicationId: string;
  applicationData?: any;
  initialData?: any;
  onSubmit: (data: Step8FormData) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
}

export function Step8Form({ applicationId, applicationData, initialData, onSubmit, isLoading, error }: Step8FormProps) {
  const today = new Date().toISOString().split('T')[0];

  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
  } = useForm<Step8FormData>({
    resolver: zodResolver(step8Schema),
    defaultValues: initialData
      ? {
          declaration_agreement: initialData.declaration_agreement || false,
          declaration_date: initialData.declaration_date || today,
          declaration_signature_name: initialData.declaration_signature_name || '',
          fee_acknowledgment: initialData.fee_acknowledgment || false,
        }
      : {
          declaration_date: today,
        },
  });

  const declarationAgreed = watch('declaration_agreement');
  const feeAcknowledged = watch('fee_acknowledgment');

  const handleFormSubmit = async (data: Step8FormData) => {
    try {
      await onSubmit(data);
    } catch (err) {
      console.error('Failed to submit application:', err);
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit(handleFormSubmit)} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Grid container spacing={3}>
        {/* Application Summary */}
        <Grid item xs={12}>
          <Alert severity="info">
            Please review your application information below. Once submitted, you cannot edit your application.
            Contact support if you need to make changes.
          </Alert>
        </Grid>

        {applicationData && (
          <>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2 }}>
                    Personal Information
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>Name:</strong> {applicationData?.first_name} {applicationData?.last_name}
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>Date of Birth:</strong> {applicationData?.date_of_birth}
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>Gender:</strong> {applicationData?.gender}
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>Email:</strong> {applicationData?.email}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2 }}>
                    Academic Information
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>Academic Year:</strong> {applicationData?.academic_year?.name}
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>Course Applied:</strong> {applicationData?.course_applied?.course_name}
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>Previous School:</strong> {applicationData?.previous_school_name || '-'}
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>Expected Start Date:</strong> {applicationData?.expected_start_date || '-'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2 }}>
                    Guardian 1 Information
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>Name:</strong> {applicationData?.guardian1_first_name} {applicationData?.guardian1_last_name}
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>Relationship:</strong> {applicationData?.guardian1_relation}
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>Mobile:</strong> {applicationData?.guardian1_mobile}
                  </Typography>
                  <Typography variant="body2" gutterBottom>
                    <strong>Email:</strong> {applicationData?.guardian1_email || '-'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            {applicationData?.guardian2_first_name && (
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2 }}>
                      Guardian 2 Information
                    </Typography>
                    <Typography variant="body2" gutterBottom>
                      <strong>Name:</strong> {applicationData?.guardian2_first_name} {applicationData?.guardian2_last_name}
                    </Typography>
                    <Typography variant="body2" gutterBottom>
                      <strong>Relationship:</strong> {applicationData?.guardian2_relation}
                    </Typography>
                    <Typography variant="body2" gutterBottom>
                      <strong>Mobile:</strong> {applicationData?.guardian2_mobile}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            )}
          </>
        )}

        {/* Declaration Section */}
        <Grid item xs={12}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2 }}>Declaration & Submission</Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Declaration Date *"
            type="date"
            {...register('declaration_date')}
            error={!!errors.declaration_date}
            helperText={errors.declaration_date?.message}
            InputLabelProps={{ shrink: true }}
            disabled={isLoading}
            required
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Full Name (Signature) *"
            {...register('declaration_signature_name')}
            error={!!errors.declaration_signature_name}
            helperText={errors.declaration_signature_name?.message}
            disabled={isLoading}
            required
            placeholder="Type your full name as your digital signature"
          />
        </Grid>

        <Grid item xs={12}>
          <Card sx={{ backgroundColor: '#f5f5f5', p: 2 }}>
            <CardContent>
              <Typography variant="body2" paragraph>
                I hereby declare that the information provided in this application form is true and complete to the best of my knowledge.
              </Typography>
              <Typography variant="body2">
                I understand that any false or misleading information may result in the rejection of this application or dismissal from the school.
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Checkbox
                {...register('declaration_agreement')}
                disabled={isLoading}
              />
            }
            label="I agree to the declaration and terms *"
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
            label="I acknowledge the admission fee payment requirement *"
          />
          {errors.fee_acknowledgment && (
            <Alert severity="error" sx={{ mt: 1 }}>{errors.fee_acknowledgment.message}</Alert>
          )}
        </Grid>

        <Grid item xs={12}>
          <Button
            type="submit"
            variant="contained"
            size="large"
            disabled={isLoading || !declarationAgreed || !feeAcknowledged}
            startIcon={isLoading && <CircularProgress size={20} />}
          >
            {isLoading ? 'Submitting...' : 'Submit Application'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
