/**
 * Edit employee page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Alert, CircularProgress } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useEmployee, useUpdateEmployee } from '@/features/hr/hooks';
import { EmployeeForm } from '@/features/hr/components/EmployeeForm';

export default function EditEmployeePage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();
  const { data: employee, isLoading: employeeLoading, error: employeeError } = useEmployee(params.id);
  const { mutateAsync: updateEmployee, error: updateError } = useUpdateEmployee(params.id);

  if (!isModuleEnabled('hr')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="info">The HR module is not enabled.</Alert>
        </Box>
      </Container>
    );
  }

  if (!can('employees.update')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">You do not have permission to edit employees.</Alert>
        </Box>
      </Container>
    );
  }

  if (employeeLoading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4, display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (employeeError || !employee) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            Failed to load employee: {(employeeError as any)?.message || 'Not found'}
          </Alert>
        </Box>
      </Container>
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
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Edit Employee: {employee.full_name}
        </Typography>

        <Box sx={{ mt: 3 }}>
          <EmployeeForm
            employee={employee}
            error={(updateError as any)?.message}
            onSubmit={handleSubmit}
            onCancel={() => router.back()}
          />
        </Box>
      </Box>
    </Container>
  );
}
