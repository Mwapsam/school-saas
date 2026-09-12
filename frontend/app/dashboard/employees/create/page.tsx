/**
 * Create new employee page.
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
import { useCreateEmployee } from '@/features/hr/hooks';
import { EmployeeForm } from '@/features/hr/components/EmployeeForm';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';

export default function CreateEmployeePage() {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();
  const { mutateAsync: createEmployee, error } = useCreateEmployee();

  if (!isModuleEnabled('hr')) {
    return (
      <Page>
        <Alert severity="info">The HR module is not enabled.</Alert>
      </Page>
    );
  }

  if (!can('employees.create')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to create employees.</Alert>
      </Page>
    );
  }

  const handleSubmit = async (data: any) => {
    try {
      await createEmployee(data);
      router.push('/dashboard/employees');
    } catch (err) {
      console.error('Create failed:', err);
      throw err;
    }
  };

  return (
    <Page>
      <PageHeader
        title="Create New Employee"
        description="Add a new staff member to the system"
        breadcrumbs={
          <Link href="/dashboard/employees" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Employees
            </Button>
          </Link>
        }
      />

      <PageContent>
        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {(error as any)?.message || 'Failed to create employee'}
          </Alert>
        )}

        <EmployeeForm
          error={(error as any)?.message}
          onSubmit={handleSubmit}
          onCancel={() => router.back()}
        />
      </PageContent>
    </Page>
  );
}
