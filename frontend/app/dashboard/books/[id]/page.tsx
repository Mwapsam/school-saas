/**
 * Library book detail view page (read-only, Phase 1).
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Button, Grid, Paper, CircularProgress, Alert } from '@mui/material';
import { ArrowBack as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useBook } from '@/features/library/hooks';

export default function LibraryBookDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: book, isLoading, error } = useBook(params.id);

  if (!bootstrap) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Typography>Loading configuration...</Typography>
        </Box>
      </Container>
    );
  }

  if (!isModuleEnabled('library') || !can('library.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view this book.
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

  if (error || !book) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            Failed to load book: {error?.message || 'Book not found'}
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
            {book.title}
          </Typography>
        </Box>

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Book Information
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Title:
                </Typography>
                <Typography variant="body2">{book.title}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Author:
                </Typography>
                <Typography variant="body2">{book.author}</Typography>

                <Typography variant="body2" color="textSecondary">
                  ISBN:
                </Typography>
                <Typography variant="body2">{book.isbn}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Category:
                </Typography>
                <Typography variant="body2">{book.category_name || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Total Copies:
                </Typography>
                <Typography variant="body2">{book.total_copies}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Available Copies:
                </Typography>
                <Typography variant="body2">{book.available_copies}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Created:
                </Typography>
                <Typography variant="body2">
                  {new Date(book.created_at).toLocaleDateString()}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
}
