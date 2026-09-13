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
  Email as EmailIcon,
  Phone as PhoneIcon,
} from '@mui/icons-material';

import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { SectionCard, DetailField } from '@/components/page';
import { StatusBadge } from '@/components/data/StatusBadge';
import { LoadingButton } from '@/design-system/components/LoadingButton';
import { ConfirmDialog } from '@/components/feedback/ConfirmDialog';
import { useTenantStore } from '@/lib/tenant/store';

import {
  useAdmissionApplicationDetail,
  useAdmitStudent,
  useDeleteApplication,
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
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
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
  const assignToClassMutation = useAssignToClass(applicationId);
  const approveMutation = useApproveApplication(applicationId);
  const rejectMutation = useRejectApplication(applicationId);
  const validateAdmissionNumberMutation = useValidateAdmissionNumber();

  if (isLoading) return <LoadingState />;
  if (error || !application) return <ErrorState error={error || undefined} onRetry={() => window.location.reload()} />;

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
      setDeleteConfirmOpen(false);
      router.push('/dashboard/admissions');
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to delete');
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
          <Alert severity="info" sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ flex: 1 }}>
              Status: <StatusBadge status={application.status as any} sx={{ ml: 0.5 }} />
              {application.remarks && <Box component="span" sx={{ ml: 1 }}>{application.remarks}</Box>}
            </Box>
          </Alert>

          <Grid container spacing={3}>
            {/* Left Column */}
            <Grid item xs={12} md={8}>
              {/* Basic Information */}
              <SectionCard title="Application Information" icon={<SchoolIcon />}>
                <Stack spacing={0.25}>
                  <DetailField label="Application Number" value={application.application_number} />
                  <DetailField label="Application Date" value={new Date(application.application_date).toLocaleDateString()} />
                  <DetailField label="Academic Year" value={application.academic_year?.name || '—'} />
                  <DetailField label="Course Applied" value={application.course_applied?.course_name || '—'} />
                </Stack>
              </SectionCard>

              {/* Personal Details */}
              <SectionCard title="Personal Details" icon={<PersonIcon />} sx={{ mt: 3 }}>
                <Stack spacing={0.25}>
                  <DetailField label="First Name" value={application.first_name} />
                  <DetailField label="Middle Name" value={application.middle_name || '—'} />
                  <DetailField label="Last Name" value={application.last_name} />
                  <DetailField label="Date of Birth" value={new Date(application.date_of_birth).toLocaleDateString()} />
                  <DetailField label="Gender" value={application.gender ? application.gender.charAt(0).toUpperCase() + application.gender.slice(1).toLowerCase() : '—'} />
                  <DetailField label="Nationality" value={application.nationality || '—'} />
                  <DetailField label="Religion" value={application.religion || '—'} />
                  <DetailField label="Birth Place" value={application.birth_place || '—'} />
                  <DetailField label="Mother Tongue" value={application.mother_tongue || '—'} />
                </Stack>
              </SectionCard>

              {/* Contact Information */}
              <SectionCard title="Contact Information" sx={{ mt: 3 }}>
                <Stack spacing={1.5}>
                  <Box>
                    <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                      Email
                    </Typography>
                    {application.email ? (
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <EmailIcon sx={{ fontSize: 18, color: 'text.secondary', flexShrink: 0 }} />
                        <Typography
                          component="a"
                          href={`mailto:${application.email}`}
                          variant="body2"
                          sx={{
                            color: 'primary.main',
                            textDecoration: 'none',
                            wordBreak: 'break-all',
                            '&:hover': { textDecoration: 'underline' },
                            flex: 1,
                          }}
                        >
                          {application.email}
                        </Typography>
                      </Stack>
                    ) : (
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <EmailIcon sx={{ fontSize: 18, color: 'text.secondary', flexShrink: 0, opacity: 0.4 }} />
                        <Typography variant="body2" color="text.secondary">
                          —
                        </Typography>
                      </Stack>
                    )}
                  </Box>

                  <Box>
                    <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                      Mobile
                    </Typography>
                    {application.mobile ? (
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <PhoneIcon sx={{ fontSize: 18, color: 'text.secondary', flexShrink: 0 }} />
                        <Typography
                          component="a"
                          href={`tel:${application.mobile}`}
                          variant="body2"
                          sx={{
                            color: 'text.primary',
                            textDecoration: 'none',
                            '&:hover': { color: 'primary.main' },
                          }}
                        >
                          {application.mobile}
                        </Typography>
                      </Stack>
                    ) : (
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <PhoneIcon sx={{ fontSize: 18, color: 'text.secondary', flexShrink: 0, opacity: 0.4 }} />
                        <Typography variant="body2" color="text.secondary">
                          —
                        </Typography>
                      </Stack>
                    )}
                  </Box>

                  <Box>
                    <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                      Phone
                    </Typography>
                    {application.phone ? (
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <PhoneIcon sx={{ fontSize: 18, color: 'text.secondary', flexShrink: 0 }} />
                        <Typography
                          component="a"
                          href={`tel:${application.phone}`}
                          variant="body2"
                          sx={{
                            color: 'text.primary',
                            textDecoration: 'none',
                            '&:hover': { color: 'primary.main' },
                          }}
                        >
                          {application.phone}
                        </Typography>
                      </Stack>
                    ) : (
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <PhoneIcon sx={{ fontSize: 18, color: 'text.secondary', flexShrink: 0, opacity: 0.4 }} />
                        <Typography variant="body2" color="text.secondary">
                          —
                        </Typography>
                      </Stack>
                    )}
                  </Box>
                </Stack>
              </SectionCard>

              {/* Address */}
              <SectionCard title="Address" sx={{ mt: 3 }}>
                <Stack spacing={0.25}>
                  <DetailField label="Address Line 1" value={application.address_line1 || '—'} />
                  <DetailField label="Address Line 2" value={application.address_line2 || '—'} />
                  <DetailField label="City" value={application.city || '—'} />
                  <DetailField label="Country" value={application.country || '—'} />
                </Stack>
              </SectionCard>

              {/* Guardians */}
              {(application.guardian1_first_name || application.guardian2_first_name) && (
                <>
                  {application.guardian1_first_name && (
                    <SectionCard title="Guardian 1" sx={{ mt: 3 }}>
                      <Stack spacing={0.25}>
                        <DetailField label="Name" value={`${application.guardian1_first_name} ${application.guardian1_last_name}`} />
                        <DetailField label="Relation" value={application.guardian1_relation || '—'} />
                        <DetailField label="Mobile" value={application.guardian1_mobile || '—'} />
                        <DetailField label="Email" value={application.guardian1_email || '—'} />
                        <DetailField label="Occupation" value={application.guardian1_occupation || '—'} />
                      </Stack>
                    </SectionCard>
                  )}

                  {application.guardian2_first_name && (
                    <SectionCard title="Guardian 2" sx={{ mt: 3 }}>
                      <Stack spacing={0.25}>
                        <DetailField label="Name" value={`${application.guardian2_first_name} ${application.guardian2_last_name}`} />
                        <DetailField label="Relation" value={application.guardian2_relation || '—'} />
                        <DetailField label="Mobile" value={application.guardian2_mobile || '—'} />
                        <DetailField label="Email" value={application.guardian2_email || '—'} />
                        <DetailField label="Occupation" value={application.guardian2_occupation || '—'} />
                      </Stack>
                    </SectionCard>
                  )}
                </>
              )}

              {/* Health Information */}
              {(application.has_medical_problems || application.recent_hospitalization || application.has_allergies) && (
                <SectionCard title="Health Information" sx={{ mt: 3 }}>
                  <Stack spacing={1.5}>
                    <Stack direction="row" gap={1} flexWrap="wrap" useFlexGap>
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
                      <Box>
                        <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                          Medical Details
                        </Typography>
                        <Typography variant="body2">{application.medical_details}</Typography>
                      </Box>
                    )}
                  </Stack>
                </SectionCard>
              )}

              {/* Declaration */}
              {application.religious_observances || application.background_information && (
                <SectionCard title="Declaration & Background" sx={{ mt: 3 }}>
                  <Stack spacing={1.5}>
                    {application.religious_observances && (
                      <Box>
                        <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                          Religious Observances
                        </Typography>
                        <Typography variant="body2">{application.religious_observances}</Typography>
                      </Box>
                    )}
                    {application.background_information && (
                      <Box>
                        <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                          Background Information
                        </Typography>
                        <Typography variant="body2">{application.background_information}</Typography>
                      </Box>
                    )}
                  </Stack>
                </SectionCard>
              )}
            </Grid>

            {/* Right Sidebar */}
            <Grid item xs={12} md={4}>
              {/* Status & Quick Actions */}
              <SectionCard title="Quick Actions">
                <Stack spacing={2}>
                  {canAdmit && (
                    <LoadingButton
                      fullWidth
                      variant="contained"
                      color="success"
                      startIcon={<CheckCircleIcon />}
                      onClick={() => setAdmitDialogOpen(true)}
                      loading={admitMutation.isPending}
                    >
                      Admit Student
                    </LoadingButton>
                  )}

                  {canAssignClass && (
                    <LoadingButton
                      fullWidth
                      variant="contained"
                      onClick={() => setAssignDialogOpen(true)}
                      loading={assignToClassMutation.isPending}
                    >
                      Assign to Class
                    </LoadingButton>
                  )}

                  {canApprove && (
                    <LoadingButton
                      fullWidth
                      variant="outlined"
                      color="success"
                      onClick={() => setApproveDialogOpen(true)}
                      loading={approveMutation.isPending}
                    >
                      Approve
                    </LoadingButton>
                  )}

                  {canReject && (
                    <LoadingButton
                      fullWidth
                      variant="outlined"
                      color="error"
                      startIcon={<CancelIcon />}
                      onClick={() => setRejectDialogOpen(true)}
                      loading={rejectMutation.isPending}
                    >
                      Reject
                    </LoadingButton>
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
                    <LoadingButton
                      fullWidth
                      variant="outlined"
                      color="error"
                      startIcon={<DeleteIcon />}
                      onClick={() => setDeleteConfirmOpen(true)}
                      loading={deleteMutation.isPending}
                    >
                      Delete
                    </LoadingButton>
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
                <Stack spacing={1.5}>
                  <Box>
                    <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                      Current Status
                    </Typography>
                    <StatusBadge status={application.status as any} sx={{ mt: 0.5 }} />
                  </Box>

                  {application.reviewed_at && (
                    <Box>
                      <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                        Reviewed On
                      </Typography>
                      <Typography variant="body2">
                        {new Date(application.reviewed_at).toLocaleDateString()}
                      </Typography>
                    </Box>
                  )}

                  {application.reviewed_by && (
                    <Box>
                      <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                        Reviewed By
                      </Typography>
                      <Typography variant="body2">{application.reviewed_by}</Typography>
                    </Box>
                  )}

                  {application.remarks && (
                    <Box>
                      <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                        Remarks
                      </Typography>
                      <Typography variant="body2">{application.remarks}</Typography>
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
          PaperProps={{ sx: { borderRadius: 2 } }}
        >
          <DialogTitle sx={{ pb: 1 }}>Admit Student</DialogTitle>
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
                size="small"
              />

              <TextField
                fullWidth
                type="date"
                label="Admission Date"
                value={admitFormData.admission_date}
                onChange={(e) => setAdmitFormData({ ...admitFormData, admission_date: e.target.value })}
                InputLabelProps={{ shrink: true }}
                size="small"
              />

              <TextField
                fullWidth
                multiline
                rows={3}
                label="Remarks (Optional)"
                value={admitFormData.remarks}
                onChange={(e) => setAdmitFormData({ ...admitFormData, remarks: e.target.value })}
                size="small"
              />
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button onClick={() => setAdmitDialogOpen(false)} disabled={admitMutation.isPending}>
              Cancel
            </Button>
            <LoadingButton
              onClick={handleAdmit}
              variant="contained"
              color="success"
              loading={admitMutation.isPending}
              disabled={!admitFormData.batch_id || !!admissionNumberError}
            >
              Admit
            </LoadingButton>
          </DialogActions>
        </Dialog>

        {/* Parent Account Created Dialog */}
        <Dialog
          open={parentAccountDialogOpen}
          onClose={() => setParentAccountDialogOpen(false)}
          maxWidth="sm"
          fullWidth
          PaperProps={{ sx: { borderRadius: 2 } }}
        >
          <DialogTitle sx={{ pb: 1 }}>
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
                        <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                          Username
                        </Typography>
                        <Typography
                          variant="body2"
                          sx={{
                            p: 1.5,
                            bgcolor: 'action.hover',
                            borderRadius: 1,
                            fontFamily: 'monospace',
                            wordBreak: 'break-all',
                          }}
                        >
                          {parentAccountInfo.username}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                          Temporary Password
                        </Typography>
                        <Typography
                          variant="body2"
                          sx={{
                            p: 1.5,
                            bgcolor: 'action.hover',
                            borderRadius: 1,
                            fontFamily: 'monospace',
                            wordBreak: 'break-all',
                          }}
                        >
                          {parentAccountInfo.password}
                        </Typography>
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
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button onClick={() => setParentAccountDialogOpen(false)} variant="contained">
              Done
            </Button>
          </DialogActions>
        </Dialog>

        {/* Assign to Class Dialog */}
        <Dialog
          open={assignDialogOpen}
          onClose={() => setAssignDialogOpen(false)}
          maxWidth="sm"
          fullWidth
          PaperProps={{ sx: { borderRadius: 2 } }}
        >
          <DialogTitle sx={{ pb: 1 }}>Assign to Class</DialogTitle>
          <DialogContent sx={{ pt: 2 }}>
            <Stack spacing={2}>
              <FormControl fullWidth required>
                <InputLabel>Batch</InputLabel>
                <Select
                  value={assignFormData.batch_id}
                  onChange={(e) => setAssignFormData({ ...assignFormData, batch_id: e.target.value })}
                  label="Batch"
                  size="small"
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
                size="small"
              />

              <TextField
                fullWidth
                multiline
                rows={2}
                label="Remarks (Optional)"
                value={assignFormData.remarks}
                onChange={(e) => setAssignFormData({ ...assignFormData, remarks: e.target.value })}
                size="small"
              />
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button onClick={() => setAssignDialogOpen(false)} disabled={assignToClassMutation.isPending}>
              Cancel
            </Button>
            <LoadingButton
              onClick={handleAssignToClass}
              variant="contained"
              loading={assignToClassMutation.isPending}
              disabled={!assignFormData.batch_id}
            >
              Assign
            </LoadingButton>
          </DialogActions>
        </Dialog>

        {/* Approve Dialog */}
        <Dialog
          open={approveDialogOpen}
          onClose={() => setApproveDialogOpen(false)}
          maxWidth="sm"
          fullWidth
          PaperProps={{ sx: { borderRadius: 2 } }}
        >
          <DialogTitle sx={{ pb: 1 }}>Approve Application</DialogTitle>
          <DialogContent sx={{ pt: 2 }}>
            <TextField
              fullWidth
              multiline
              rows={3}
              label="Remarks (Optional)"
              value={approveReason}
              onChange={(e) => setApproveReason(e.target.value)}
              placeholder="Add any remarks about the approval..."
              size="small"
            />
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button onClick={() => setApproveDialogOpen(false)} disabled={approveMutation.isPending}>
              Cancel
            </Button>
            <LoadingButton
              onClick={handleApprove}
              variant="contained"
              color="success"
              loading={approveMutation.isPending}
            >
              Approve
            </LoadingButton>
          </DialogActions>
        </Dialog>

        {/* Reject Dialog */}
        <Dialog
          open={rejectDialogOpen}
          onClose={() => setRejectDialogOpen(false)}
          maxWidth="sm"
          fullWidth
          PaperProps={{ sx: { borderRadius: 2 } }}
        >
          <DialogTitle sx={{ pb: 1 }}>Reject Application</DialogTitle>
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
              size="small"
            />
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button onClick={() => setRejectDialogOpen(false)} disabled={rejectMutation.isPending}>
              Cancel
            </Button>
            <LoadingButton
              onClick={handleReject}
              variant="contained"
              color="error"
              loading={rejectMutation.isPending}
              disabled={!rejectReason.trim()}
            >
              Reject
            </LoadingButton>
          </DialogActions>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <ConfirmDialog
          open={deleteConfirmOpen}
          title="Delete Application"
          description={`Are you sure you want to delete application #${application?.application_number}? This action cannot be undone.`}
          confirmLabel="Delete"
          cancelLabel="Cancel"
          destructive
          loading={deleteMutation.isPending}
          onConfirm={handleDelete}
          onCancel={() => setDeleteConfirmOpen(false)}
        />
      </PageContent>
    </Page>
  );
};

export default ApplicationDetailPage;
