/**
 * Create new applicant enquiry page.
 *
 * Reference implementation using design system:
 * - Page wrapper for consistent layout
 * - PageHeader for title and breadcrumbs
 * - PageContent for form
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Alert, Button } from '@mui/material';
import { ChevronLeft as BackIcon } from '@mui/icons-material';
import Link from 'next/link';
import { useTenantStore } from '@/lib/tenant/store';
import { useCreateEnquiry, EnquiryForm, type EnquiryFormData } from '@/features/enquiries';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';

export default function CreateEnquiryPage() {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const createMutation = useCreateEnquiry();

  if (!bootstrap || !isModuleEnabled('admissions') || !can('admissions.enquiry.manage')) {
    return (
      <Page>
        <Alert severity="error">
          You do not have permission to create enquiries.
        </Alert>
      </Page>
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
    <Page>
      <PageHeader
        title="New Enquiry"
        description="Record a new student enquiry"
        breadcrumbs={
          <Link href="/dashboard/inquiries" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Enquiries
            </Button>
          </Link>
        }
      />

      <PageContent>
        {createMutation.error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {createMutation.error.message || 'Failed to create enquiry'}
          </Alert>
        )}

        <EnquiryForm
          onSubmit={handleSubmit}
          isLoading={createMutation.isPending}
          error={createMutation.error?.message || null}
        />
      </PageContent>
    </Page>
  );
}
