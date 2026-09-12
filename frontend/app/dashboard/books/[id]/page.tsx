/**
 * Library book detail page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Button, Box, Typography, Grid, Paper, Alert } from '@mui/material';
import { ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useBook } from '@/features/library/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';

export default function LibraryBookDetailPage({ params }: { params: { id: string } }) {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: book, isLoading, error, refetch } = useBook(params.id);

  if (!bootstrap) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (!isModuleEnabled('library') || !can('library.view')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to view this book.</Alert>
      </Page>
    );
  }

  if (isLoading) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (error || !book) {
    return (
      <Page>
        <ErrorState error={error} onRetry={() => refetch()} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title={book.title}
        description={`by ${book.author}`}
        breadcrumbs={
          <Link href="/dashboard/books" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Books
            </Button>
          </Link>
        }
      />

      <PageContent>
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
      </PageContent>
    </Page>
  );
}
