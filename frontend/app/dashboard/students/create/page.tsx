/**
 * Create new student page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Alert } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useCreateStudent } from '@/features/students/hooks';
import { StudentForm } from '@/features/students/StudentForm';

export default function CreateStudentPage() {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { mutateAsync: createStudent, error } = useCreateStudent();

  if (!bootstrap) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Typography>Loading configuration...</Typography>
        </Box>
      </Container>
    );
  }

  if (!isModuleEnabled('academics')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="info">
            The Academics module is not enabled.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (!can('students.create')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to create students.
          </Alert>
        </Box>
      </Container>
    );
  }

  const handleSubmit = async (data: any) => {
    try {
      await createStudent(data);
      router.push('/dashboard/students');
    } catch (err) {
      console.error('Create failed:', err);
      throw err;
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Create New Student
        </Typography>

        <Box sx={{ mt: 3 }}>
          <StudentForm
            error={error?.message}
            onSubmit={handleSubmit}
            onCancel={() => router.back()}
          />
        </Box>
      </Box>
    </Container>
  );
}
