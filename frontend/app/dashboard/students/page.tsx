/**
 * Students list page.
 *
 * Displays:
 * - Table of all students
 * - Search and filter controls
 * - Pagination
 * - Create button
 * - Module/capability checks
 */

'use client';

export const dynamic = 'force-dynamic';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Button, Alert } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useStudentList, useDeleteStudent } from '@/features/students/hooks';
import { StudentTable } from '@/features/students/StudentTable';

export default function StudentsPage() {
  const router = useRouter();
  const { bootstrap, can, isModuleEnabled } = useTenantStore();

  // Pagination & filtering state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState('');
  const [ordering, setOrdering] = useState('-created_at');

  // Queries & mutations
  const { data, isLoading, error } = useStudentList({
    page,
    page_size: pageSize,
    search,
    ordering,
  });

  // Module/permission checks
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
            The Academics module is not enabled for your school. Contact your administrator to enable it.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (!can('students.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view students.
          </Alert>
        </Box>
      </Container>
    );
  }

  const handleDeleteStudent = async (id: string) => {
    try {
      const { mutateAsync } = useDeleteStudent(id);
      await mutateAsync();
      router.refresh();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Students
          </Typography>
          {can('students.create') && (
            <Link href="/dashboard/students/create" passHref legacyBehavior>
              <Button
                component="a"
                variant="contained"
                startIcon={<AddIcon />}
              >
                New Student
              </Button>
            </Link>
          )}
        </Box>

        {/* Table */}
        <StudentTable
          students={data?.results}
          loading={isLoading}
          error={error}
          total={data?.count || 0}
          page={page}
          pageSize={pageSize}
          search={search}
          ordering={ordering}
          onPageChange={setPage}
          onPageSizeChange={(size) => {
            setPageSize(size);
            setPage(1); // Reset to first page
          }}
          onSearchChange={(s) => {
            setSearch(s);
            setPage(1); // Reset to first page
          }}
          onOrderingChange={setOrdering}
          onDelete={can('students.delete') ? handleDeleteStudent : undefined}
          canEdit={can('students.update')}
          canDelete={can('students.delete')}
        />
      </Box>
    </Container>
  );
}
