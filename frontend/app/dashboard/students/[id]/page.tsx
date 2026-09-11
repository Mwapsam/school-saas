/**
 * Student detail view page.
 */

'use client';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Container, Box, Typography, Button, Grid, Paper, CircularProgress, Alert } from '@mui/material';
import { Edit as EditIcon, ArrowBack as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useStudent } from '@/features/students/hooks';

export default function StudentDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: student, isLoading, error } = useStudent(params.id);

  if (!bootstrap) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Typography>Loading configuration...</Typography>
        </Box>
      </Container>
    );
  }

  if (!isModuleEnabled('academics') || !can('students.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view this student.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (isLoading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4, display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error || !student) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            Failed to load student: {error?.message || 'Student not found'}
          </Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Button
              startIcon={<BackIcon />}
              onClick={() => router.back()}
              variant="text"
            >
              Back
            </Button>
            <Typography variant="h4" component="h1">
              {student.full_name}
            </Typography>
          </Box>

          {can('students.update') && (
            <Link href={`/dashboard/students/${student.id}/edit`} passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<EditIcon />}>
                Edit
              </Button>
            </Link>
          )}
        </Box>

        {/* Details */}
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Personal Information
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Admission #:
                </Typography>
                <Typography variant="body2">{student.admission_number}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Date of Birth:
                </Typography>
                <Typography variant="body2">{student.date_of_birth}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Gender:
                </Typography>
                <Typography variant="body2">
                  {student.gender === 'M' ? 'Male' : student.gender === 'F' ? 'Female' : 'Other'}
                </Typography>

                <Typography variant="body2" color="textSecondary">
                  Email:
                </Typography>
                <Typography variant="body2">{student.email || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Phone:
                </Typography>
                <Typography variant="body2">{student.phone || '-'}</Typography>
              </Box>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Academic Information
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Batch:
                </Typography>
                <Typography variant="body2">{student.batch_name || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Status:
                </Typography>
                <Box
                  sx={{
                    display: 'inline-block',
                    px: 1,
                    py: 0.5,
                    backgroundColor: student.is_active ? '#e8f5e9' : '#ffebee',
                    color: student.is_active ? '#2e7d32' : '#c62828',
                    borderRadius: 1,
                    fontSize: '0.85rem',
                    fontWeight: 500,
                    width: 'fit-content',
                  }}
                >
                  {student.is_active ? 'Active' : 'Inactive'}
                </Box>

                <Typography variant="body2" color="textSecondary">
                  Created:
                </Typography>
                <Typography variant="body2">
                  {new Date(student.created_at).toLocaleDateString()}
                </Typography>

                <Typography variant="body2" color="textSecondary">
                  Updated:
                </Typography>
                <Typography variant="body2">
                  {new Date(student.updated_at).toLocaleDateString()}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
}
