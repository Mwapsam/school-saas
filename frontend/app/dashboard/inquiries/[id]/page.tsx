/**
 * Applicant enquiry detail page (view/edit + stage history + follow-ups).
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import { Container, Box, Typography, Button, Grid, Paper, CircularProgress, Alert, Chip, Tabs, Tab } from '@mui/material';
import { ArrowBack as BackIcon, CallReceived as ConvertIcon } from '@mui/icons-material';
import { useState } from 'react';
import { useTenantStore } from '@/lib/tenant/store';
import { useEnquiry, useUpdateEnquiry, useConvertToApplication, EnquiryForm, type EnquiryUpdateData } from '@/features/enquiries';

export default function EnquiryDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: enquiry, isLoading, error } = useEnquiry(params.id);
  const updateMutation = useUpdateEnquiry(params.id);
  const convertMutation = useConvertToApplication(params.id);
  const [tabValue, setTabValue] = useState(0);

  if (!bootstrap) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Typography>Loading configuration...</Typography>
        </Box>
      </Container>
    );
  }

  if (!isModuleEnabled('admissions') || !can('admissions.enquiry.view')) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            You do not have permission to view this enquiry.
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

  if (error || !enquiry) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Alert severity="error">
            Failed to load enquiry: {error?.message || 'Enquiry not found'}
          </Alert>
        </Box>
      </Container>
    );
  }

  const handleUpdate = async (data: EnquiryUpdateData) => {
    try {
      await updateMutation.mutateAsync(data);
    } catch (error) {
      console.error('Failed to update enquiry:', error);
    }
  };

  const handleConvert = async () => {
    if (!confirm('Convert this enquiry to an admission application?')) {
      return;
    }
    try {
      await convertMutation.mutateAsync();
      router.push('/dashboard/admissions');
    } catch (error) {
      console.error('Failed to convert enquiry:', error);
    }
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Button startIcon={<BackIcon />} onClick={() => router.back()} variant="text">
              Back
            </Button>
            <Typography variant="h4" component="h1">
              {enquiry.enquiry_number}
            </Typography>
            {enquiry.stage && (
              <Chip
                label={enquiry.stage.name}
                size="small"
                sx={{ backgroundColor: enquiry.stage.color || '#007bff', color: 'white' }}
              />
            )}
          </Box>
          {can('admissions.enquiry.manage') && (
            <Button
              variant="outlined"
              startIcon={<ConvertIcon />}
              onClick={handleConvert}
              disabled={convertMutation.isPending}
            >
              Convert to Application
            </Button>
          )}
        </Box>

        <Grid container spacing={3}>
          {/* Overview Panel */}
          <Grid item xs={12} md={3}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Overview
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 1, fontSize: '0.875rem' }}>
                <Typography variant="body2" color="textSecondary">Name:</Typography>
                <Typography variant="body2">{`${enquiry.first_name} ${enquiry.last_name}`}</Typography>

                <Typography variant="body2" color="textSecondary">Email:</Typography>
                <Typography variant="body2">{enquiry.email || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">Phone:</Typography>
                <Typography variant="body2">{enquiry.phone || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">Course:</Typography>
                <Typography variant="body2">{enquiry.course?.name || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">Counselor:</Typography>
                <Typography variant="body2">{enquiry.counselor?.full_name || '-'}</Typography>

                <Typography variant="body2" color="textSecondary">Enquired:</Typography>
                <Typography variant="body2">{new Date(enquiry.enquired_date).toLocaleDateString()}</Typography>
              </Box>
            </Paper>
          </Grid>

          {/* Main Content */}
          <Grid item xs={12} md={9}>
            <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
              <Tabs value={tabValue} onChange={(_, value) => setTabValue(value)}>
                <Tab label="Details" />
                <Tab label={`History (${enquiry.stage_logs?.length || 0})`} />
                <Tab label={`Follow-ups (${enquiry.follow_ups?.length || 0})`} />
              </Tabs>
            </Box>

            {/* Details Tab */}
            {tabValue === 0 && (
              <Paper sx={{ p: 3 }}>
                {can('admissions.enquiry.manage') ? (
                  <EnquiryForm
                    initialData={enquiry}
                    onSubmit={handleUpdate}
                    isLoading={updateMutation.isPending}
                    error={updateMutation.error?.message || null}
                  />
                ) : (
                  <Box>
                    <Typography variant="body2" color="textSecondary" gutterBottom>Name:</Typography>
                    <Typography variant="body1" gutterBottom>{`${enquiry.first_name} ${enquiry.last_name}`}</Typography>

                    <Typography variant="body2" color="textSecondary" sx={{ mt: 2 }} gutterBottom>Email:</Typography>
                    <Typography variant="body1" gutterBottom>{enquiry.email || '-'}</Typography>

                    <Typography variant="body2" color="textSecondary" sx={{ mt: 2 }} gutterBottom>Phone:</Typography>
                    <Typography variant="body1" gutterBottom>{enquiry.phone || '-'}</Typography>

                    <Typography variant="body2" color="textSecondary" sx={{ mt: 2 }} gutterBottom>Remarks:</Typography>
                    <Typography variant="body1">{enquiry.remarks || '-'}</Typography>
                  </Box>
                )}
              </Paper>
            )}

            {/* History Tab */}
            {tabValue === 1 && (
              <Paper sx={{ p: 3 }}>
                {enquiry.stage_logs && enquiry.stage_logs.length > 0 ? (
                  <Box>
                    {enquiry.stage_logs.map((log) => (
                      <Box key={log.id} sx={{ mb: 2, pb: 2, borderBottom: '1px solid #eee' }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                            {log.stage_name}
                          </Typography>
                          <Typography variant="caption" color="textSecondary">
                            {new Date(log.created_at).toLocaleString()}
                          </Typography>
                        </Box>
                        {log.changed_by_name && (
                          <Typography variant="caption" color="textSecondary">
                            by {log.changed_by_name}
                          </Typography>
                        )}
                        {log.notes && log.notes.length > 0 && (
                          <Box sx={{ mt: 1, p: 1, backgroundColor: '#f5f5f5', borderRadius: 1 }}>
                            {log.notes.map((note) => (
                              <Box key={note.id} sx={{ mb: 1, pb: 1, borderBottom: '1px solid #ddd' }}>
                                <Typography variant="body2">{note.notes}</Typography>
                                {note.follow_up_date && (
                                  <Typography variant="caption" color="textSecondary">
                                    Follow-up: {new Date(note.follow_up_date).toLocaleDateString()}
                                  </Typography>
                                )}
                              </Box>
                            ))}
                          </Box>
                        )}
                      </Box>
                    ))}
                  </Box>
                ) : (
                  <Typography variant="body2" color="textSecondary">No stage history</Typography>
                )}
              </Paper>
            )}

            {/* Follow-ups Tab */}
            {tabValue === 2 && (
              <Paper sx={{ p: 3 }}>
                {enquiry.follow_ups && enquiry.follow_ups.length > 0 ? (
                  <Box>
                    {enquiry.follow_ups.map((followUp) => (
                      <Box key={followUp.id} sx={{ mb: 2, pb: 2, borderBottom: '1px solid #eee' }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                            <Chip label={followUp.follow_up_type_display} size="small" />
                            <Chip
                              label={followUp.status_display}
                              size="small"
                              color={followUp.status === 'completed' ? 'success' : 'default'}
                              variant="outlined"
                            />
                          </Box>
                          <Typography variant="caption" color="textSecondary">
                            {new Date(followUp.scheduled_date).toLocaleString()}
                          </Typography>
                        </Box>
                        {followUp.notes && (
                          <Typography variant="body2" sx={{ mb: 1 }}>
                            <strong>Notes:</strong> {followUp.notes}
                          </Typography>
                        )}
                        {followUp.completion_notes && (
                          <Typography variant="body2">
                            <strong>Completion:</strong> {followUp.completion_notes}
                          </Typography>
                        )}
                      </Box>
                    ))}
                  </Box>
                ) : (
                  <Typography variant="body2" color="textSecondary">No follow-ups</Typography>
                )}
              </Paper>
            )}
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
}
