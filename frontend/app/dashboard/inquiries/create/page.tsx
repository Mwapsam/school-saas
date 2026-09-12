/**
 * Create new applicant enquiry page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Button, Alert } from '@mui/material';
import { ArrowBack as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useCreateEnquiry, EnquiryForm, type EnquiryFormData } from '@/features/enquiries';

export default function CreateEnquiryPage() {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const createMutation = useCreateEnquiry();

  if (!bootstrap || !isModuleEnabled('admissions') || !can('admissions.enquiry.manage')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to create enquiries.
          </Alert>
        </Box>
      </Container>
    );
  }

  const handleSubmit = async (data: EnquiryFormData) => {
    try {
      await createMutation.mutateAsync(data);
      router.push('/dashboard/inquiries');
    } catch (error) {
      console.error('Failed to create enquiry:', error);
    }
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <Button startIcon={<BackIcon />} onClick={() => router.back()} variant="text">
            Back
          </Button>
          <Typography variant="h4" component="h1">
            New Enquiry
          </Typography>
        </Box>

        <Box sx={{ mt: 3 }}>
          <EnquiryForm
            onSubmit={handleSubmit}
            isLoading={createMutation.isPending}
            error={createMutation.error?.message || null}
          />
        </Box>
      </Box>
    </Container>
  );
}
