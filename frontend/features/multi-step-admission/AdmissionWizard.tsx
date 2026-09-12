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
} from './steps';
import {
  type Step1FormData,
  type Step2FormData,
  type Step3FormData,
  type Step4FormData,
  type Step5FormData,
} from './schemas';

const STEP_LABELS = [
  'Academic Year',
  'Personal Details',
  'Communication',
  'Guardians',
  'Health & Declaration',
  'Documents',
  'Review & Submit',
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
      await step1Mutation.mutateAsync(data);
      handleNext();
    } catch (error: any) {
      setSubmitError(error?.message || 'Failed to save step 1');
    }
  };

  const handleStep2Submit = async (data: Step2FormData) => {
    setSubmitError(null);
    try {
      await step2Mutation.mutateAsync(data);
      handleNext();
    } catch (error: any) {
      setSubmitError(error?.message || 'Failed to save step 2');
    }
  };

  const handleStep3Submit = async (data: Step3FormData) => {
    setSubmitError(null);
    try {
      await step3Mutation.mutateAsync(data);
      handleNext();
    } catch (error: any) {
      setSubmitError(error?.message || 'Failed to save step 3');
    }
  };

  const handleStep4Submit = async (data: Step4FormData) => {
    setSubmitError(null);
    try {
      await step4Mutation.mutateAsync(data);
      handleNext();
    } catch (error: any) {
      setSubmitError(error?.message || 'Failed to save step 4');
    }
  };

  const handleStep5Submit = async (data: Step5FormData) => {
    setSubmitError(null);
    try {
      await step5Mutation.mutateAsync(data);
      handleNext();
    } catch (error: any) {
      setSubmitError(error?.message || 'Failed to save step 5');
    }
  };

  const handleSubmit = async (data: { confirm_submission: boolean }) => {
    setSubmitError(null);
    try {
      await submitMutation.mutateAsync(data);
      router.push('/dashboard/admissions');
    } catch (error: any) {
      setSubmitError(error?.message || 'Failed to submit application');
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

        <Stepper activeStep={activeStep}>
          {STEP_LABELS.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

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
              onNext={handleNext}
              isLoading={false}
            />
          )}

          {activeStep === 6 && (
            <Step7Form
              applicationId={applicationId}
              applicationData={application}
              onSubmit={handleSubmit}
              isLoading={submitMutation.isPending}
              error={submitMutation.error?.message || null}
            />
          )}
        </Box>
      </Box>
    </Container>
  );
}
