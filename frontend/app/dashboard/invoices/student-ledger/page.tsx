/**
 * Particular-wise Student Transaction Report — a per-student fee
 * reconciliation ledger (expected/paid/balance, split PTA vs tuition).
 * Ported from the legacy server-rendered
 * `core/finance/particular_wise_student_transaction_report.html` template
 * (`ParticularWiseStudentTransactionReportView`), which stays in place
 * unmodified. PDF export stays on that legacy view; this page supports CSV
 * export only.
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
  MenuItem,
  FormControlLabel,
  Switch,
  Button,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  CircularProgress,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import { useTenantStore } from '@/lib/tenant/store';
import {
  useStudentLedgerReport,
  useFeeCategoryList,
  useCourseOptions,
  useBatchOptions,
  getStudentLedgerCsvExportUrl,
  StudentLedgerReportParams,
} from '@/features/finance/hooks';

function formatAmount(value: number | undefined): string {
  return (value ?? 0).toFixed(2);
}

export default function StudentLedgerReportPage() {
  const { can, isModuleEnabled } = useTenantStore();

  const [studentStatus, setStudentStatus] = useState<'active' | 'all'>('active');
  const [classFilter, setClassFilter] = useState('all');
  const [batchFilter, setBatchFilter] = useState('all');
  const [feeAccount, setFeeAccount] = useState('all');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [withExpected, setWithExpected] = useState(false);

  const canView = can('finance.transactions.view');
  const moduleEnabled = isModuleEnabled('finance');

  const params: StudentLedgerReportParams = {
    student_status: studentStatus,
    class: classFilter,
    batch: batchFilter,
    fee_account: feeAccount,
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
    with_expected: withExpected,
  };

  const { data, isLoading, error } = useStudentLedgerReport(params, {
    enabled: moduleEnabled && canView,
  });
  const { data: feeCategoryData } = useFeeCategoryList({ page_size: 200 }, { enabled: moduleEnabled && canView });
  const { data: courseData } = useCourseOptions();
  const { data: batchData } = useBatchOptions();

  if (!moduleEnabled) {
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
          <Alert severity="error">You do not have permission to view the student ledger report.</Alert>
        </Box>
      </Container>
    );
  }

  const grandTotals = data?.grand_totals;

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2 }}>
          <Box>
            <Typography variant="h4" fontWeight={600} gutterBottom>
              Student Ledger
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Particular-wise per-student fee reconciliation — expected, paid, and balance amounts.
              {data?.academic_year_name ? ` Academic year: ${data.academic_year_name}.` : ''}
            </Typography>
          </Box>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            component="a"
            href={getStudentLedgerCsvExportUrl(params)}
          >
            Export CSV
          </Button>
        </Box>

        <Paper variant="outlined" sx={{ p: 2, my: 3 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={6} md={2}>
              <TextField
                select
                label="Student status"
                fullWidth
                size="small"
                value={studentStatus}
                onChange={(e) => setStudentStatus(e.target.value as 'active' | 'all')}
              >
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="all">All</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <TextField
                select
                label="Class"
                fullWidth
                size="small"
                value={classFilter}
                onChange={(e) => setClassFilter(e.target.value)}
              >
                <MenuItem value="all">All classes</MenuItem>
                {(courseData?.results ?? []).map((c) => (
                  <MenuItem key={c.id} value={c.id}>
                    {c.course_name}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <TextField
                select
                label="Batch"
                fullWidth
                size="small"
                value={batchFilter}
                onChange={(e) => setBatchFilter(e.target.value)}
                disabled={classFilter !== 'all'}
              >
                <MenuItem value="all">All batches</MenuItem>
                {(batchData?.results ?? []).map((b) => (
                  <MenuItem key={b.id} value={b.id}>
                    {b.name}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <TextField
                select
                label="Fee account"
                fullWidth
                size="small"
                value={feeAccount}
                onChange={(e) => setFeeAccount(e.target.value)}
              >
                <MenuItem value="all">All fee accounts</MenuItem>
                {(feeCategoryData?.results ?? []).map((fc) => (
                  <MenuItem key={fc.id} value={fc.id}>
                    {fc.name}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={6} sm={3} md={2}>
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
            <Grid item xs={6} sm={3} md={2}>
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
            <Grid item xs={12}>
              <FormControlLabel
                control={<Switch checked={withExpected} onChange={(e) => setWithExpected(e.target.checked)} />}
                label="With expected (show PTA / tuition breakdown)"
              />
            </Grid>
          </Grid>
        </Paper>

        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            Failed to load the student ledger report.
          </Alert>
        )}

        {isLoading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
        )}

        {data && (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Sl No.</TableCell>
                  <TableCell>Student Name</TableCell>
                  <TableCell>Batch Name(s)</TableCell>
                  <TableCell align="right">Expected</TableCell>
                  <TableCell align="right">Paid</TableCell>
                  <TableCell align="right">Balance</TableCell>
                  {withExpected && (
                    <>
                      <TableCell align="right">PTA Expected</TableCell>
                      <TableCell align="right">PTA Paid</TableCell>
                      <TableCell align="right">PTA Balance</TableCell>
                      <TableCell align="right">Tuition Expected</TableCell>
                      <TableCell align="right">Tuition Paid</TableCell>
                      <TableCell align="right">Tuition Balance</TableCell>
                    </>
                  )}
                </TableRow>
              </TableHead>
              <TableBody>
                {data.rows.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={withExpected ? 12 : 6} align="center">
                      No students match these filters.
                    </TableCell>
                  </TableRow>
                )}
                {data.rows.map((row, i) => (
                  <TableRow key={row.student_id}>
                    <TableCell>{i + 1}</TableCell>
                    <TableCell>{row.student_name}</TableCell>
                    <TableCell>{row.batch_name}</TableCell>
                    <TableCell align="right">{formatAmount(row.expected_amount)}</TableCell>
                    <TableCell align="right">{formatAmount(row.paid_amount)}</TableCell>
                    <TableCell align="right">{formatAmount(row.balance_amount)}</TableCell>
                    {withExpected && (
                      <>
                        <TableCell align="right">{formatAmount(row.pta_expected)}</TableCell>
                        <TableCell align="right">{formatAmount(row.pta_paid)}</TableCell>
                        <TableCell align="right">{formatAmount(row.pta_balance)}</TableCell>
                        <TableCell align="right">{formatAmount(row.tuition_expected)}</TableCell>
                        <TableCell align="right">{formatAmount(row.tuition_paid)}</TableCell>
                        <TableCell align="right">{formatAmount(row.tuition_balance)}</TableCell>
                      </>
                    )}
                  </TableRow>
                ))}
                {grandTotals && data.rows.length > 0 && (
                  <TableRow>
                    <TableCell />
                    <TableCell sx={{ fontWeight: 600 }}>Grand Total</TableCell>
                    <TableCell />
                    <TableCell align="right" sx={{ fontWeight: 600 }}>
                      {formatAmount(grandTotals.grand_expected)}
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>
                      {formatAmount(grandTotals.grand_paid)}
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>
                      {formatAmount(grandTotals.grand_balance)}
                    </TableCell>
                    {withExpected && (
                      <>
                        <TableCell align="right" sx={{ fontWeight: 600 }}>
                          {formatAmount(grandTotals.grand_pta_expected)}
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 600 }}>
                          {formatAmount(grandTotals.grand_pta_paid)}
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 600 }}>
                          {formatAmount(grandTotals.grand_pta_balance)}
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 600 }}>
                          {formatAmount(grandTotals.grand_tuition_expected)}
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 600 }}>
                          {formatAmount(grandTotals.grand_tuition_paid)}
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 600 }}>
                          {formatAmount(grandTotals.grand_tuition_balance)}
                        </TableCell>
                      </>
                    )}
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>
    </Container>
  );
}
