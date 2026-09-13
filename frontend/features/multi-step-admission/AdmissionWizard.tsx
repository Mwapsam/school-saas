'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Container, Box, Stepper, Step, StepLabel, Typography, Alert, CircularProgress, Button } from '@mui/material';
import { ArrowBack as BackIcon } from '@mui/icons-material';
import {
  useGetApplication,
  useUpdateApplicationStep,
  useSubmitApplication,
  useGetProgress,
  type ExtendedAdmissionApplication,
} from './hooks';
import {
  Step1Form,
  Step2Form,
  Step3Form,
  Step4Form,
  Step5Form,
  Step6Form,
  Step7Form,
  Step8Form,
} from './steps';
import {
  type Step1FormData,
  type Step2FormData,
  type Step3FormData,
  type Step4FormData,
  type Step5FormData,
  type Step6FormData,
  type Step8FormData,
} from './schemas';

const STEP_LABELS = [
  'Terms',
  'Academic',
  'Personal',
  'Guardian 1',
  'Guardian 2',
  'Address',
  'Documents',
  'Declaration',
];

interface AdmissionWizardProps {
  applicationId: string;
}

export function AdmissionWizard({ applicationId }: AdmissionWizardProps) {
  const router = useRouter();
  const [activeStep, setActiveStep] = useState(0);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const { data: application, isLoading: isLoadingApp } = useGetApplication(applicationId);
  const { data: progress } = useGetProgress(applicationId);
  const step1Mutation = useUpdateApplicationStep(applicationId, 1);
  const step2Mutation = useUpdateApplicationStep(applicationId, 2);
  const step3Mutation = useUpdateApplicationStep(applicationId, 3);
  const step4Mutation = useUpdateApplicationStep(applicationId, 4);
  const step5Mutation = useUpdateApplicationStep(applicationId, 5);
  const step6Mutation = useUpdateApplicationStep(applicationId, 6);
  const step8Mutation = useUpdateApplicationStep(applicationId, 8);
  const submitMutation = useSubmitApplication(applicationId);

  if (isLoadingApp) {
    return (
      <Container maxWidth="md">
        <Box sx={{ py: 4, display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (!application) {
    return (
      <Container maxWidth="md">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">Application not found</Alert>
        </Box>
      </Container>
    );
  }

  const handleStep1Submit = async (data: Step1FormData) => {
    setSubmitError(null);
    try {
      console.log('Submitting Step 1:', data);
      await step1Mutation.mutateAsync(data);
      console.log('Step 1 saved successfully');
      handleNext();
    } catch (error: any) {
      console.error('Step 1 error:', error);
      const errorMsg = error?.response?.data?.error || error?.response?.data?.detail || error?.message || 'Failed to save step 1';
      setSubmitError(errorMsg);
    }
  };

  const handleStep2Submit = async (data: Step2FormData) => {
    setSubmitError(null);
    try {
      console.log('Submitting Step 2:', data);
      await step2Mutation.mutateAsync(data);
      console.log('Step 2 saved successfully');
      handleNext();
    } catch (error: any) {
      console.error('Step 2 error:', error);
      const errorMsg = error?.response?.data?.error || error?.response?.data?.detail || error?.message || 'Failed to save step 2';
      setSubmitError(errorMsg);
    }
  };

  const handleStep3Submit = async (data: Step3FormData) => {
    setSubmitError(null);
    try {
      console.log('Submitting Step 3:', data);
      await step3Mutation.mutateAsync(data);
      console.log('Step 3 saved successfully');
      handleNext();
    } catch (error: any) {
      console.error('Step 3 error:', error);
      const errorMsg = error?.response?.data?.error || error?.response?.data?.detail || error?.message || 'Failed to save step 3';
      setSubmitError(errorMsg);
    }
  };

  const handleStep4Submit = async (data: Step4FormData) => {
    setSubmitError(null);
    try {
      console.log('Submitting Step 4:', data);
      await step4Mutation.mutateAsync(data);
      console.log('Step 4 saved successfully');
      handleNext();
    } catch (error: any) {
      console.error('Step 4 error:', error);
      const errorMsg = error?.response?.data?.error || error?.response?.data?.detail || error?.message || 'Failed to save step 4';
      setSubmitError(errorMsg);
    }
  };

  const handleStep5Submit = async (data: Step5FormData) => {
    setSubmitError(null);
    try {
      console.log('Submitting Step 5:', data);
      await step5Mutation.mutateAsync(data);
      console.log('Step 5 saved successfully');
      handleNext();
    } catch (error: any) {
      console.error('Step 5 error:', error);
      const errorMsg = error?.response?.data?.error || error?.response?.data?.detail || error?.message || 'Failed to save step 5';
      setSubmitError(errorMsg);
    }
  };

  const handleStep6Submit = async (data: Step6FormData) => {
    setSubmitError(null);
    try {
      console.log('Submitting Step 6:', data);
      await step6Mutation.mutateAsync(data);
      console.log('Step 6 saved successfully');
      handleNext();
    } catch (error: any) {
      console.error('Step 6 error:', error);
      const errorMsg = error?.response?.data?.error || error?.response?.data?.detail || error?.message || 'Failed to save step 6';
      setSubmitError(errorMsg);
    }
  };

  const handleStep8Submit = async (data: Step8FormData) => {
    setSubmitError(null);
    try {
      console.log('Submitting Step 8:', data);
      await step8Mutation.mutateAsync(data);
      console.log('Step 8 saved successfully');
      console.log('Submitting application...');
      await submitMutation.mutateAsync({ confirm_submission: true });
      console.log('Application submitted successfully');
      router.push('/dashboard/admissions');
    } catch (error: any) {
      console.error('Step 8 or submission error:', error);
      const errorMsg = error?.response?.data?.error || error?.response?.data?.detail || error?.message || 'Failed to submit application';
      setSubmitError(errorMsg);
    }
  };

  const handleNext = () => {
    setActiveStep((prev) => prev + 1);
  };

  const handleBack = () => {
    if (activeStep === 0) {
      router.back();
    } else {
      setActiveStep((prev) => prev - 1);
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <Button startIcon={<BackIcon />} onClick={handleBack} variant="text">
            Back
          </Button>
          <Typography variant="h5">{application.application_number}</Typography>
        </Box>

        <Stepper
          activeStep={activeStep}
          sx={{
            py: 2,
            '& .MuiStepLabel-label': {
              display: { xs: 'none', sm: 'block' },
              fontSize: { sm: '0.8rem', md: '0.9rem' },
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            },
            '& .MuiStep-root': {
              flex: '1 1 auto',
              minWidth: 0,
              padding: { xs: '0 2px', sm: '0 8px' },
            },
          }}
        >
          {STEP_LABELS.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {/* Mobile: step progress indicator */}
        <Box sx={{ display: { xs: 'block', sm: 'none' }, textAlign: 'center', mb: 2 }}>
          <Typography variant="caption" color="textSecondary">
            Step {activeStep + 1} of {STEP_LABELS.length}
          </Typography>
        </Box>

        <Box sx={{ mt: 4 }}>
          {submitError && <Alert severity="error" sx={{ mb: 2 }}>{submitError}</Alert>}

          {activeStep === 0 && (
            <Step1Form
              applicationId={applicationId}
              initialData={application}
              onSubmit={handleStep1Submit}
              isLoading={step1Mutation.isPending}
              error={step1Mutation.error?.message || null}
              onNext={handleNext}
            />
          )}

          {activeStep === 1 && (
            <Step2Form
              applicationId={applicationId}
              initialData={application}
              onSubmit={handleStep2Submit}
              isLoading={step2Mutation.isPending}
              error={step2Mutation.error?.message || null}
              onNext={handleNext}
            />
          )}

          {activeStep === 2 && (
            <Step3Form
              applicationId={applicationId}
              initialData={application}
              onSubmit={handleStep3Submit}
              isLoading={step3Mutation.isPending}
              error={step3Mutation.error?.message || null}
              onNext={handleNext}
            />
          )}

          {activeStep === 3 && (
            <Step4Form
              applicationId={applicationId}
              initialData={application}
              onSubmit={handleStep4Submit}
              isLoading={step4Mutation.isPending}
              error={step4Mutation.error?.message || null}
              onNext={handleNext}
            />
          )}

          {activeStep === 4 && (
            <Step5Form
              applicationId={applicationId}
              initialData={application}
              onSubmit={handleStep5Submit}
              isLoading={step5Mutation.isPending}
              error={step5Mutation.error?.message || null}
              onNext={handleNext}
            />
          )}

          {activeStep === 5 && (
            <Step6Form
              applicationId={applicationId}
              initialData={application}
              onSubmit={handleStep6Submit}
              isLoading={step6Mutation.isPending}
              error={step6Mutation.error?.message || null}
              onNext={handleNext}
            />
          )}

          {activeStep === 6 && (
            <Step7Form
              applicationId={applicationId}
              onNext={handleNext}
              isLoading={false}
            />
          )}

          {activeStep === 7 && (
            <Step8Form
              applicationId={applicationId}
              applicationData={application}
              initialData={application}
              onSubmit={handleStep8Submit}
              isLoading={step8Mutation.isPending || submitMutation.isPending}
              error={step8Mutation.error?.message || submitMutation.error?.message || null}
            />
          )}
        </Box>
      </Box>
    </Container>
  );
}
