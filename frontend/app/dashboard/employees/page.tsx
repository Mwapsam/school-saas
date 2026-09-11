/**
 * Employees list page.
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Container, Box, Typography, Button, Alert, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useEmployeeList } from '@/features/hr/hooks';

export default function EmployeesPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useEmployeeList({ page, page_size: 10 });

  if (!bootstrap || !isModuleEnabled('hr') || !can('hr.employees.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view employees.
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
            Employees
          </Typography>
          {can('hr.employees.create') && (
            <Link href="/dashboard/employees/create" passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<AddIcon />}>
                New Employee
              </Button>
            </Link>
          )}
        </Box>

        {error && <Alert severity="error">{error.message}</Alert>}

        <TableContainer component={Paper}>
          <Table>
            <TableHead sx={{ backgroundColor: '#f5f5f5' }}>
              <TableRow>
                <TableCell>Employee ID</TableCell>
                <TableCell>Name</TableCell>
                <TableCell>Department</TableCell>
                <TableCell>Position</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data?.results?.map((emp) => (
                <TableRow key={emp.id} hover>
                  <TableCell>{emp.employee_id}</TableCell>
                  <TableCell>{emp.full_name}</TableCell>
                  <TableCell>{emp.department || '-'}</TableCell>
                  <TableCell>{emp.position || '-'}</TableCell>
                  <TableCell>{emp.is_active ? 'Active' : 'Inactive'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    </Container>
  );
}
