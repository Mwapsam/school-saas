/**
 * Create new admission application page.
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
import { useCreateAdmissionApplication } from '@/features/admissions/hooks';
import { AdmissionForm } from '@/features/admissions/components/AdmissionForm';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';

export default function CreateAdmissionPage() {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();
  const { mutateAsync: createAdmission, error } = useCreateAdmissionApplication();

  if (!isModuleEnabled('admissions')) {
    return (
      <Page>
        <Alert severity="info">The Admissions module is not enabled.</Alert>
      </Page>
    );
  }

  if (!can('admissions.create')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to create admission applications.</Alert>
      </Page>
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
    <Page>
      <PageHeader
        title="New Admission Application"
        description="Create a new admission application in the system"
        breadcrumbs={
          <Link href="/dashboard/admissions" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Applications
            </Button>
          </Link>
        }
      />

      <PageContent>
        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {(error as any)?.message || 'Failed to create application'}
          </Alert>
        )}

        <AdmissionForm
          error={(error as any)?.message}
          onSubmit={handleSubmit}
          onCancel={() => router.back()}
        />
      </PageContent>
    </Page>
  );
}
