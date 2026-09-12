/**
 * Multi-step admission application new application starter page using design system.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Box, Button, Alert, CircularProgress, Typography, Paper } from '@mui/material';
import { ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useStartApplication } from '@/features/multi-step-admission';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';

export default function StartMultiStepAdmissionPage() {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const startMutation = useStartApplication();

  if (!bootstrap) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (!isModuleEnabled('admissions') || !can('admissions.application.manage')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to create applications.</Alert>
      </Page>
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
    <Page>
      <PageHeader
        title="New Application"
        breadcrumbs={
          <Link href="/dashboard/admissions" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Admissions
            </Button>
          </Link>
        }
      />

      <PageContent>
        <Paper sx={{ p: 3, maxWidth: 600 }}>
          <Typography variant="h6" gutterBottom>
            Multi-Step Admission Application
          </Typography>
          <Typography variant="body1" color="textSecondary" paragraph>
            This is a comprehensive multi-step application form that will guide you through the admission process. You can save your progress and come back to complete it later.
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
        </Paper>
      </PageContent>
    </Page>
  );
}
