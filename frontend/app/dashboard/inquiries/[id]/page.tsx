/**
 * Applicant enquiry detail page using design system components.
 */

'use client';

export const dynamic = 'force-dynamic';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button, Box, Typography, Grid, Paper, Alert, Tabs, Tab } from '@mui/material';
import { ChevronLeft as BackIcon, CallReceived as ConvertIcon } from '@mui/icons-material';
import { useState } from 'react';
import { useTenantStore } from '@/lib/tenant/store';
import { useEnquiry, useUpdateEnquiry, useConvertToApplication, EnquiryForm, type EnquiryUpdateData } from '@/features/enquiries';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { ConfirmDialog } from '@/components/feedback/ConfirmDialog';
import { StatusBadge } from '@/components/data/StatusBadge';

export default function EnquiryDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: enquiry, isLoading, error, refetch } = useEnquiry(params.id);
  const updateMutation = useUpdateEnquiry(params.id);
  const convertMutation = useConvertToApplication(params.id);
  const [tabValue, setTabValue] = useState(0);
  const [showConvertDialog, setShowConvertDialog] = useState(false);

  if (!bootstrap) {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (!isModuleEnabled('admissions') || !can('admissions.enquiry.view')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to view this enquiry.</Alert>
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

  if (error || !enquiry) {
    return (
      <Page>
        <ErrorState error={error} onRetry={() => refetch()} />
      </Page>
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
    try {
      await convertMutation.mutateAsync();
      router.push('/dashboard/admissions');
    } catch (error) {
      console.error('Failed to convert enquiry:', error);
    }
  };

  return (
    <Page>
      <PageHeader
        title={enquiry.enquiry_number}
        description={enquiry.stage ? `Stage: ${enquiry.stage.name}` : undefined}
        breadcrumbs={
          <Link href="/dashboard/inquiries" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Enquiries
            </Button>
          </Link>
        }
        actions={
          can('admissions.enquiry.manage') && (
            <Button
              variant="outlined"
              startIcon={<ConvertIcon />}
              onClick={() => setShowConvertDialog(true)}
              disabled={convertMutation.isPending}
            >
              Convert to Application
            </Button>
          )
        }
      />

      <PageContent>
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
                            <StatusBadge status={followUp.follow_up_type_display.toLowerCase()} />
                            <StatusBadge status={followUp.status === 'completed' ? 'completed' : 'pending'} />
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
      </PageContent>

      {/* Convert to Application Dialog */}
      <ConfirmDialog
        open={showConvertDialog}
        title="Convert to Application"
        message="Are you sure you want to convert this enquiry to an admission application?"
        confirmLabel="Convert"
        onConfirm={handleConvert}
        onCancel={() => setShowConvertDialog(false)}
        isLoading={convertMutation.isPending}
      />
    </Page>
  );
}
