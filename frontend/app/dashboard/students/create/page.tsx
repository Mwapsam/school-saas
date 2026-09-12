/**
 * Create new student page.
 *
 * Reference implementation using design system components:
 * - Page wrapper for consistent layout
 * - PageHeader for title and description
 * - PageContent for form
 * - Form validation with react-hook-form + zod
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Alert } from '@mui/material';
import { ChevronLeft as BackIcon } from '@mui/icons-material';
import Link from 'next/link';
import { useTenantStore } from '@/lib/tenant/store';
import { useCreateStudent } from '@/features/students/hooks';
import { StudentForm } from '@/features/students/StudentForm';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { Button } from '@mui/material';

export default function CreateStudentPage() {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { mutateAsync: createStudent, error } = useCreateStudent();

  if (!bootstrap) {
    return (
      <Page>
        <Alert severity="info">Loading configuration...</Alert>
      </Page>
    );
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

  if (!can('students.create')) {
    return (
      <Page>
        <Alert severity="error">
          You do not have permission to create students.
        </Alert>
      </Page>
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
    <Page>
      <PageHeader
        title="Add Student"
        description="Create a new student record in the system."
        breadcrumbs={
          <Link href="/dashboard/students" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Students
            </Button>
          </Link>
        }
      />

      <PageContent>
        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error.message || 'Failed to create student'}
          </Alert>
        )}

        <StudentForm
          error={error?.message}
          onSubmit={handleSubmit}
          onCancel={() => router.back()}
        />
      </PageContent>
    </Page>
  );
}
