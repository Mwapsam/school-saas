'use client';

export const dynamic = 'force-dynamic';

import { useState } from 'react';
import Link from 'next/link';
import {
  Button,
  Grid,
  Alert,
  Tabs,
  Tab,
  Box,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Checkbox,
  FormControlLabel,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Chip,
  Paper,
  Tooltip,
} from '@mui/material';
import {
  Edit as EditIcon,
  ArrowBack as BackIcon,
  PersonAdd as PersonAddIcon,
  Delete as DeleteIcon,
  Phone as PhoneIcon,
  Email as EmailIcon,
  Description as DocumentIcon,
} from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import {
  useStudent,
  useStudentFeeBalance,
  useStudentAttendanceSummary,
  useStudentDocuments,
  useDeleteDocument,
  useStudentGuardians,
  useAttachGuardian,
} from '@/features/students/hooks';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { SectionCard, DetailField } from '@/components/page';
import { StatusBadge } from '@/components/data/StatusBadge';
import { LoadingButton } from '@/design-system/components/LoadingButton';
import { MetricTile } from '@/design-system/components/MetricTile';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';
import { ConfirmDialog } from '@/components/feedback/ConfirmDialog';
import { alpha } from '@mui/material/styles';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index, ...other }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`student-tabpanel-${index}`}
      aria-labelledby={`student-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 2.5 }}>{children}</Box>}
    </div>
  );
}

function EmptyState({ message, icon }: { message: string; icon?: React.ReactNode }) {
  return (
    <Box
      sx={{
        py: 5,
        px: 2,
        textAlign: 'center',
        color: 'text.secondary',
      }}
    >
      {icon && (
        <Box sx={{ mb: 1.5, opacity: 0.45, display: 'flex', justifyContent: 'center' }}>
          {icon}
        </Box>
      )}
      <Typography variant="body2" color="text.secondary">
        {message}
      </Typography>
    </Box>
  );
}

export default function StudentDetailPage({ params }: { params: { id: string } }) {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: student, isLoading, error } = useStudent(params.id);

  const [activeTab, setActiveTab] = useState(0);

  const [attachDialogOpen, setAttachDialogOpen] = useState(false);
  const [guardianMode, setGuardianMode] = useState<'existing' | 'new'>('existing');
  const [guardianForm, setGuardianForm] = useState({
    guardian_id: '',
    first_name: '',
    last_name: '',
    mobile_phone: '',
    email: '',
    occupation: '',
    relation: '',
    is_immediate_contact: false,
  });

  const [deleteDocumentId, setDeleteDocumentId] = useState<string | null>(null);

  const { data: feeBalance } = useStudentFeeBalance(params.id);
  const { data: attendanceSummary } = useStudentAttendanceSummary(params.id);
  const { data: documents } = useStudentDocuments(params.id);
  const { data: guardians } = useStudentGuardians(params.id);
  const attachGuardianMutation = useAttachGuardian(params.id);
  const deleteDocumentMutation = useDeleteDocument(params.id);

  if (!bootstrap) {
    return (
      <Page>
        <LoadingState message="Loading configuration..." />
      </Page>
    );
  }

  if (!isModuleEnabled('academics') || !can('students.view')) {
    return (
      <Page>
        <Alert severity="error">You do not have permission to view this student.</Alert>
      </Page>
    );
  }

  if (isLoading) {
    return (
      <Page>
        <LoadingState message="Loading student..." />
      </Page>
    );
  }

  if (error || !student) {
    return (
      <Page>
        <ErrorState
          title="Failed to load student"
          error={error?.message || 'Student not found'}
          onRetry={() => window.location.reload()}
        />
      </Page>
    );
  }

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const resetGuardianForm = () => {
    setGuardianForm({
      guardian_id: '',
      first_name: '',
      last_name: '',
      mobile_phone: '',
      email: '',
      occupation: '',
      relation: '',
      is_immediate_contact: false,
    });
    setGuardianMode('existing');
  };

  const handleAttachGuardian = async () => {
    try {
      const payload =
        guardianMode === 'existing'
          ? {
              guardian_id: guardianForm.guardian_id,
              relation: guardianForm.relation,
              is_immediate_contact: guardianForm.is_immediate_contact,
            }
          : {
              first_name: guardianForm.first_name,
              last_name: guardianForm.last_name,
              mobile_phone: guardianForm.mobile_phone,
              email: guardianForm.email,
              occupation: guardianForm.occupation,
              relation: guardianForm.relation,
              is_immediate_contact: guardianForm.is_immediate_contact,
            };

      await attachGuardianMutation.mutateAsync(payload as any);
      setAttachDialogOpen(false);
      resetGuardianForm();
    } catch (err) {
      console.error('Failed to attach guardian:', err);
    }
  };

  const activeBatch = student.batches?.find((b) => b.is_active);

  const fullNameWithMiddle = [student.first_name, student.middle_name, student.last_name]
    .filter(Boolean)
    .join(' ');

  const genderLabel =
    student.gender?.charAt(0).toUpperCase() + student.gender?.slice(1).toLowerCase() || '—';


  const canUpdate = can('students.update');

  return (
    <Page>
      <PageHeader
        title={fullNameWithMiddle}
        description={`Admission No: ${student.admission_no}`}
        actions={
    <Stack direction="row" spacing={1.5} alignItems="center">
      <Button
        component={Link}
        href="/dashboard/students"
        startIcon={<BackIcon />}
        variant="outlined"
        color="inherit"
      >
        Back to Students
      </Button>
      {canUpdate && (
        <Button
          component={Link}
          href={`/dashboard/students/${student.id}/edit`}
          variant="contained"
          startIcon={<EditIcon />}
        >
          Edit Student
        </Button>
      )}
    </Stack>
  }
/>

      <PageContent>
        {!student.is_active && (
          <Alert severity="warning" sx={{ mb: 3 }} variant="outlined">
            This student is inactive
            {student.status_description ? `. Reason: ${student.status_description}` : '.'}
          </Alert>
        )}

        <Grid container spacing={3}>
          {/* ── LEFT ─────────────────────────────────────────────── */}
          <Grid item xs={12} md={4}>
            <Stack spacing={2.5}>
              {/* Profile */}
              <SectionCard>
                <Stack spacing={0.25}>
                  <DetailField label="Admission #" value={student.admission_no} />
                  <DetailField label="Admission Date" value={student.admission_date || '—'} />
                  <DetailField label="Date of Birth" value={student.date_of_birth || '—'} />
                  <DetailField label="Age" value={student.age ?? '—'} />
                  <DetailField label="Gender" value={genderLabel} />
                  {student.blood_group && (
                    <DetailField label="Blood Group" value={student.blood_group} />
                  )}
                </Stack>
              </SectionCard>

              {/* Contact */}
              <SectionCard title="Contact">
                <Stack spacing={1.75}>
                  {/* Email */}
                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                      Email
                    </Typography>
                    {student.email ? (
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <EmailIcon sx={{ fontSize: 18, color: 'text.secondary', flexShrink: 0 }} />
                        <Typography
                          component="a"
                          href={`mailto:${student.email}`}
                          variant="body2"
                          sx={{
                            color: 'primary.main',
                            textDecoration: 'none',
                            wordBreak: 'break-all',
                            '&:hover': { textDecoration: 'underline' },
                            flex: 1,
                          }}
                        >
                          {student.email}
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

                  {/* Phone(s) */}
                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5, fontWeight: 550 }}>
                      Phone
                    </Typography>
                    <Stack spacing={0.75}>
                      {student.phone1 ? (
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <PhoneIcon sx={{ fontSize: 18, color: 'text.secondary', flexShrink: 0 }} />
                          <Typography
                            component="a"
                            href={`tel:${student.phone1}`}
                            variant="body2"
                            sx={{
                              color: 'text.primary',
                              textDecoration: 'none',
                              '&:hover': { color: 'primary.main' },
                              flex: 1,
                            }}
                          >
                            {student.phone1}
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
                      {student.phone2 && (
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <PhoneIcon sx={{ fontSize: 18, color: 'text.secondary', flexShrink: 0 }} />
                          <Typography
                            component="a"
                            href={`tel:${student.phone2}`}
                            variant="body2"
                            sx={{
                              color: 'text.primary',
                              textDecoration: 'none',
                              '&:hover': { color: 'primary.main' },
                              flex: 1,
                            }}
                          >
                            {student.phone2}
                          </Typography>
                        </Stack>
                      )}
                    </Stack>
                  </Box>
                </Stack>
              </SectionCard>

              {/* Guardians */}
              <SectionCard
                title="Guardians"
                actions={
                  <Button
                    size="small"
                    startIcon={<PersonAddIcon />}
                    onClick={() => setAttachDialogOpen(true)}
                  >
                    Attach
                  </Button>
                }
              >
                {guardians?.results && guardians.results.length > 0 ? (
                  <Stack spacing={1.25} sx={{ mt: 0.5 }}>
                    {guardians.results.map((guardian) => (
                      <Paper
                        key={guardian.id}
                        variant="outlined"
                        sx={{
                          p: 1.5,
                          borderRadius: 2,
                          bgcolor: (theme) =>
                            guardian.is_immediate_contact
                              ? alpha(theme.palette.info.main, 0.04)
                              : 'transparent',
                        }}
                      >
                        <Stack spacing={0.75}>
                          {/* Name and Primary Badge */}
                          <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
                            <Typography
                              variant="subtitle2"
                              sx={{ fontWeight: 600, flex: 1, minWidth: 0 }}
                              noWrap
                            >
                              {guardian.name}
                            </Typography>
                            {guardian.is_immediate_contact && (
                              <Chip
                                label="Primary"
                                size="small"
                                color="info"
                                variant="outlined"
                                sx={{ height: 20, fontSize: '0.7rem', flexShrink: 0 }}
                              />
                            )}
                          </Stack>

                          {/* Relation */}
                          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                            {guardian.relation || 'Guardian'}
                          </Typography>

                          {/* Phone */}
                          {guardian.phone && (
                            <Stack direction="row" alignItems="center" spacing={0.75} sx={{ mt: 0.25 }}>
                              <PhoneIcon sx={{ fontSize: 16, color: 'text.secondary', flexShrink: 0 }} />
                              <Typography
                                component="a"
                                href={`tel:${guardian.phone}`}
                                variant="body2"
                                sx={{
                                  color: 'text.primary',
                                  textDecoration: 'none',
                                  '&:hover': { color: 'primary.main' },
                                }}
                              >
                                {guardian.phone}
                              </Typography>
                            </Stack>
                          )}
                        </Stack>
                      </Paper>
                    ))}
                  </Stack>
                ) : (
                  <EmptyState message="No guardians attached yet" />
                )}
              </SectionCard>
            </Stack>
          </Grid>

          {/* ── RIGHT ────────────────────────────────────────────── */}
          <Grid item xs={12} md={8}>
            <Stack spacing={2.5}>
              {/* Enrollment banner */}
              {activeBatch && (
                <SectionCard>
                  <Stack
                    direction={{ xs: 'column', sm: 'row' }}
                    alignItems={{ sm: 'center' }}
                    justifyContent="space-between"
                    spacing={2}
                  >
                    <Box>
                      <Typography variant="overline" color="text.secondary" sx={{ letterSpacing: 0.8 }}>
                        Current Enrollment
                      </Typography>
                      <Typography variant="h6" sx={{ fontWeight: 650, mt: 0.25 }}>
                        {activeBatch.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
                        Roll No: {activeBatch.roll_number || '—'}
                      </Typography>
                    </Box>
                    <StatusBadge label="Active" status="success" />
                  </Stack>
                </SectionCard>
              )}

              {/* Tabbed content */}
              <SectionCard sx={{ overflow: 'hidden' }}>
                <Tabs
                  value={activeTab}
                  onChange={handleTabChange}
                  aria-label="Student details"
                  variant="scrollable"
                  scrollButtons="auto"
                  sx={{
                    borderBottom: 1,
                    borderColor: 'divider',
                    minHeight: 48,
                    '& .MuiTab-root': {
                      minHeight: 48,
                      textTransform: 'none',
                      fontWeight: 550,
                      fontSize: '0.9rem',
                    },
                  }}
                >
                  <Tab label="Attendance" id="student-tab-0" aria-controls="student-tabpanel-0" />
                  <Tab label="Fees" id="student-tab-1" aria-controls="student-tabpanel-1" />
                  <Tab label="Address" id="student-tab-2" aria-controls="student-tabpanel-2" />
                  <Tab label="Reports" id="student-tab-3" aria-controls="student-tabpanel-3" />
                  <Tab label="Documents" id="student-tab-4" aria-controls="student-tabpanel-4" />
                </Tabs>

                {/* Attendance */}
                <TabPanel value={activeTab} index={0}>
                  {attendanceSummary ? (
                    <Box>
                      <Grid container spacing={2} sx={{ mb: 1 }}>
                        <Grid item xs={6} sm={3}>
                          <MetricTile value={attendanceSummary.total_days} label="Total Days" />
                        </Grid>
                        <Grid item xs={6} sm={3}>
                          <MetricTile value={attendanceSummary.present_days} label="Present" />
                        </Grid>
                        <Grid item xs={6} sm={3}>
                          <MetricTile value={attendanceSummary.absent_days} label="Absent" />
                        </Grid>
                        <Grid item xs={6} sm={3}>
                          <MetricTile
                            value={`${attendanceSummary.attendance_percentage}%`}
                            label="Percentage"
                          />
                        </Grid>
                      </Grid>

                      {attendanceSummary.available_terms &&
                        attendanceSummary.available_terms.length > 0 && (
                          <FormControl fullWidth size="small" sx={{ mt: 2.5, maxWidth: 320 }}>
                            <InputLabel id="term-select-label">Filter by term</InputLabel>
                            <Select
                              labelId="term-select-label"
                              label="Filter by term"
                              value=""
                              displayEmpty
                            >
                              <MenuItem value="">
                                <em>All terms</em>
                              </MenuItem>
                              {attendanceSummary.available_terms.map((term) => (
                                <MenuItem key={term.id} value={term.id}>
                                  {term.name}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        )}
                    </Box>
                  ) : (
                    <EmptyState message="Loading attendance summary…" />
                  )}
                </TabPanel>

                {/* Fees */}
                <TabPanel value={activeTab} index={1}>
                  {feeBalance ? (
                    <Box>
                      {feeBalance.balance > 0 && (
                        <Alert severity="error" variant="outlined" sx={{ mb: 2 }}>
                          Outstanding balance of{' '}
                          <strong>{feeBalance.balance}</strong>
                        </Alert>
                      )}
                      {feeBalance.balance === 0 && (
                        <Alert severity="success" variant="outlined" sx={{ mb: 2 }}>
                          No outstanding fees
                        </Alert>
                      )}
                      {feeBalance.balance < 0 && (
                        <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
                          Credit balance of{' '}
                          <strong>{Math.abs(feeBalance.balance)}</strong>
                        </Alert>
                      )}

                      <Paper
                        variant="outlined"
                        sx={{
                          p: 2.5,
                          borderRadius: 2,
                          display: 'flex',
                          alignItems: 'baseline',
                          gap: 1,
                        }}
                      >
                        <Typography variant="body2" color="text.secondary">
                          Current balance
                        </Typography>
                        <Typography
                          variant="h5"
                          sx={{
                            fontWeight: 700,
                            color:
                              feeBalance.balance > 0
                                ? 'error.main'
                                : feeBalance.balance < 0
                                  ? 'info.main'
                                  : 'success.main',
                          }}
                        >
                          {feeBalance.balance}
                        </Typography>
                      </Paper>
                    </Box>
                  ) : (
                    <EmptyState message="Loading fee information…" />
                  )}
                </TabPanel>

                {/* Address */}
                <TabPanel value={activeTab} index={2}>
                  {student.address_line1 || student.city || student.state ? (
                    <Stack spacing={0.25}>
                      <DetailField
                        label="Address"
                        value={
                          [student.address_line1, student.address_line2]
                            .filter(Boolean)
                            .join(', ') || '—'
                        }
                      />
                      <DetailField
                        label="City / State"
                        value={[student.city, student.state].filter(Boolean).join(', ') || '—'}
                      />
                      <DetailField label="Pin Code" value={student.pin_code || '—'} />
                      <DetailField label="Country" value={student.country_name || '—'} />
                    </Stack>
                  ) : (
                    <EmptyState message="No address information available" />
                  )}
                </TabPanel>

                {/* Reports */}
                <TabPanel value={activeTab} index={3}>
                  <EmptyState
                    message="Report generation is coming soon"
                    icon={<DocumentIcon sx={{ fontSize: 40 }} />}
                  />
                </TabPanel>

                {/* Documents */}
                <TabPanel value={activeTab} index={4}>
                  {documents?.results && documents.results.length > 0 ? (
                    <TableContainer>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell sx={{ fontWeight: 600 }}>Category</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Filename</TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>Uploaded</TableCell>
                            <TableCell align="right" sx={{ fontWeight: 600 }}>
                              Actions
                            </TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {documents.results.map((doc) => (
                            <TableRow key={doc.id} hover>
                              <TableCell>{doc.category_name}</TableCell>
                              <TableCell>
                                <Typography variant="body2" noWrap sx={{ maxWidth: 220 }}>
                                  {doc.original_filename}
                                </Typography>
                              </TableCell>
                              <TableCell>
                                {new Date(doc.uploaded_at).toLocaleDateString()}
                              </TableCell>
                              <TableCell align="right">
                                <Tooltip title="Delete document">
                                  <IconButton
                                    size="small"
                                    color="error"
                                    onClick={() => setDeleteDocumentId(doc.id)}
                                    aria-label={`Delete ${doc.original_filename}`}
                                  >
                                    <DeleteIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  ) : (
                    <EmptyState
                      message="No documents uploaded yet"
                      icon={<DocumentIcon sx={{ fontSize: 40 }} />}
                    />
                  )}
                </TabPanel>
              </SectionCard>
            </Stack>
          </Grid>
        </Grid>

        {/* Attach Guardian Dialog */}
        <Dialog
          open={attachDialogOpen}
          onClose={() => {
            if (!attachGuardianMutation.isPending) {
              setAttachDialogOpen(false);
              resetGuardianForm();
            }
          }}
          maxWidth="sm"
          fullWidth
          PaperProps={{ sx: { borderRadius: 2 } }}
        >
          <DialogTitle sx={{ pb: 1 }}>Attach Guardian</DialogTitle>
          <DialogContent>
            <ToggleButtonGroup
              value={guardianMode}
              exclusive
              onChange={(_e, newMode) => {
                if (newMode !== null) setGuardianMode(newMode);
              }}
              fullWidth
              size="small"
              sx={{ mb: 2.5, mt: 0.5 }}
            >
              <ToggleButton value="existing">Link existing</ToggleButton>
              <ToggleButton value="new">Create new</ToggleButton>
            </ToggleButtonGroup>

            <Stack spacing={2}>
              {guardianMode === 'existing' ? (
                <TextField
                  fullWidth
                  label="Guardian ID"
                  placeholder="Enter guardian ID"
                  value={guardianForm.guardian_id}
                  onChange={(e) =>
                    setGuardianForm({ ...guardianForm, guardian_id: e.target.value })
                  }
                  helperText="Paste the ID of an existing guardian record"
                  size="small"
                />
              ) : (
                <>
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                    <TextField
                      fullWidth
                      label="First name"
                      value={guardianForm.first_name}
                      onChange={(e) =>
                        setGuardianForm({ ...guardianForm, first_name: e.target.value })
                      }
                      size="small"
                      required
                    />
                    <TextField
                      fullWidth
                      label="Last name"
                      value={guardianForm.last_name}
                      onChange={(e) =>
                        setGuardianForm({ ...guardianForm, last_name: e.target.value })
                      }
                      size="small"
                      required
                    />
                  </Stack>
                  <TextField
                    fullWidth
                    label="Mobile phone"
                    value={guardianForm.mobile_phone}
                    onChange={(e) =>
                      setGuardianForm({ ...guardianForm, mobile_phone: e.target.value })
                    }
                    size="small"
                  />
                  <TextField
                    fullWidth
                    label="Email"
                    type="email"
                    value={guardianForm.email}
                    onChange={(e) =>
                      setGuardianForm({ ...guardianForm, email: e.target.value })
                    }
                    size="small"
                  />
                  <TextField
                    fullWidth
                    label="Occupation"
                    value={guardianForm.occupation}
                    onChange={(e) =>
                      setGuardianForm({ ...guardianForm, occupation: e.target.value })
                    }
                    size="small"
                  />
                </>
              )}

              <TextField
                fullWidth
                label="Relationship"
                placeholder="e.g. Father, Mother, Guardian"
                value={guardianForm.relation}
                onChange={(e) =>
                  setGuardianForm({ ...guardianForm, relation: e.target.value })
                }
                size="small"
              />

              <FormControlLabel
                control={
                  <Checkbox
                    checked={guardianForm.is_immediate_contact}
                    onChange={(e) =>
                      setGuardianForm({
                        ...guardianForm,
                        is_immediate_contact: e.target.checked,
                      })
                    }
                  />
                }
                label="Set as primary contact"
              />
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2.5 }}>
            <Button
              onClick={() => {
                setAttachDialogOpen(false);
                resetGuardianForm();
              }}
              disabled={attachGuardianMutation.isPending}
            >
              Cancel
            </Button>
            <LoadingButton
              onClick={handleAttachGuardian}
              variant="contained"
              loading={attachGuardianMutation.isPending}
            >
              Attach Guardian
            </LoadingButton>
          </DialogActions>
        </Dialog>

        {/* Document delete confirmation */}
        <ConfirmDialog
          open={deleteDocumentId !== null}
          title="Delete document?"
          description="This action cannot be undone. The document will be permanently removed."
          confirmLabel="Delete"
          cancelLabel="Cancel"
          destructive
          loading={deleteDocumentMutation.isPending}
          onConfirm={async () => {
            if (deleteDocumentId) {
              await deleteDocumentMutation.mutateAsync(deleteDocumentId);
              setDeleteDocumentId(null);
            }
          }}
          onCancel={() => setDeleteDocumentId(null)}
        />
      </PageContent>
    </Page>
  );
}