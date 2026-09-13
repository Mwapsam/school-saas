'use client';

import React, { useState } from 'react';
import {
  Container,
  Grid,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Card,
  CardContent,
  LinearProgress,
  Stack,
  Typography,
  Box,
} from '@mui/material';

import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { SectionCard } from '@/components/page/SectionCard';

import { useAdmissionReport } from '@/features/admission-management/hooks';

const COLORS = ['#2196F3', '#4CAF50', '#FF9800', '#F44336', '#9C27B0'];

const AdmissionReportPage: React.FC = () => {
  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [academicYearFilter, setAcademicYearFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Query
  const { data: report, isLoading, error } = useAdmissionReport({
    status: statusFilter,
    academic_year: academicYearFilter,
    date_from: dateFrom,
    date_to: dateTo,
  });

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState title="Failed to load report" description="Please try again" />;

  const handleClearFilters = () => {
    setStatusFilter('');
    setAcademicYearFilter('');
    setDateFrom('');
    setDateTo('');
  };

  const approvalRate = report?.approval_rate || 0;
  const stats = report?.statistics || {};
  const statusBreakdown = report?.status_breakdown || [];
  const courseBreakdown = report?.course_breakdown || [];

  return (
    <Page>
      <PageHeader title="Admission Report" description="View admission statistics and breakdowns" />

      <PageContent>
        <Container maxWidth="lg">
          {/* Filters */}
          <SectionCard title="Filters">
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 2 }}>
              <FormControl sx={{ minWidth: 200 }}>
                <InputLabel>Status</InputLabel>
                <Select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  label="Status"
                >
                  <MenuItem value="">All Statuses</MenuItem>
                  <MenuItem value="submitted">Submitted</MenuItem>
                  <MenuItem value="under_review">Under Review</MenuItem>
                  <MenuItem value="approved">Approved</MenuItem>
                  <MenuItem value="admitted">Admitted</MenuItem>
                  <MenuItem value="rejected">Rejected</MenuItem>
                </Select>
              </FormControl>

              <TextField
                label="From Date"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                InputLabelProps={{ shrink: true }}
                sx={{ minWidth: 200 }}
              />

              <TextField
                label="To Date"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                InputLabelProps={{ shrink: true }}
                sx={{ minWidth: 200 }}
              />

              <Button variant="outlined" onClick={handleClearFilters}>
                Clear Filters
              </Button>
            </Stack>
          </SectionCard>

          {/* Statistics Summary */}
          <Grid container spacing={3} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Total Applications
                  </Typography>
                  <Typography variant="h4">
                    {stats.total_applications || 0}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Approved
                  </Typography>
                  <Typography variant="h4" color="success.main">
                    {stats.approved_applications || 0}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Admitted
                  </Typography>
                  <Typography variant="h4" color="info.main">
                    {stats.admitted_applications || 0}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Approval Rate
                  </Typography>
                  <Typography variant="h4">
                    {Math.round(approvalRate * 100)}%
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={approvalRate * 100}
                    sx={{ mt: 1 }}
                  />
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Charts */}
          <Grid container spacing={3} sx={{ mt: 1 }}>
            {/* Status Breakdown Chart */}
            {statusBreakdown.length > 0 && (
              <Grid item xs={12} md={6}>
                <SectionCard title="Applications by Status">
                  <Stack spacing={2}>
                    {statusBreakdown.map((item: any, idx: number) => (
                      <Box key={idx}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2">{item.label}</Typography>
                          <Typography variant="body2" fontWeight="bold">{item.count}</Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={Math.min(100, (item.count / (statusBreakdown[0]?.count || 1)) * 100)}
                        />
                      </Box>
                    ))}
                  </Stack>
                </SectionCard>
              </Grid>
            )}

            {/* Course Breakdown */}
            {courseBreakdown.length > 0 && (
              <Grid item xs={12} md={6}>
                <SectionCard title="Applications by Course">
                  <Stack spacing={1}>
                    {courseBreakdown.map((item: any, idx: number) => (
                      <Box key={idx} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="body2">{item.course}</Typography>
                        <Typography variant="body2" fontWeight="bold">{item.count}</Typography>
                      </Box>
                    ))}
                  </Stack>
                </SectionCard>
              </Grid>
            )}
          </Grid>

          {/* Status Breakdown Details */}
          {statusBreakdown.length > 0 && (
            <SectionCard title="Status Breakdown Details" sx={{ mt: 3 }}>
              <Stack spacing={2}>
                {statusBreakdown.map((item, idx) => (
                  <Box key={idx}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography>{item.label}</Typography>
                      <Typography variant="body2" color="textSecondary">
                        {item.count} ({Math.round(item.percentage || 0)}%)
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={item.percentage || 0}
                    />
                  </Box>
                ))}
              </Stack>
            </SectionCard>
          )}
        </Container>
      </PageContent>
    </Page>
  );
};

export default AdmissionReportPage;
