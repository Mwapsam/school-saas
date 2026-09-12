/**
 * Student detail page.
 *
 * Reference implementation using design system:
 * - Page wrapper for consistent layout
 * - PageHeader for title and back button
 * - ErrorState, LoadingState for states
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Box, Button, Grid, Paper, Alert, Typography } from '@mui/material';
import { Edit as EditIcon, ArrowBack as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useStudent } from '@/features/students/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';

export default function StudentDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: student, isLoading, error } = useStudent(params.id);

  if (!bootstrap) {
    return <Page><LoadingState message="Loading configuration..." /></Page>;
  }

  if (!isModuleEnabled('academics') || !can('students.view')) {
    return (
      <Page>
        <Alert severity="error">
          You do not have permission to view this student.
        </Alert>
      </Page>
    );
  }

  if (isLoading) {
    return <Page><LoadingState message="Loading student..." /></Page>;
  }

  if (error || !student) {
    return (
      <Page>
        <ErrorState
          title="Failed to load student"
          error={error?.message || 'Student not found'}
          onRetry={() => window.location.reload()}
        />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title={student.full_name}
        description="Student enrollment and personal information"
        actions={
          can('students.update') && (
            <Link href={`/dashboard/students/${student.id}/edit`} passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<EditIcon />}>
                Edit
              </Button>
            </Link>
          )
        }
        breadcrumbs={
          <Link href="/dashboard/students" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Students
            </Button>
          </Link>
        }
      />

      <PageContent>

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
                <Typography variant="body2">{student.admission_no}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Admission Date:
                </Typography>
                <Typography variant="body2">{student.admission_date}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Date of Birth:
                </Typography>
                <Typography variant="body2">{student.date_of_birth}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Age:
                </Typography>
                <Typography variant="body2">{student.age ?? '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Gender:
                </Typography>
                <Typography variant="body2">
                  {student.gender.charAt(0).toUpperCase() + student.gender.slice(1)}
                </Typography>

                <Typography variant="body2" color="textSecondary">
                  Email:
                </Typography>
                <Typography variant="body2">{student.email || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Phone 1:
                </Typography>
                <Typography variant="body2">{student.phone1 || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Phone 2:
                </Typography>
                <Typography variant="body2">{student.phone2 || '-'}</Typography>
              </Box>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Address
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Address:
                </Typography>
                <Typography variant="body2">
                  {[student.address_line1, student.address_line2].filter(Boolean).join(', ') || '-'}
                </Typography>

                <Typography variant="body2" color="textSecondary">
                  City / State:
                </Typography>
                <Typography variant="body2">
                  {[student.city, student.state].filter(Boolean).join(', ') || '-'}
                </Typography>

                <Typography variant="body2" color="textSecondary">
                  Pin Code:
                </Typography>
                <Typography variant="body2">{student.pin_code || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Country:
                </Typography>
                <Typography variant="body2">{student.country_name || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Nationality:
                </Typography>
                <Typography variant="body2">{student.nationality_name || '-'}</Typography>
              </Box>
            </Paper>

            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Academic Information
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Batches:
                </Typography>
                <Typography variant="body2">
                  {student.batches.length > 0
                    ? student.batches.map((b) => b.name).join(', ')
                    : '-'}
                </Typography>

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

            {student.guardians.length > 0 && (
              <Paper sx={{ p: 2, mt: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Guardians
                </Typography>
                <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                  {student.guardians.map((g) => (
                    <Box key={g.id} sx={{ display: 'contents' }}>
                      <Typography variant="body2" color="textSecondary">
                        {g.relationship}:
                      </Typography>
                      <Typography variant="body2">
                        {g.name} {g.phone ? `(${g.phone})` : ''}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </Paper>
            )}
          </Grid>
        </Grid>
      </PageContent>
    </Page>
  );
}
