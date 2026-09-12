/**
 * Multi-step admission application new application starter page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Button, Alert, CircularProgress } from '@mui/material';
import { ArrowBack as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useStartApplication } from '@/features/multi-step-admission';

export default function StartMultiStepAdmissionPage() {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const startMutation = useStartApplication();

  if (!bootstrap) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Typography>Loading configuration...</Typography>
        </Box>
      </Container>
    );
  }

  if (!isModuleEnabled('admissions') || !can('admissions.application.manage')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to create applications.
          </Alert>
        </Box>
      </Container>
    );
  }

  const handleStartApplication = async () => {
    try {
      const response = await startMutation.mutateAsync();
      router.push(`/dashboard/admissions/multi-step/${response.id}`);
    } catch (error) {
      console.error('Failed to start application:', error);
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <Button startIcon={<BackIcon />} onClick={() => router.back()} variant="text">
            Back
          </Button>
          <Typography variant="h4" component="h1">
            New Application
          </Typography>
        </Box>

        <Box sx={{ mt: 4, p: 3, border: '1px solid #e0e0e0', borderRadius: 1 }}>
          <Typography variant="h6" gutterBottom>
            Multi-Step Admission Application
          </Typography>
          <Typography variant="body1" color="textSecondary" paragraph>
            This is a comprehensive multi-step application form that will guide you through the admission process.
            You can save your progress and come back to complete it later.
          </Typography>

          <Typography variant="h6" sx={{ mt: 3 }} gutterBottom>
            Application Steps:
          </Typography>
          <Typography variant="body2" component="ol" sx={{ pl: 2 }}>
            <li>Academic Year & Course Selection</li>
            <li>Personal Details (Name, Date of Birth, etc.)</li>
            <li>Contact Information (Address, Phone, Email)</li>
            <li>Guardian Information</li>
            <li>Health Information & Declaration</li>
            <li>Document Upload</li>
            <li>Review & Final Submission</li>
          </Typography>

          <Button
            variant="contained"
            size="large"
            onClick={handleStartApplication}
            disabled={startMutation.isPending}
            sx={{ mt: 4 }}
            startIcon={startMutation.isPending && <CircularProgress size={20} />}
          >
            {startMutation.isPending ? 'Starting Application...' : 'Start New Application'}
          </Button>

          {startMutation.error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {startMutation.error.message || 'Failed to start application'}
            </Alert>
          )}
        </Box>
      </Box>
    </Container>
  );
}
