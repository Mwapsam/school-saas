/**
 * Global 404 not found page.
 */

'use client';

import Link from 'next/link';
import { Container, Box, Typography, Button } from '@mui/material';

export default function NotFound() {
  return (
    <Container maxWidth="sm">
      <Box sx={{ py: 12, display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
        <Typography variant="h1" component="h1" sx={{ mb: 2 }}>
          404
        </Typography>
        <Typography variant="h5" component="h2" sx={{ mb: 3 }}>
          Page Not Found
        </Typography>
        <Typography sx={{ mb: 4, color: 'text.secondary' }}>
          The page you&apos;re looking for doesn&apos;t exist.
        </Typography>
        <Link href="/dashboard" passHref legacyBehavior>
          <Button component="a" variant="contained">
            Go to Dashboard
          </Button>
        </Link>
      </Box>
    </Container>
  );
}
