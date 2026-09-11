/**
 * Transport routes list page.
 */

'use client';

import { Container, Box, Typography, Alert, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useTransportRouteList } from '@/features/transport/hooks';

export default function RoutesPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data, error } = useTransportRouteList({ page: 1, page_size: 10 });

  if (!bootstrap || !isModuleEnabled('transport') || !can('transport.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">You do not have permission to view transport routes.</Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Transport Routes
        </Typography>

        {error && <Alert severity="error">{error.message}</Alert>}

        <TableContainer component={Paper}>
          <Table>
            <TableHead sx={{ backgroundColor: '#f5f5f5' }}>
              <TableRow>
                <TableCell>Route Name</TableCell>
                <TableCell>Code</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Vehicle</TableCell>
                <TableCell>Students</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data?.results?.map((route) => (
                <TableRow key={route.id} hover>
                  <TableCell>{route.name}</TableCell>
                  <TableCell>{route.code}</TableCell>
                  <TableCell>{route.route_type}</TableCell>
                  <TableCell>{route.vehicle_name}</TableCell>
                  <TableCell>{route.student_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    </Container>
  );
}
