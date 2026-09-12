/**
 * Multi-step admission application wizard page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useTenantStore } from '@/lib/tenant/store';
import { AdmissionWizard } from '@/features/multi-step-admission';
import { Container, Box, Alert } from '@mui/material';

export default function MultiStepAdmissionPage({ params }: { params: { id: string } }) {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();

  if (!bootstrap) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="info">Loading...</Alert>
        </Box>
      </Container>
    );
  }

  if (!isModuleEnabled('admissions') || !can('admissions.application.manage')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to access this application.
          </Alert>
        </Box>
      </Container>
    );
  }

  return <AdmissionWizard applicationId={params.id} />;
}
