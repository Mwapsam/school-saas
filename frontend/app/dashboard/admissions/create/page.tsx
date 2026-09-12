/**
 * Create new admission application page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Alert } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useCreateAdmissionApplication } from '@/features/admissions/hooks';
import { AdmissionForm } from '@/features/admissions/components/AdmissionForm';

export default function CreateAdmissionPage() {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();
  const { mutateAsync: createAdmission, error } = useCreateAdmissionApplication();

  if (!isModuleEnabled('admissions')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="info">The Admissions module is not enabled.</Alert>
        </Box>
      </Container>
    );
  }

  if (!can('admissions.create')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">You do not have permission to create admission applications.</Alert>
        </Box>
      </Container>
    );
  }

  const handleSubmit = async (data: any) => {
    try {
      await createAdmission(data);
      router.push('/dashboard/admissions');
    } catch (err) {
      console.error('Create failed:', err);
      throw err;
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          New Admission Application
        </Typography>

        <Box sx={{ mt: 3 }}>
          <AdmissionForm
            error={(error as any)?.message}
            onSubmit={handleSubmit}
            onCancel={() => router.back()}
          />
        </Box>
      </Box>
    </Container>
  );
}
