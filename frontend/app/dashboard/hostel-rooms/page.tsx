/**
 * Hostel rooms list page.
 */

'use client';


import { Container, Box, Typography, Alert, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useHostelRoomList } from '@/features/hostel/hooks';

export default function HostelRoomsPage() {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data, error } = useHostelRoomList({ page: 1, page_size: 10 });

  if (!bootstrap || !isModuleEnabled('hostel') || !can('hostel.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">You do not have permission to view hostel.</Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Hostel Rooms
        </Typography>

        {error && <Alert severity="error">{error.message}</Alert>}

        <TableContainer component={Paper}>
          <Table>
            <TableHead sx={{ backgroundColor: '#f5f5f5' }}>
              <TableRow>
                <TableCell>Hostel</TableCell>
                <TableCell>Room Number</TableCell>
                <TableCell>Capacity</TableCell>
                <TableCell>Occupancy</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data?.results?.map((room) => (
                <TableRow key={room.id} hover>
                  <TableCell>{room.hostel_name}</TableCell>
                  <TableCell>{room.room_number}</TableCell>
                  <TableCell>{room.capacity}</TableCell>
                  <TableCell>{room.current_occupancy} / {room.capacity}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    </Container>
  );
}
