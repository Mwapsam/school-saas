/**
 * Hostel room detail view page (read-only, Phase 1).
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Button, Grid, Paper, CircularProgress, Alert } from '@mui/material';
import { ArrowBack as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useHostelRoom } from '@/features/hostel/hooks';

export default function HostelRoomDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: room, isLoading, error } = useHostelRoom(params.id);

  if (!bootstrap) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Typography>Loading configuration...</Typography>
        </Box>
      </Container>
    );
  }

  if (!isModuleEnabled('hostel') || !can('hostel.rooms.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view this hostel room.
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

  if (error || !room) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            Failed to load room: {error?.message || 'Room not found'}
          </Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <Button startIcon={<BackIcon />} onClick={() => router.back()} variant="text">
            Back
          </Button>
          <Typography variant="h4" component="h1">
            {room.hostel_name} — Room {room.room_number}
          </Typography>
        </Box>

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Room Information
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Hostel:
                </Typography>
                <Typography variant="body2">{room.hostel_name}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Room Number:
                </Typography>
                <Typography variant="body2">{room.room_number}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Capacity:
                </Typography>
                <Typography variant="body2">{room.capacity}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Current Occupancy:
                </Typography>
                <Typography variant="body2">{room.current_occupancy}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Created:
                </Typography>
                <Typography variant="body2">
                  {new Date(room.created_at).toLocaleDateString()}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
}
