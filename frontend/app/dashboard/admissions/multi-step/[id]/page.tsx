/**
 * Multi-step admission application wizard page using design system.
 */

'use client';

export const dynamic = 'force-dynamic';

import { Alert } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { AdmissionWizard } from '@/features/multi-step-admission';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';

export default function MultiStepAdmissionPage({ params }: { params: { id: string } }) {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();

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
        <Alert severity="error">You do not have permission to access this application.</Alert>
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader title="Admission Application" description="Complete the multi-step application form" />
      <PageContent>
        <AdmissionWizard applicationId={params.id} />
      </PageContent>
    </Page>
  );
}
