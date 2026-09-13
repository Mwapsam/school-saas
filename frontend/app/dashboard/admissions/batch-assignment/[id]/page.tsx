'use client';

import React, { useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  Container,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid,
  Stack,
  Typography,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  School as SchoolIcon,
} from '@mui/icons-material';

import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { SectionCard } from '@/components/page/SectionCard';
import { StatusBadge } from '@/components/data/StatusBadge';

import {
  useBatchAssignmentDetail,
  useAssignSingle,
  useAvailableBatches,
} from '@/features/admission-management/hooks';

const BatchAssignmentDetailPage: React.FC = () => {
  const router = useRouter();
  const params = useParams();
  const applicationId = params?.id as string;

  const [formData, setFormData] = useState({
    batch_id: '',
    roll_number: '',
    remarks: '',
  });

  // Queries
  const { data: application, isLoading, error } = useBatchAssignmentDetail(applicationId);
  const { data: availableBatches = [] } = useAvailableBatches();

  // Mutations
  const assignMutation = useAssignSingle();

  if (isLoading) return <LoadingState />;
  if (error || !application) return <ErrorState title="Application not found" description="Please try again" />;

  const handleAssign = async () => {
    if (!formData.batch_id) {
      alert('Please select a batch');
      return;
    }

    try {
      await assignMutation.mutateAsync({
        application_id: applicationId,
        batch_id: formData.batch_id,
        roll_number: formData.roll_number,
      });
      alert('Application assigned successfully');
      router.back();
    } catch (err: any) {
      alert(err?.response?.data?.error || 'Failed to assign application');
    }
  };

  const fullName = `${application.first_name || ''} ${application.last_name || ''}`;

  return (
    <Page>
      <PageHeader title="Batch Assignment" description={fullName}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => router.back()}
          variant="outlined"
        >
          Back
        </Button>
      </PageHeader>

      <PageContent>
        <Container maxWidth="md">
          <Grid container spacing={3}>
            {/* Application Summary */}
            <Grid item xs={12}>
              <SectionCard title="Application Summary" icon={<SchoolIcon />}>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Application Number
                    </Typography>
                    <Typography>{application.application_number}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Status
                    </Typography>
                    <StatusBadge status={application.status} />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Course
                    </Typography>
                    <Typography>
                      {application.course_applied?.course_name || '-'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Date of Birth
                    </Typography>
                    <Typography>
                      {application.date_of_birth
                        ? new Date(application.date_of_birth).toLocaleDateString()
                        : '-'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Email
                    </Typography>
                    <Typography>{application.email || '-'}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Mobile
                    </Typography>
                    <Typography>{application.mobile || '-'}</Typography>
                  </Grid>
                </Grid>
              </SectionCard>
            </Grid>

            {/* Assignment Form */}
            <Grid item xs={12}>
              <SectionCard title="Assign to Batch">
                <Stack spacing={3}>
                  <FormControl fullWidth>
                    <InputLabel>Batch</InputLabel>
                    <Select
                      value={formData.batch_id}
                      onChange={(e) =>
                        setFormData({ ...formData, batch_id: e.target.value })
                      }
                      label="Batch"
                    >
                      {availableBatches.map((batch: any) => (
                        <MenuItem key={batch.id} value={batch.id}>
                          {batch.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>

                  <TextField
                    label="Roll Number (Optional)"
                    value={formData.roll_number}
                    onChange={(e) =>
                      setFormData({ ...formData, roll_number: e.target.value })
                    }
                    fullWidth
                  />

                  <TextField
                    label="Remarks (Optional)"
                    value={formData.remarks}
                    onChange={(e) =>
                      setFormData({ ...formData, remarks: e.target.value })
                    }
                    multiline
                    rows={3}
                    fullWidth
                  />

                  <Stack direction="row" spacing={2} justifyContent="flex-end">
                    <Button variant="outlined" onClick={() => router.back()}>
                      Cancel
                    </Button>
                    <Button
                      variant="contained"
                      onClick={handleAssign}
                      disabled={assignMutation.isPending}
                    >
                      Assign
                    </Button>
                  </Stack>
                </Stack>
              </SectionCard>
            </Grid>
          </Grid>
        </Container>
      </PageContent>
    </Page>
  );
};

export default BatchAssignmentDetailPage;
