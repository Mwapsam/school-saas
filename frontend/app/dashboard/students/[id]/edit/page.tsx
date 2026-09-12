/**
 * Edit student page.
 *
 * Reference implementation using design system:
 * - Page wrapper for consistent layout
 * - PageHeader for title
 * - LoadingState, ErrorState for states
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Alert, Button } from '@mui/material';
import { ChevronLeft as BackIcon } from '@mui/icons-material';
import Link from 'next/link';
import { useTenantStore } from '@/lib/tenant/store';
import { useStudent, useUpdateStudent } from '@/features/students/hooks';
import { StudentForm } from '@/features/students/StudentForm';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';

export default function EditStudentPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: student, isLoading: studentLoading, error: studentError } = useStudent(params.id);
  const { mutateAsync: updateStudent, error: updateError } = useUpdateStudent(params.id);

  if (!bootstrap) {
    return <Page><LoadingState message="Loading configuration..." /></Page>;
  }

  if (!isModuleEnabled('academics')) {
    return (
      <Page>
        <Alert severity="info">
          The Academics module is not enabled.
        </Alert>
      </Page>
    );
  }

  if (!can('students.update')) {
    return (
      <Page>
        <Alert severity="error">
          You do not have permission to edit students.
        </Alert>
      </Page>
    );
  }

  if (studentLoading) {
    return <Page><LoadingState message="Loading student..." /></Page>;
  }

  if (studentError || !student) {
    return (
      <Page>
        <ErrorState
          title="Failed to load student"
          error={studentError?.message || 'Student not found'}
          onRetry={() => window.location.reload()}
        />
      </Page>
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
    <Page>
      <PageHeader
        title={`Edit Student: ${student.full_name}`}
        description="Update student enrollment and personal information"
        breadcrumbs={
          <Link href="/dashboard/students" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Students
            </Button>
          </Link>
        }
      />

      <PageContent>
        {updateError && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {updateError.message || 'Failed to update student'}
          </Alert>
        )}

        <StudentForm
          student={student}
          error={updateError?.message}
          onSubmit={handleSubmit}
          onCancel={() => router.back()}
        />
      </PageContent>
    </Page>
  );
}
