/**
 * Employee detail page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Button, Grid, Alert } from '@mui/material';
import { Edit as EditIcon, ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useEmployee } from '@/features/hr/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { SectionCard, DetailField } from '@/components/page';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { StatusBadge } from '@/components/data/StatusBadge';

export default function EmployeeDetailPage({ params }: { params: { id: string } }) {
  const { can, isModuleEnabled } = useTenantStore();
  const { data: employee, isLoading, error, refetch } = useEmployee(params.id);

  if (!isModuleEnabled('hr') || !can('employees.view')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to view this employee.</Alert>
      </Page>
    );
  }

  if (isLoading) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (error || !employee) {
    return (
      <Page>
        <ErrorState error={error || undefined} onRetry={() => refetch()} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title={employee.full_name}
        description={`${employee.position_name || 'Position'} • ${employee.department_name || 'Department'}`}
        breadcrumbs={
          <Link href="/dashboard/employees" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Employees
            </Button>
          </Link>
        }
        actions={
          can('employees.update') && (
            <Link href={`/dashboard/employees/${employee.id}/edit`} passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<EditIcon />}>
                Edit
              </Button>
            </Link>
          )
        }
      />

      <PageContent>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <SectionCard title="Personal Information">
              <DetailField label="Employee ID" value={employee.employee_number} />
              <DetailField label="Email" value={employee.email || '-'} truncate />
              <DetailField label="Phone" value={employee.mobile_phone || '-'} truncate />
            </SectionCard>
          </Grid>

          <Grid item xs={12} md={6}>
            <SectionCard title="Employment Information">
              <DetailField label="Department" value={employee.department_name || '-'} />
              <DetailField label="Position" value={employee.position_name || '-'} />
              <DetailField label="Hire Date" value={employee.joining_date} />
              <DetailField
                label="Status"
                value={
                  <StatusBadge
                    label={employee.status ? 'Active' : 'Inactive'}
                    status={employee.status ? 'success' : 'error'}
                  />
                }
              />
              <DetailField label="Created" value={new Date(employee.created_at).toLocaleDateString()} />
              <DetailField label="Updated" value={new Date(employee.updated_at).toLocaleDateString()} />
            </SectionCard>
          </Grid>
        </Grid>
      </PageContent>
    </Page>
  );
}
