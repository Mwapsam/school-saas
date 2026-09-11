/**
 * Invoices list page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Button, Alert } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useInvoiceList, useDeleteInvoice } from '@/features/finance/hooks';
import { InvoiceTable } from '@/features/finance/InvoiceTable';

export default function InvoicesPage() {
  const router = useRouter();
  const { bootstrap, can, isModuleEnabled } = useTenantStore();

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState('');
  const [ordering, setOrdering] = useState('-created_at');

  const { data, isLoading, error } = useInvoiceList({
    page,
    page_size: pageSize,
    search,
    ordering,
  });

  if (!bootstrap) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Typography>Loading configuration...</Typography>
        </Box>
      </Container>
    );
  }

  if (!isModuleEnabled('finance')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="info">
            The Finance module is not enabled. Contact your administrator.
          </Alert>
        </Box>
      </Container>
    );
  }

  if (!can('finance.invoices.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view invoices.
          </Alert>
        </Box>
      </Container>
    );
  }

  const handleDeleteInvoice = async (id: string) => {
    try {
      const { mutateAsync } = useDeleteInvoice(id);
      await mutateAsync();
      router.refresh();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Invoices
          </Typography>
          {can('finance.invoices.create') && (
            <Link href="/dashboard/invoices/create" passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<AddIcon />}>
                New Invoice
              </Button>
            </Link>
          )}
        </Box>

        <InvoiceTable
          invoices={data?.results}
          loading={isLoading}
          error={error}
          total={data?.count || 0}
          page={page}
          pageSize={pageSize}
          search={search}
          ordering={ordering}
          onPageChange={setPage}
          onPageSizeChange={(size) => {
            setPageSize(size);
            setPage(1);
          }}
          onSearchChange={(s) => {
            setSearch(s);
            setPage(1);
          }}
          onOrderingChange={setOrdering}
          onDelete={can('finance.invoices.delete') ? handleDeleteInvoice : undefined}
          canEdit={can('finance.invoices.update')}
          canDelete={can('finance.invoices.delete')}
        />
      </Box>
    </Container>
  );
}
