/**
 * Admissions applications list page.
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Container, Box, Typography, Button, Alert, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Chip } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useAdmissionApplicationList } from '@/features/admissions/hooks';

export default function AdmissionsPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useAdmissionApplicationList({ page, page_size: 10 });

  if (!bootstrap || !isModuleEnabled('admissions') || !can('admissions.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view admissions.
          </Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Admission Applications
          </Typography>
          {can('admissions.create') && (
            <Link href="/dashboard/admissions/create" passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<AddIcon />}>
                New Application
              </Button>
            </Link>
          )}
        </Box>

        {error && <Alert severity="error">{error.message}</Alert>}

        <TableContainer component={Paper}>
          <Table>
            <TableHead sx={{ backgroundColor: '#f5f5f5' }}>
              <TableRow>
                <TableCell>Application #</TableCell>
                <TableCell>Student Name</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data?.results?.map((app) => (
                <TableRow key={app.id} hover>
                  <TableCell>{app.application_number}</TableCell>
                  <TableCell>{app.student_name}</TableCell>
                  <TableCell>{app.email}</TableCell>
                  <TableCell>
                    <Chip
                      label={app.status}
                      color={app.status === 'approved' ? 'success' : app.status === 'rejected' ? 'error' : 'default'}
                      size="small"
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    </Container>
  );
}
