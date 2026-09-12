/**
 * Edit employee page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button, Alert } from '@mui/material';
import { ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useEmployee, useUpdateEmployee } from '@/features/hr/hooks';
import { EmployeeForm } from '@/features/hr/components/EmployeeForm';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';

export default function EditEmployeePage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();
  const { data: employee, isLoading: employeeLoading, error: employeeError, refetch } = useEmployee(params.id);
  const { mutateAsync: updateEmployee, error: updateError } = useUpdateEmployee(params.id);

  if (!isModuleEnabled('hr')) {
    return (
      <Page>
        <Alert severity="info">The HR module is not enabled.</Alert>
      </Page>
    );
  }

  if (!can('employees.update')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to edit employees.</Alert>
      </Page>
    );
  }

  if (employeeLoading) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (employeeError || !employee) {
    return (
      <Page>
        <ErrorState error={employeeError || undefined} onRetry={() => refetch()} />
      </Page>
    );
  }

  const handleSubmit = async (data: any) => {
    try {
      await updateEmployee(data);
      router.push(`/dashboard/employees/${employee.id}`);
    } catch (err) {
      console.error('Update failed:', err);
      throw err;
    }
  };

  return (
    <Page>
      <PageHeader
        title={`Edit Employee: ${employee.full_name}`}
        breadcrumbs={
          <Link href={`/dashboard/employees/${employee.id}`} passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Employee
            </Button>
          </Link>
        }
      />

      <PageContent>
        {updateError && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {(updateError as any)?.message || 'Failed to update employee'}
          </Alert>
        )}

        <EmployeeForm
          employee={employee}
          error={(updateError as any)?.message}
          onSubmit={handleSubmit}
          onCancel={() => router.back()}
        />
      </PageContent>
    </Page>
  );
}
