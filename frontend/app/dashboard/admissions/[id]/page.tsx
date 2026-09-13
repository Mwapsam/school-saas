'use client';

import React, { useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  Box,
  Container,
  Grid,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  Chip,
  Stack,
  Typography,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Print as PrintIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Download as DownloadIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  Person as PersonIcon,
  School as SchoolIcon,
} from '@mui/icons-material';

import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { SectionCard } from '@/components/page/SectionCard';
import { StatusBadge } from '@/components/data/StatusBadge';
import { useTenantStore } from '@/lib/tenant/store';

import {
  useAdmissionApplicationDetail,
  useAdmitStudent,
  useDeleteApplication,
  useDuplicateApplication,
  useAssignToClass,
  useApproveApplication,
  useRejectApplication,
  useValidateAdmissionNumber,
  useActiveBatches,
} from '@/features/admission-management/hooks';

const ApplicationDetailPage: React.FC = () => {
  const router = useRouter();
  const params = useParams();
  const { can } = useTenantStore();
  const applicationId = params?.id as string;

  // Dialog states
  const [admitDialogOpen, setAdmitDialogOpen] = useState(false);
  const [assignDialogOpen, setAssignDialogOpen] = useState(false);
  const [approveDialogOpen, setApproveDialogOpen] = useState(false);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [parentAccountDialogOpen, setParentAccountDialogOpen] = useState(false);

  // Form states
  const [admitFormData, setAdmitFormData] = useState({
    batch_id: '',
    admission_number: '',
    admission_date: new Date().toISOString().split('T')[0],
    remarks: '',
  });

  const [assignFormData, setAssignFormData] = useState({
    batch_id: '',
    roll_number: '',
    remarks: '',
  });

  const [approveReason, setApproveReason] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [admissionNumberError, setAdmissionNumberError] = useState('');
  const [parentAccountInfo, setParentAccountInfo] = useState<any>(null);

  // Queries
  const { data: application, isLoading, error } = useAdmissionApplicationDetail(applicationId);
  const { data: availableBatches } = useActiveBatches(application?.course_applied?.id);

  // Mutations
  const admitMutation = useAdmitStudent(applicationId);
  const deleteMutation = useDeleteApplication(applicationId);
  const duplicateMutation = useDuplicateApplication(applicationId);
  const assignToClassMutation = useAssignToClass(applicationId);
  const approveMutation = useApproveApplication(applicationId);
  const rejectMutation = useRejectApplication(applicationId);
  const validateAdmissionNumberMutation = useValidateAdmissionNumber();

  if (isLoading) return <LoadingState />;
  if (error || !application) return <ErrorState message="Application not found" />;

  const statusColor = {
    draft: 'default',
    submitted: 'info',
    under_review: 'warning',
    approved: 'success',
    admitted: 'success',
    rejected: 'error',
  }[application.status] || 'default';

  const canApprove = application.status === 'submitted' || application.status === 'under_review';
  const canReject = application.status === 'submitted' || application.status === 'under_review';
  const canAdmit = application.status === 'approved';
  const canAssignClass = application.status === 'admitted' && application.admitted_student;
  const canDelete = can('admissions.application.manage');
  const canEdit = can('admissions.application.manage');

  // Handler: Admit Student
  const handleAdmit = async () => {
    if (!admitFormData.batch_id) {
      alert('Please select a batch');
      return;
    }

    try {
      const result = await admitMutation.mutateAsync({
        batch_id: admitFormData.batch_id,
        admission_number: admitFormData.admission_number,
        admission_date: admitFormData.admission_date,
        remarks: admitFormData.remarks,
      });

      setParentAccountInfo((result as any)?.parent_account);
      setParentAccountDialogOpen(true);
      setAdmitDialogOpen(false);

      // Refresh application data
      setTimeout(() => {
        router.refresh();
      }, 1000);
    } catch (err: any) {
      alert(err?.response?.data?.error || 'Failed to admit student');
    }
  };

  // Handler: Assign to Class
  const handleAssignToClass = async () => {
    if (!assignFormData.batch_id) {
      alert('Please select a batch');
      return;
    }

    try {
      await assignToClassMutation.mutateAsync({
        batch_id: assignFormData.batch_id,
        roll_number: assignFormData.roll_number,
        remarks: assignFormData.remarks,
      });

      setAssignDialogOpen(false);
      router.refresh();
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to assign to class');
    }
  };

  // Handler: Approve
  const handleApprove = async () => {
    try {
      await approveMutation.mutateAsync();
      setApproveDialogOpen(false);
      router.refresh();
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to approve');
    }
  };

  // Handler: Reject
  const handleReject = async () => {
    if (!rejectReason.trim()) {
      alert('Rejection reason is required');
      return;
    }

    try {
      await rejectMutation.mutateAsync({ reason: rejectReason });
      setRejectDialogOpen(false);
      router.refresh();
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to reject');
    }
  };

  // Handler: Delete
  const handleDelete = async () => {
    try {
      await deleteMutation.mutateAsync();
      router.push('/dashboard/admissions');
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to delete');
    }
  };

  // Handler: Duplicate
  const handleDuplicate = async () => {
    try {
      const result = await duplicateMutation.mutateAsync();
      setDuplicateDialogOpen(false);
      const newId = (result as any)?.data?.id || (result as any)?.id;
      router.push(`/dashboard/admissions/multi-step/${newId}`);
    } catch (err: any) {
      alert(err?.response?.data?.error || 'Failed to duplicate');
    }
  };

  // Handler: Validate admission number on blur
  const handleValidateAdmissionNumber = async (value: string) => {
    if (!value) {
      setAdmissionNumberError('');
      return;
    }

    try {
      const result = await validateAdmissionNumberMutation.mutateAsync(value);
      if (!result.is_unique) {
        setAdmissionNumberError('This admission number is already in use');
      } else {
        setAdmissionNumberError('');
      }
    } catch (err) {
      setAdmissionNumberError('Error validating admission number');
    }
  };

  const applicationNumber = application.application_number;
  const fullName = `${application.first_name}${application.middle_name ? ' ' + application.middle_name : ''} ${application.last_name}`;

  return (
    <Page>
      <PageHeader title={fullName} description={`Application #${applicationNumber}`}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => router.back()}
          variant="outlined"
        >
          Back
        </Button>
      </PageHeader>

      <PageContent>
        <Container maxWidth="lg">
          {/* Status Alert */}
          <Alert severity="info" sx={{ mb: 3 }}>
            Status: <StatusBadge status={application.status} color={statusColor} />
            {application.remarks && ` — ${application.remarks}`}
          </Alert>

          <Grid container spacing={3}>
            {/* Left Column */}
            <Grid item xs={12} md={8}>
              {/* Basic Information */}
              <SectionCard title="Application Information" icon={<SchoolIcon />}>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Application Number
                    </Typography>
                    <Typography>{application.application_number}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Application Date
                    </Typography>
                    <Typography>
                      {new Date(application.application_date).toLocaleDateString()}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Academic Year
                    </Typography>
                    <Typography>{application.academic_year?.name || 'N/A'}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Course Applied
                    </Typography>
                    <Typography>{application.course_applied?.course_name || 'N/A'}</Typography>
                  </Grid>
                </Grid>
              </SectionCard>

              {/* Personal Details */}
              <SectionCard title="Personal Details" icon={<PersonIcon />} sx={{ mt: 3 }}>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={4}>
                    <Typography variant="caption" color="textSecondary">
                      First Name
                    </Typography>
                    <Typography>{application.first_name}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <Typography variant="caption" color="textSecondary">
                      Middle Name
                    </Typography>
                    <Typography>{application.middle_name || '-'}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <Typography variant="caption" color="textSecondary">
                      Last Name
                    </Typography>
                    <Typography>{application.last_name}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <Typography variant="caption" color="textSecondary">
                      Date of Birth
                    </Typography>
                    <Typography>
                      {new Date(application.date_of_birth).toLocaleDateString()}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <Typography variant="caption" color="textSecondary">
                      Gender
                    </Typography>
                    <Typography sx={{ textTransform: 'capitalize' }}>
                      {application.gender || '-'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <Typography variant="caption" color="textSecondary">
                      Nationality
                    </Typography>
                    <Typography>{application.nationality || '-'}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Religion
                    </Typography>
                    <Typography>{application.religion || '-'}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Birth Place
                    </Typography>
                    <Typography>{application.birth_place || '-'}</Typography>
                  </Grid>
                  <Grid item xs={12}>
                    <Typography variant="caption" color="textSecondary">
                      Mother Tongue
                    </Typography>
                    <Typography>{application.mother_tongue || '-'}</Typography>
                  </Grid>
                </Grid>
              </SectionCard>

              {/* Contact Information */}
              <SectionCard title="Contact Information" sx={{ mt: 3 }}>
                <Grid container spacing={2}>
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
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Phone
                    </Typography>
                    <Typography>{application.phone || '-'}</Typography>
                  </Grid>
                </Grid>
              </SectionCard>

              {/* Address */}
              <SectionCard title="Address" sx={{ mt: 3 }}>
                <Grid container spacing={2}>
                  <Grid item xs={12}>
                    <Typography variant="caption" color="textSecondary">
                      Address Line 1
                    </Typography>
                    <Typography>{application.address_line1 || '-'}</Typography>
                  </Grid>
                  <Grid item xs={12}>
                    <Typography variant="caption" color="textSecondary">
                      Address Line 2
                    </Typography>
                    <Typography>{application.address_line2 || '-'}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      City
                    </Typography>
                    <Typography>{application.city || '-'}</Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="textSecondary">
                      Country
                    </Typography>
                    <Typography>{application.country || '-'}</Typography>
                  </Grid>
                </Grid>
              </SectionCard>

              {/* Guardians */}
              {(application.guardian1_first_name || application.guardian2_first_name) && (
                <>
                  {application.guardian1_first_name && (
                    <SectionCard title="Guardian 1" sx={{ mt: 3 }}>
                      <Grid container spacing={2}>
                        <Grid item xs={12} sm={6}>
                          <Typography variant="caption" color="textSecondary">
                            Name
                          </Typography>
                          <Typography>
                            {application.guardian1_first_name} {application.guardian1_last_name}
                          </Typography>
                        </Grid>
                        <Grid item xs={12} sm={6}>
                          <Typography variant="caption" color="textSecondary">
                            Relation
                          </Typography>
                          <Typography>{application.guardian1_relation || '-'}</Typography>
                        </Grid>
                        <Grid item xs={12} sm={6}>
                          <Typography variant="caption" color="textSecondary">
                            Mobile
                          </Typography>
                          <Typography>{application.guardian1_mobile || '-'}</Typography>
                        </Grid>
                        <Grid item xs={12} sm={6}>
                          <Typography variant="caption" color="textSecondary">
                            Email
                          </Typography>
                          <Typography>{application.guardian1_email || '-'}</Typography>
                        </Grid>
                        <Grid item xs={12} sm={6}>
                          <Typography variant="caption" color="textSecondary">
                            Occupation
                          </Typography>
                          <Typography>{application.guardian1_occupation || '-'}</Typography>
                        </Grid>
                      </Grid>
                    </SectionCard>
                  )}

                  {application.guardian2_first_name && (
                    <SectionCard title="Guardian 2" sx={{ mt: 3 }}>
                      <Grid container spacing={2}>
                        <Grid item xs={12} sm={6}>
                          <Typography variant="caption" color="textSecondary">
                            Name
                          </Typography>
                          <Typography>
                            {application.guardian2_first_name} {application.guardian2_last_name}
                          </Typography>
                        </Grid>
                        <Grid item xs={12} sm={6}>
                          <Typography variant="caption" color="textSecondary">
                            Relation
                          </Typography>
                          <Typography>{application.guardian2_relation || '-'}</Typography>
                        </Grid>
                        <Grid item xs={12} sm={6}>
                          <Typography variant="caption" color="textSecondary">
                            Mobile
                          </Typography>
                          <Typography>{application.guardian2_mobile || '-'}</Typography>
                        </Grid>
                        <Grid item xs={12} sm={6}>
                          <Typography variant="caption" color="textSecondary">
                            Email
                          </Typography>
                          <Typography>{application.guardian2_email || '-'}</Typography>
                        </Grid>
                        <Grid item xs={12} sm={6}>
                          <Typography variant="caption" color="textSecondary">
                            Occupation
                          </Typography>
                          <Typography>{application.guardian2_occupation || '-'}</Typography>
                        </Grid>
                      </Grid>
                    </SectionCard>
                  )}
                </>
              )}

              {/* Health Information */}
              {(application.has_medical_problems || application.recent_hospitalization || application.has_allergies) && (
                <SectionCard title="Health Information" sx={{ mt: 3 }}>
                  <Stack direction="row" gap={1} flexWrap="wrap" sx={{ mb: 2 }}>
                    {application.has_medical_problems && (
                      <Chip label="Has Medical Problems" size="small" color="warning" variant="outlined" />
                    )}
                    {application.recent_hospitalization && (
                      <Chip label="Recent Hospitalization" size="small" color="error" variant="outlined" />
                    )}
                    {application.has_allergies && (
                      <Chip label="Has Allergies" size="small" color="info" variant="outlined" />
                    )}
                  </Stack>
                  {application.medical_details && (
                    <>
                      <Typography variant="caption" color="textSecondary">
                        Medical Details
                      </Typography>
                      <Typography>{application.medical_details}</Typography>
                    </>
                  )}
                </SectionCard>
              )}

              {/* Declaration */}
              {application.religious_observances || application.background_information && (
                <SectionCard title="Declaration & Background" sx={{ mt: 3 }}>
                  {application.religious_observances && (
                    <>
                      <Typography variant="caption" color="textSecondary">
                        Religious Observances
                      </Typography>
                      <Typography sx={{ mb: 2 }}>{application.religious_observances}</Typography>
                    </>
                  )}
                  {application.background_information && (
                    <>
                      <Typography variant="caption" color="textSecondary">
                        Background Information
                      </Typography>
                      <Typography>{application.background_information}</Typography>
                    </>
                  )}
                </SectionCard>
              )}
            </Grid>

            {/* Right Sidebar */}
            <Grid item xs={12} md={4}>
              {/* Status & Quick Actions */}
              <SectionCard title="Quick Actions">
                <Stack spacing={2}>
                  {canAdmit && (
                    <Button
                      fullWidth
                      variant="contained"
                      color="success"
                      startIcon={<CheckCircleIcon />}
                      onClick={() => setAdmitDialogOpen(true)}
                      disabled={admitMutation.isPending}
                    >
                      Admit Student
                    </Button>
                  )}

                  {canAssignClass && (
                    <Button
                      fullWidth
                      variant="contained"
                      onClick={() => setAssignDialogOpen(true)}
                      disabled={assignToClassMutation.isPending}
                    >
                      Assign to Class
                    </Button>
                  )}

                  {canApprove && (
                    <Button
                      fullWidth
                      variant="outlined"
                      color="success"
                      onClick={() => setApproveDialogOpen(true)}
                      disabled={approveMutation.isPending}
                    >
                      Approve
                    </Button>
                  )}

                  {canReject && (
                    <Button
                      fullWidth
                      variant="outlined"
                      color="error"
                      startIcon={<CancelIcon />}
                      onClick={() => setRejectDialogOpen(true)}
                      disabled={rejectMutation.isPending}
                    >
                      Reject
                    </Button>
                  )}

                  {canEdit && (
                    <Button
                      fullWidth
                      variant="outlined"
                      startIcon={<EditIcon />}
                      onClick={() => router.push(`/dashboard/admissions/multi-step/${applicationId}?edit=true`)}
                    >
                      Edit Application
                    </Button>
                  )}

                  {canDelete && (
                    <Button
                      fullWidth
                      variant="outlined"
                      color="error"
                      startIcon={<DeleteIcon />}
                      onClick={() => setDeleteDialogOpen(true)}
                      disabled={deleteMutation.isPending}
                    >
                      Delete
                    </Button>
                  )}

                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<PrintIcon />}
                    onClick={() => window.print()}
                  >
                    Print
                  </Button>

                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<DownloadIcon />}
                    onClick={() => {/* TODO: Export PDF */}}
                  >
                    Export PDF
                  </Button>
                </Stack>
              </SectionCard>

              {/* Status Info */}
              <SectionCard title="Status Information" sx={{ mt: 3 }}>
                <Stack spacing={2}>
                  <Box>
                    <Typography variant="caption" color="textSecondary">
                      Current Status
                    </Typography>
                    <StatusBadge status={application.status} color={statusColor} sx={{ mt: 1 }} />
                  </Box>

                  {application.reviewed_at && (
                    <Box>
                      <Typography variant="caption" color="textSecondary">
                        Reviewed On
                      </Typography>
                      <Typography>
                        {new Date(application.reviewed_at).toLocaleDateString()}
                      </Typography>
                    </Box>
                  )}

                  {application.reviewed_by && (
                    <Box>
                      <Typography variant="caption" color="textSecondary">
                        Reviewed By
                      </Typography>
                      <Typography>{application.reviewed_by}</Typography>
                    </Box>
                  )}

                  {application.remarks && (
                    <Box>
                      <Typography variant="caption" color="textSecondary">
                        Remarks
                      </Typography>
                      <Typography>{application.remarks}</Typography>
                    </Box>
                  )}
                </Stack>
              </SectionCard>
            </Grid>
          </Grid>
        </Container>

        {/* MODALS */}

        {/* Admit Student Dialog */}
        <Dialog
          open={admitDialogOpen}
          onClose={() => setAdmitDialogOpen(false)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>Admit Student</DialogTitle>
          <DialogContent sx={{ pt: 2 }}>
            <Stack spacing={2}>
              <FormControl fullWidth required>
                <InputLabel>Batch</InputLabel>
                <Select
                  value={admitFormData.batch_id}
                  onChange={(e) => setAdmitFormData({ ...admitFormData, batch_id: e.target.value })}
                  label="Batch"
                >
                  <MenuItem value="">
                    <em>Select a batch</em>
                  </MenuItem>
                  {availableBatches?.map((batch) => (
                    <MenuItem key={batch.id} value={batch.id}>
                      {batch.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <TextField
                fullWidth
                label="Admission Number"
                value={admitFormData.admission_number}
                onChange={(e) => setAdmitFormData({ ...admitFormData, admission_number: e.target.value })}
                onBlur={(e) => handleValidateAdmissionNumber(e.target.value)}
                placeholder="Leave empty to auto-generate"
                helperText={admissionNumberError || 'Leave empty for system to auto-generate'}
                error={!!admissionNumberError}
              />

              <TextField
                fullWidth
                type="date"
                label="Admission Date"
                value={admitFormData.admission_date}
                onChange={(e) => setAdmitFormData({ ...admitFormData, admission_date: e.target.value })}
                InputLabelProps={{ shrink: true }}
              />

              <TextField
                fullWidth
                multiline
                rows={3}
                label="Remarks"
                value={admitFormData.remarks}
                onChange={(e) => setAdmitFormData({ ...admitFormData, remarks: e.target.value })}
              />
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setAdmitDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={handleAdmit}
              variant="contained"
              disabled={admitMutation.isPending || !admitFormData.batch_id || !!admissionNumberError}
            >
              {admitMutation.isPending ? 'Admitting...' : 'Admit'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Parent Account Created Dialog */}
        <Dialog open={parentAccountDialogOpen} onClose={() => setParentAccountDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>
            {parentAccountInfo?.status === 'created'
              ? 'Parent Portal Account Created'
              : 'Admission Successful'}
          </DialogTitle>
          <DialogContent sx={{ pt: 2 }}>
            <Stack spacing={2}>
              {parentAccountInfo?.status === 'created' && (
                <>
                  <Alert severity="success">
                    A parent portal account has been created for the guardians.
                  </Alert>
                  {parentAccountInfo?.username && (
                    <>
                      <Box>
                        <Typography variant="caption" color="textSecondary">
                          Username
                        </Typography>
                        <TextField
                          fullWidth
                          value={parentAccountInfo.username}
                          InputProps={{ readOnly: true }}
                          variant="outlined"
                          size="small"
                        />
                      </Box>
                      <Box>
                        <Typography variant="caption" color="textSecondary">
                          Temporary Password
                        </Typography>
                        <TextField
                          fullWidth
                          value={parentAccountInfo.password}
                          InputProps={{ readOnly: true }}
                          variant="outlined"
                          size="small"
                        />
                      </Box>
                      <Alert severity="warning">
                        Please share these credentials with the parent/guardian. They should change the password on first login.
                      </Alert>
                    </>
                  )}
                </>
              )}
              {parentAccountInfo?.status === 'linked' && (
                <Alert severity="info">
                  The application has been linked to an existing parent portal account.
                </Alert>
              )}
              {parentAccountInfo?.status === 'skipped' && (
                <Alert severity="warning">
                  Parent portal account creation was skipped: {parentAccountInfo?.reason}
                </Alert>
              )}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setParentAccountDialogOpen(false)} variant="contained">
              Done
            </Button>
          </DialogActions>
        </Dialog>

        {/* Assign to Class Dialog */}
        <Dialog open={assignDialogOpen} onClose={() => setAssignDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Assign to Class</DialogTitle>
          <DialogContent sx={{ pt: 2 }}>
            <Stack spacing={2}>
              <FormControl fullWidth required>
                <InputLabel>Batch</InputLabel>
                <Select
                  value={assignFormData.batch_id}
                  onChange={(e) => setAssignFormData({ ...assignFormData, batch_id: e.target.value })}
                  label="Batch"
                >
                  <MenuItem value="">
                    <em>Select a batch</em>
                  </MenuItem>
                  {availableBatches?.map((batch) => (
                    <MenuItem key={batch.id} value={batch.id}>
                      {batch.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <TextField
                fullWidth
                label="Roll Number"
                value={assignFormData.roll_number}
                onChange={(e) => setAssignFormData({ ...assignFormData, roll_number: e.target.value })}
              />

              <TextField
                fullWidth
                multiline
                rows={2}
                label="Remarks"
                value={assignFormData.remarks}
                onChange={(e) => setAssignFormData({ ...assignFormData, remarks: e.target.value })}
              />
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setAssignDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={handleAssignToClass}
              variant="contained"
              disabled={assignToClassMutation.isPending || !assignFormData.batch_id}
            >
              {assignToClassMutation.isPending ? 'Assigning...' : 'Assign'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Approve Dialog */}
        <Dialog open={approveDialogOpen} onClose={() => setApproveDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Approve Application</DialogTitle>
          <DialogContent sx={{ pt: 2 }}>
            <TextField
              fullWidth
              multiline
              rows={3}
              label="Remarks (Optional)"
              value={approveReason}
              onChange={(e) => setApproveReason(e.target.value)}
              placeholder="Add any remarks about the approval..."
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setApproveDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={handleApprove}
              variant="contained"
              color="success"
              disabled={approveMutation.isPending}
            >
              {approveMutation.isPending ? 'Approving...' : 'Approve'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Reject Dialog */}
        <Dialog open={rejectDialogOpen} onClose={() => setRejectDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Reject Application</DialogTitle>
          <DialogContent sx={{ pt: 2 }}>
            <TextField
              fullWidth
              multiline
              rows={3}
              label="Rejection Reason"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Explain why the application is being rejected..."
              error={!rejectReason.trim()}
              helperText={!rejectReason.trim() ? 'Reason is required' : ''}
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setRejectDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={handleReject}
              variant="contained"
              color="error"
              disabled={rejectMutation.isPending || !rejectReason.trim()}
            >
              {rejectMutation.isPending ? 'Rejecting...' : 'Reject'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Delete Application</DialogTitle>
          <DialogContent sx={{ pt: 2 }}>
            <Alert severity="warning" sx={{ mb: 2 }}>
              This action cannot be undone. Are you sure you want to delete this application?
            </Alert>
            <Typography>
              Application: <strong>{application?.application_number}</strong>
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={handleDelete}
              variant="contained"
              color="error"
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Duplicate Confirmation Dialog */}
        <Dialog open={duplicateDialogOpen} onClose={() => setDuplicateDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Duplicate Application</DialogTitle>
          <DialogContent sx={{ pt: 2 }}>
            <Typography>
              This will create a copy of the application with status set to "Draft". You'll be able to edit the copy.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDuplicateDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={handleDuplicate}
              variant="contained"
              disabled={duplicateMutation.isPending}
            >
              {duplicateMutation.isPending ? 'Duplicating...' : 'Duplicate'}
            </Button>
          </DialogActions>
        </Dialog>
      </PageContent>
    </Page>
  );
};

export default ApplicationDetailPage;
