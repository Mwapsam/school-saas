/**
 * Edit student page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Alert, CircularProgress } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useStudent, useUpdateStudent } from '@/features/students/hooks';
import { StudentForm } from '@/features/students/StudentForm';

export default function EditStudentPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: student, isLoading: studentLoading, error: studentError } = useStudent(params.id);
  const { mutateAsync: updateStudent, error: updateError } = useUpdateStudent(params.id);

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

  if (!can('students.update')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to edit students.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (studentLoading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4, display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (studentError || !student) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            Failed to load student: {studentError?.message || 'Not found'}
          </Alert>
        </Box>
      </Container>
    );
  }

  const handleSubmit = async (data: any) => {
    try {
      await updateStudent(data);
      router.push(`/dashboard/students/${student.id}`);
    } catch (err) {
      console.error('Update failed:', err);
      throw err;
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Edit Student: {student.full_name}
        </Typography>

        <Box sx={{ mt: 3 }}>
          <StudentForm
            student={student}
            error={updateError?.message}
            onSubmit={handleSubmit}
            onCancel={() => router.back()}
          />
        </Box>
      </Box>
    </Container>
  );
}
