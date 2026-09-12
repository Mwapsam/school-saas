/**
 * Day Book report page — per-day, per-payment-mode cash reconciliation.
 * Ported from the legacy server-rendered `core/finance/day_book.html`
 * template (`DayBookReportView`), which stays in place unmodified.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useState } from 'react';
import {
  Container,
  Box,
  Typography,
  Alert,
  Paper,
  Grid,
  TextField,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  CircularProgress,
} from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';
import { useDayBookReport } from '@/features/finance/hooks';

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoStr(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function formatAmount(value: number | undefined): string {
  return (value ?? 0).toFixed(2);
}

function StatBlock({ label, value }: { label: string; value: string }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, height: '100%' }}>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h5" fontWeight={600}>
        {value}
      </Typography>
    </Paper>
  );
}

export default function DayBookReportPage() {
  const { can, isModuleEnabled } = useTenantStore();
  const [fromDate, setFromDate] = useState(daysAgoStr(7));
  const [toDate, setToDate] = useState(todayStr());

  const canView = can('finance.transactions.view');
  const { data, isLoading, error } = useDayBookReport(fromDate, toDate, {
    enabled: isModuleEnabled('finance') && canView,
  });

  if (!isModuleEnabled('finance')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="info">The Finance module is not enabled. Contact your administrator.</Alert>
        </Box>
      </Container>
    );
  }

  if (!canView) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">You do not have permission to view the Day Book.</Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" fontWeight={600} gutterBottom>
          Day Book
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Per-day cash/bank reconciliation across fee collection and general-ledger transactions.
        </Typography>

        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={4} md={3}>
              <TextField
                label="From date"
                type="date"
                fullWidth
                size="small"
                InputLabelProps={{ shrink: true }}
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
              />
            </Grid>
            <Grid item xs={12} sm={4} md={3}>
              <TextField
                label="To date"
                type="date"
                fullWidth
                size="small"
                InputLabelProps={{ shrink: true }}
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
              />
            </Grid>
          </Grid>
        </Paper>

        {fromDate > toDate && (
          <Alert severity="warning" sx={{ mb: 3 }}>
            From date must not be after to date.
          </Alert>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            Failed to load the Day Book report.
          </Alert>
        )}

        {isLoading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
        )}

        {data && (
          <>
            <Grid container spacing={2} sx={{ mb: 3 }}>
              <Grid item xs={12} sm={4}>
                <StatBlock label="Total In" value={formatAmount(data.total_in)} />
              </Grid>
              <Grid item xs={12} sm={4}>
                <StatBlock label="Total Out" value={formatAmount(data.total_out)} />
              </Grid>
              <Grid item xs={12} sm={4}>
                <StatBlock label="Closing Balance" value={formatAmount(data.closing_balance)} />
              </Grid>
            </Grid>

            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Date</TableCell>
                    <TableCell align="right">Opening</TableCell>
                    <TableCell align="right">Total In</TableCell>
                    <TableCell align="right">Total Out</TableCell>
                    <TableCell align="right">Closing</TableCell>
                    <TableCell>By Mode</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.days.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} align="center">
                        No transactions in this date range.
                      </TableCell>
                    </TableRow>
                  )}
                  {data.days.map((day) => (
                    <TableRow key={day.date}>
                      <TableCell>{day.date}</TableCell>
                      <TableCell align="right">{formatAmount(day.opening_balance)}</TableCell>
                      <TableCell align="right">{formatAmount(day.total_in)}</TableCell>
                      <TableCell align="right">{formatAmount(day.total_out)}</TableCell>
                      <TableCell align="right">{formatAmount(day.closing_balance)}</TableCell>
                      <TableCell>
                        {Object.entries(day.by_mode)
                          .map(([mode, totals]) => `${mode}: +${formatAmount(totals.in)}/-${formatAmount(totals.out)}`)
                          .join(', ') || '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </>
        )}
      </Box>
    </Container>
  );
}
