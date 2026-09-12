/**
 * Employee detail page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Button, Box, Typography, Grid, Paper, Alert } from '@mui/material';
import { Edit as EditIcon, ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useEmployee } from '@/features/hr/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
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
        <ErrorState error={error} onRetry={() => refetch()} />
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
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Personal Information
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Employee ID:
                </Typography>
                <Typography variant="body2">{employee.employee_number}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Email:
                </Typography>
                <Typography variant="body2">{employee.email || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Phone:
                </Typography>
                <Typography variant="body2">{employee.mobile_phone || '-'}</Typography>
              </Box>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Employment Information
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Department:
                </Typography>
                <Typography variant="body2">{employee.department_name || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Position:
                </Typography>
                <Typography variant="body2">{employee.position_name || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Hire Date:
                </Typography>
                <Typography variant="body2">{employee.joining_date}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Status:
                </Typography>
                <Box>
                  <StatusBadge status={employee.status ? 'active' : 'inactive'} />
                </Box>

                <Typography variant="body2" color="textSecondary">
                  Created:
                </Typography>
                <Typography variant="body2">
                  {new Date(employee.created_at).toLocaleDateString()}
                </Typography>

                <Typography variant="body2" color="textSecondary">
                  Updated:
                </Typography>
                <Typography variant="body2">
                  {new Date(employee.updated_at).toLocaleDateString()}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </PageContent>
    </Page>
  );
}
