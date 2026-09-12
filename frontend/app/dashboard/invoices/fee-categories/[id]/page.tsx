/**
 * Fee category detail view page.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Container, Box, Typography, Button, Grid, Paper, CircularProgress, Alert } from '@mui/material';
import { Edit as EditIcon, ArrowBack as BackIcon } from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { useFeeCategory } from '@/features/finance/hooks';

export default function FeeCategoryDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled } = useTenantStore();
  const { data: feeCategory, isLoading, error } = useFeeCategory(params.id);

  if (!isModuleEnabled('finance') || !can('finance.fees.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view this fee category.
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

  if (error || !feeCategory) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            Failed to load fee category: {error?.message || 'Fee category not found'}
          </Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Button
              startIcon={<BackIcon />}
              onClick={() => router.back()}
              variant="text"
            >
              Back
            </Button>
            <Typography variant="h4" component="h1">
              {feeCategory.name}
            </Typography>
          </Box>

          {can('finance.fees.manage') && (
            <Link href={`/dashboard/invoices/fee-categories/${feeCategory.id}/edit`} passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<EditIcon />}>
                Edit
              </Button>
            </Link>
          )}
        </Box>

        {/* Details */}
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Fee Category Information
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                <Typography variant="body2" color="textSecondary">
                  Name:
                </Typography>
                <Typography variant="body2">{feeCategory.name}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Description:
                </Typography>
                <Typography variant="body2">{feeCategory.description || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">
                  Status:
                </Typography>
                <Box
                  sx={{
                    display: 'inline-block',
                    px: 1,
                    py: 0.5,
                    backgroundColor: feeCategory.is_active ? '#e8f5e9' : '#ffebee',
                    color: feeCategory.is_active ? '#2e7d32' : '#c62828',
                    borderRadius: 1,
                    fontSize: '0.85rem',
                    fontWeight: 500,
                    width: 'fit-content',
                  }}
                >
                  {feeCategory.is_active ? 'Active' : 'Inactive'}
                </Box>

                <Typography variant="body2" color="textSecondary">
                  Created:
                </Typography>
                <Typography variant="body2">
                  {new Date(feeCategory.created_at).toLocaleDateString()}
                </Typography>

                <Typography variant="body2" color="textSecondary">
                  Updated:
                </Typography>
                <Typography variant="body2">
                  {new Date(feeCategory.updated_at).toLocaleDateString()}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
}
