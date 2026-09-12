/**
 * Library book detail page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { Button, Grid, Alert } from '@mui/material';
import { ChevronLeft as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useBook } from '@/features/library/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { SectionCard, DetailField } from '@/components/page';
import { StatusBadge } from '@/components/data/StatusBadge';
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
        <ErrorState error={error || undefined} onRetry={() => refetch()} />
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
            <SectionCard title="Book Information">
              <DetailField label="Title" value={book.title} />
              <DetailField label="Author" value={book.author} truncate />
              <DetailField label="ISBN" value={book.isbn} />
              <DetailField label="Category" value={book.category_name || '-'} />
              <DetailField label="Total Copies" value={book.total_copies} />
              <DetailField
                label="Available Copies"
                value={
                  book.available_copies === 0 ? (
                    <StatusBadge label="Out of Stock" status="error" />
                  ) : (
                    `${book.available_copies} / ${book.total_copies}`
                  )
                }
              />
              <DetailField label="Created" value={new Date(book.created_at).toLocaleDateString()} />
            </SectionCard>
          </Grid>
        </Grid>
      </PageContent>
    </Page>
  );
}
