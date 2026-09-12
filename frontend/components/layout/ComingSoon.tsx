'use client';

import { Container, Box, Paper, Typography } from '@mui/material';
import ConstructionIcon from '@mui/icons-material/Construction';

export interface ComingSoonProps {
  title?: string;
}

/**
 * Lightweight placeholder for sidebar links whose backend/API isn't ported
 * yet (strangler-fig Phase 2 items). Avoids a raw 404 while still being
 * discoverable from navigation.
 */
export function ComingSoon({ title = 'Coming Soon' }: ComingSoonProps) {
  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          {title}
        </Typography>

        <Paper
          variant="outlined"
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 2,
            py: 8,
            px: 3,
            textAlign: 'center',
          }}
        >
          <ConstructionIcon sx={{ fontSize: 48, color: 'text.secondary' }} />
          <Typography variant="h6" color="text.secondary">
            This feature is coming soon
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 420 }}>
            We&apos;re working on bringing this to the dashboard. Check back later.
          </Typography>
        </Paper>
      </Box>
    </Container>
  );
}
