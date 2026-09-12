'use client';

export const dynamic = 'force-dynamic';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Button,
  Grid,
  Alert,
  Tabs,
  Tab,
  Box,
  Avatar,
  Typography,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Checkbox,
  FormControlLabel,
  Card,
  CardContent,
  Divider,
  List,
  ListItem,
  ListItemText,
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
} from '@mui/material';
import {
  Edit as EditIcon,
  ArrowBack as BackIcon,
  PersonAdd as PersonAddIcon,
  Delete as DeleteIcon,
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
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`tabpanel-${index}`}
      aria-labelledby={`tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

export default function StudentDetailPage({ params }: { params: { id: string } }) {
  const { can, isModuleEnabled, bootstrap } = useTenantStore();
  const { data: student, isLoading, error } = useStudent(params.id);

  // Tab state
  const [activeTab, setActiveTab] = useState(0);

  // Attach guardian dialog
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

  // Additional data
  const { data: feeBalance } = useStudentFeeBalance(params.id);
  const { data: attendanceSummary } = useStudentAttendanceSummary(params.id);
  const { data: documents } = useStudentDocuments(params.id);
  const { data: guardians } = useStudentGuardians(params.id);
  const attachGuardianMutation = useAttachGuardian(params.id);
  const deleteDocumentMutation = useDeleteDocument(params.id);

  if (!bootstrap) {
    return <Page><LoadingState message="Loading configuration..." /></Page>;
  }

  if (!isModuleEnabled('academics') || !can('students.view')) {
    return (
      <Page>
        <Alert severity="error">
          You do not have permission to view this student.
        </Alert>
      </Page>
    );
  }

  if (isLoading) {
    return <Page><LoadingState message="Loading student..." /></Page>;
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
    } catch (err) {
      console.error('Failed to attach guardian:', err);
    }
  };

  // Get active batch
  const activeBatch = student.batches?.find((b) => b.is_active);

  // Get full name with middle name
  const fullNameWithMiddle = [student.first_name, student.middle_name, student.last_name]
    .filter(Boolean)
    .join(' ');

  return (
    <Page>
      <PageHeader
        title={fullNameWithMiddle}
        description={`Admission No: ${student.admission_no}`}
        actions={
          can('students.update') && (
            <Link href={`/dashboard/students/${student.id}/edit`} passHref legacyBehavior>
              <Button component="a" variant="contained" startIcon={<EditIcon />}>
                Edit
              </Button>
            </Link>
          )
        }
        breadcrumbs={
          <Link href="/dashboard/students" passHref legacyBehavior>
            <Button startIcon={<BackIcon />} variant="text">
              Back to Students
            </Button>
          </Link>
        }
      />

      <PageContent>
        {/* Inactive alert */}
        {!student.is_active && (
          <Alert severity="warning" sx={{ mb: 3 }}>
            This student is inactive. {student.status_description && `Reason: ${student.status_description}`}
          </Alert>
        )}

        <Grid container spacing={3}>
          {/* LEFT COLUMN */}
          <Grid item xs={12} md={4}>
            {/* Basic Information */}
            <SectionCard title="Basic Information">
              <Box sx={{ textAlign: 'center', mb: 2 }}>
                <Avatar
                  sx={{ width: 80, height: 80, mx: 'auto', mb: 1, bgcolor: 'primary.main' }}
                >
                  {fullNameWithMiddle.charAt(0).toUpperCase()}
                </Avatar>
                <Typography variant="h6">{fullNameWithMiddle}</Typography>
              </Box>
              <Divider sx={{ my: 2 }} />
              <DetailField label="Admission #" value={student.admission_no} />
              <DetailField label="Admission Date" value={student.admission_date} />
              <DetailField label="Date of Birth" value={student.date_of_birth} />
              <DetailField label="Age" value={student.age ?? '-'} />
              <DetailField
                label="Gender"
                value={student.gender.charAt(0).toUpperCase() + student.gender.slice(1)}
              />
              {student.blood_group && <DetailField label="Blood Group" value={student.blood_group} />}
            </SectionCard>

            {/* Contact Information */}
            <SectionCard title="Contact Information" sx={{ mt: 3 }}>
              {student.email ? (
                <DetailField label="Email" value={student.email} truncate />
              ) : (
                <DetailField label="Email" value="-" />
              )}
              {student.phone1 ? (
                <DetailField label="Phone 1" value={student.phone1} />
              ) : (
                <DetailField label="Phone 1" value="-" />
              )}
              {student.phone2 ? (
                <DetailField label="Phone 2" value={student.phone2} />
              ) : (
                <DetailField label="Phone 2" value="-" />
              )}
            </SectionCard>

            {/* Guardians */}
            <SectionCard title="Guardians" sx={{ mt: 3 }}>
              <Button
                fullWidth
                variant="outlined"
                startIcon={<PersonAddIcon />}
                onClick={() => setAttachDialogOpen(true)}
                sx={{ mb: 2 }}
              >
                Attach Guardian
              </Button>

              {guardians?.results && guardians.results.length > 0 ? (
                <List disablePadding>
                  {guardians.results.map((guardian) => (
                    <ListItem key={guardian.id} disablePadding sx={{ mb: 1, pb: 1, borderBottom: '1px solid #eee' }}>
                      <ListItemText
                        primary={guardian.name}
                        secondary={
                          <>
                            <Typography variant="caption" display="block">
                              {guardian.relation}
                              {guardian.is_immediate_contact && (
                                <StatusBadge label="Primary" status="info" />
                              )}
                            </Typography>
                            {guardian.phone && (
                              <Typography variant="caption" display="block">
                                {guardian.phone}
                              </Typography>
                            )}
                          </>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Typography variant="body2" color="textSecondary">
                  No guardians attached
                </Typography>
              )}
            </SectionCard>
          </Grid>

          {/* RIGHT COLUMN */}
          <Grid item xs={12} md={8}>
            {/* Current Enrollment */}
            {activeBatch && (
              <SectionCard title="Current Enrollment">
                <DetailField label="Batch" value={activeBatch.name} />
                <DetailField label="Roll Number" value={activeBatch.roll_number || '-'} />
                <DetailField label="Status" value={<StatusBadge label="Active" status="success" />} />
              </SectionCard>
            )}

            {/* Tabbed Card */}
            <Card sx={{ mt: 3 }}>
              <Tabs
                value={activeTab}
                onChange={handleTabChange}
                aria-label="student detail tabs"
                sx={{ borderBottom: 1, borderColor: 'divider', pl: 2 }}
              >
                <Tab label="Attendance" id="tab-0" aria-controls="tabpanel-0" />
                <Tab label="Fees" id="tab-1" aria-controls="tabpanel-1" />
                <Tab label="Address" id="tab-2" aria-controls="tabpanel-2" />
                <Tab label="Reports" id="tab-3" aria-controls="tabpanel-3" />
                <Tab label="Documents" id="tab-4" aria-controls="tabpanel-4" />
              </Tabs>

              <CardContent>
                {/* Attendance Tab */}
                <TabPanel value={activeTab} index={0}>
                  {attendanceSummary ? (
                    <Box>
                      <Grid container spacing={2} sx={{ mb: 3 }}>
                        <Grid item xs={6} sm={3}>
                          <Paper sx={{ p: 2, textAlign: 'center' }}>
                            <Typography variant="h6">{attendanceSummary.total_days}</Typography>
                            <Typography variant="caption" color="textSecondary">
                              Total Days
                            </Typography>
                          </Paper>
                        </Grid>
                        <Grid item xs={6} sm={3}>
                          <Paper sx={{ p: 2, textAlign: 'center' }}>
                            <Typography variant="h6">{attendanceSummary.present_days}</Typography>
                            <Typography variant="caption" color="textSecondary">
                              Present
                            </Typography>
                          </Paper>
                        </Grid>
                        <Grid item xs={6} sm={3}>
                          <Paper sx={{ p: 2, textAlign: 'center' }}>
                            <Typography variant="h6">{attendanceSummary.absent_days}</Typography>
                            <Typography variant="caption" color="textSecondary">
                              Absent
                            </Typography>
                          </Paper>
                        </Grid>
                        <Grid item xs={6} sm={3}>
                          <Paper sx={{ p: 2, textAlign: 'center' }}>
                            <Typography variant="h6">{attendanceSummary.attendance_percentage}%</Typography>
                            <Typography variant="caption" color="textSecondary">
                              Percentage
                            </Typography>
                          </Paper>
                        </Grid>
                      </Grid>

                      {attendanceSummary.available_terms && attendanceSummary.available_terms.length > 0 && (
                        <FormControl fullWidth sx={{ mt: 2 }}>
                          <InputLabel>Select Term</InputLabel>
                          <Select label="Select Term" value="">
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
                    <Typography color="textSecondary">Loading attendance...</Typography>
                  )}
                </TabPanel>

                {/* Fees Tab */}
                <TabPanel value={activeTab} index={1}>
                  {feeBalance ? (
                    <Box>
                      {feeBalance.balance > 0 && (
                        <Alert severity="error" sx={{ mb: 2 }}>
                          Outstanding Balance: {feeBalance.balance}
                        </Alert>
                      )}
                      {feeBalance.balance === 0 && (
                        <Alert severity="success" sx={{ mb: 2 }}>
                          No outstanding fees
                        </Alert>
                      )}
                      {feeBalance.balance < 0 && (
                        <Alert severity="info" sx={{ mb: 2 }}>
                          Credit Balance: {Math.abs(feeBalance.balance)}
                        </Alert>
                      )}
                    </Box>
                  ) : (
                    <Typography color="textSecondary">Loading fee information...</Typography>
                  )}
                </TabPanel>

                {/* Address Tab */}
                <TabPanel value={activeTab} index={2}>
                  {student.address_line1 || student.city || student.state ? (
                    <Box>
                      <DetailField
                        label="Address"
                        value={[student.address_line1, student.address_line2]
                          .filter(Boolean)
                          .join(', ') || '-'}
                      />
                      <DetailField
                        label="City / State"
                        value={[student.city, student.state].filter(Boolean).join(', ') || '-'}
                      />
                      <DetailField label="Pin Code" value={student.pin_code || '-'} />
                      <DetailField label="Country" value={student.country_name || '-'} />
                    </Box>
                  ) : (
                    <Typography color="textSecondary">No address information available</Typography>
                  )}
                </TabPanel>

                {/* Reports Tab */}
                <TabPanel value={activeTab} index={3}>
                  <Typography variant="body2" color="textSecondary">
                    Report generation features coming soon
                  </Typography>
                </TabPanel>

                {/* Documents Tab */}
                <TabPanel value={activeTab} index={4}>
                  {documents?.results && documents.results.length > 0 ? (
                    <TableContainer>
                      <Table>
                        <TableHead>
                          <TableRow>
                            <TableCell>Category</TableCell>
                            <TableCell>Filename</TableCell>
                            <TableCell>Uploaded</TableCell>
                            <TableCell align="right">Actions</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {documents.results.map((doc) => (
                            <TableRow key={doc.id}>
                              <TableCell>{doc.category_name}</TableCell>
                              <TableCell>{doc.original_filename}</TableCell>
                              <TableCell>{new Date(doc.uploaded_at).toLocaleDateString()}</TableCell>
                              <TableCell align="right">
                                <IconButton
                                  size="small"
                                  onClick={() => deleteDocumentMutation.mutate(doc.id)}
                                >
                                  <DeleteIcon fontSize="small" />
                                </IconButton>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  ) : (
                    <Typography color="textSecondary">No documents uploaded</Typography>
                  )}
                </TabPanel>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Attach Guardian Dialog */}
        <Dialog open={attachDialogOpen} onClose={() => setAttachDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Attach Guardian</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', gap: 2, my: 2 }}>
              <Button
                variant={guardianMode === 'existing' ? 'contained' : 'outlined'}
                onClick={() => setGuardianMode('existing')}
              >
                Link Existing
              </Button>
              <Button
                variant={guardianMode === 'new' ? 'contained' : 'outlined'}
                onClick={() => setGuardianMode('new')}
              >
                Create New
              </Button>
            </Box>

            {guardianMode === 'existing' ? (
              <TextField
                fullWidth
                label="Guardian ID"
                value={guardianForm.guardian_id}
                onChange={(e) => setGuardianForm({ ...guardianForm, guardian_id: e.target.value })}
                margin="normal"
              />
            ) : (
              <>
                <TextField
                  fullWidth
                  label="First Name"
                  value={guardianForm.first_name}
                  onChange={(e) => setGuardianForm({ ...guardianForm, first_name: e.target.value })}
                  margin="normal"
                />
                <TextField
                  fullWidth
                  label="Last Name"
                  value={guardianForm.last_name}
                  onChange={(e) => setGuardianForm({ ...guardianForm, last_name: e.target.value })}
                  margin="normal"
                />
                <TextField
                  fullWidth
                  label="Mobile Phone"
                  value={guardianForm.mobile_phone}
                  onChange={(e) => setGuardianForm({ ...guardianForm, mobile_phone: e.target.value })}
                  margin="normal"
                />
                <TextField
                  fullWidth
                  label="Email"
                  type="email"
                  value={guardianForm.email}
                  onChange={(e) => setGuardianForm({ ...guardianForm, email: e.target.value })}
                  margin="normal"
                />
                <TextField
                  fullWidth
                  label="Occupation"
                  value={guardianForm.occupation}
                  onChange={(e) => setGuardianForm({ ...guardianForm, occupation: e.target.value })}
                  margin="normal"
                />
              </>
            )}

            <TextField
              fullWidth
              label="Relationship"
              value={guardianForm.relation}
              onChange={(e) => setGuardianForm({ ...guardianForm, relation: e.target.value })}
              margin="normal"
            />

            <FormControlLabel
              control={
                <Checkbox
                  checked={guardianForm.is_immediate_contact}
                  onChange={(e) =>
                    setGuardianForm({ ...guardianForm, is_immediate_contact: e.target.checked })
                  }
                />
              }
              label="Set as primary contact"
              sx={{ mt: 2 }}
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setAttachDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={handleAttachGuardian}
              variant="contained"
              disabled={attachGuardianMutation.isPending}
            >
              Attach
            </Button>
          </DialogActions>
        </Dialog>
      </PageContent>
    </Page>
  );
}
