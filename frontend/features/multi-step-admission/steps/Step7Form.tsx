'use client';

import { useForm } from 'react-hook-form';
import { Box, Grid, Button, CircularProgress, Alert, Card, CardContent, Typography, FormControlLabel, Checkbox } from '@mui/material';
import { FileDownload as DownloadIcon, CheckCircle as SubmitIcon } from '@mui/icons-material';

interface Step7FormProps {
  applicationId: string;
  applicationData?: any;
  onSubmit: (data: { confirm_submission: boolean }) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
}

export function Step7Form({ applicationId, applicationData, onSubmit, isLoading, error }: Step7FormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
  } = useForm<{ confirm_submission: boolean }>({
    defaultValues: { confirm_submission: false },
  });

  const confirmSubmission = watch('confirm_submission');

  return (
    <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Alert severity="info">
            Please review your application information below. Once submitted, you cannot edit your application.
            Contact support if you need to make changes.
          </Alert>
        </Grid>

        {/* Application Summary */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Personal Information
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Name:</strong> {applicationData?.full_name}
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Date of Birth:</strong> {applicationData?.date_of_birth}
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Gender:</strong> {applicationData?.gender}
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Nationality:</strong> {applicationData?.nationality}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Application Information
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Application #:</strong> {applicationData?.application_number}
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Academic Year:</strong> {applicationData?.academic_year?.name}
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Course Applied:</strong> {applicationData?.course_applied?.course_name}
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Status:</strong> {applicationData?.status}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Contact Information
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Email:</strong> {applicationData?.email || '-'}
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Phone:</strong> {applicationData?.phone || '-'}
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Mobile:</strong> {applicationData?.mobile || '-'}
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>City:</strong> {applicationData?.city || '-'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Guardian Information
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Guardian 1:</strong> {applicationData?.guardian1_first_name} {applicationData?.guardian1_last_name}
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Relation:</strong> {applicationData?.guardian1_relation}
              </Typography>
              <Typography variant="body2" color="textSecondary" gutterBottom>
                <strong>Mobile:</strong> {applicationData?.guardian1_mobile}
              </Typography>
              {applicationData?.guardian2_first_name && (
                <Typography variant="body2" color="textSecondary" gutterBottom>
                  <strong>Guardian 2:</strong> {applicationData?.guardian2_first_name} {applicationData?.guardian2_last_name}
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Completion Checklist */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Completion Checklist
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                ✓ Step 1: Academic Year Selection
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                ✓ Step 2: Personal Details
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                ✓ Step 3: Communication Details
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                ✓ Step 4: Guardian Information
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                ✓ Step 5: Health & Declaration
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                ✓ Step 6: Documents Uploaded ({applicationData?.documents?.length || 0})
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Confirmation */}
        <Grid item xs={12}>
          <Alert severity="warning">
            By submitting this application, I confirm that all information provided is accurate and complete.
          </Alert>
        </Grid>

        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Checkbox
                {...register('confirm_submission')}
                disabled={isLoading}
              />
            }
            label="I confirm that all information is accurate and agree to submit this application"
          />
          {errors.confirm_submission && (
            <Alert severity="error" sx={{ mt: 1 }}>{errors.confirm_submission.message}</Alert>
          )}
        </Grid>

        <Grid item xs={12}>
          <Button
            type="submit"
            variant="contained"
            size="large"
            color="success"
            disabled={!confirmSubmission || isLoading}
            startIcon={isLoading ? <CircularProgress size={20} /> : <SubmitIcon />}
          >
            {isLoading ? 'Submitting...' : 'Submit Application'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
