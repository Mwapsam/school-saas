/**
 * Create new employee page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Alert } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useCreateEmployee } from '@/features/hr/hooks';
import { EmployeeForm } from '@/features/hr/components/EmployeeForm';

export default function CreateEmployeePage() {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();
  const { mutateAsync: createEmployee, error } = useCreateEmployee();

  if (!isModuleEnabled('hr')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="info">The HR module is not enabled.</Alert>
        </Box>
      </Container>
    );
  }

  if (!can('employees.create')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">You do not have permission to create employees.</Alert>
        </Box>
      </Container>
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
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Create New Employee
        </Typography>

        <Box sx={{ mt: 3 }}>
          <EmployeeForm
            error={(error as any)?.message}
            onSubmit={handleSubmit}
            onCancel={() => router.back()}
          />
        </Box>
      </Box>
    </Container>
  );
}
