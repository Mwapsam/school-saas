'use client';

import { useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  CircularProgress,
  Typography,
  Chip,
  Stack,
} from '@mui/material';
import { Check as ApproveIcon, Close as RejectIcon } from '@mui/icons-material';
import { useApproveApplication, useRejectApplication, type ApplicantForAssignment } from './hooks';

interface ApplicationAdminActionsProps {
  application: ApplicantForAssignment;
  onStatusChange?: () => void;
}

export function ApplicationAdminActions({
  application,
  onStatusChange,
}: ApplicationAdminActionsProps) {
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const approveMutation = useApproveApplication(application.id);
  const rejectMutation = useRejectApplication(application.id);

  const handleApprove = async () => {
    try {
      await approveMutation.mutateAsync();
      onStatusChange?.();
    } catch (err) {
      console.error('Approve failed:', err);
    }
  };

  const handleRejectConfirm = async () => {
    if (!rejectReason.trim()) {
      alert('Please provide a reason for rejection');
      return;
    }

    try {
      await rejectMutation.mutateAsync({ reason: rejectReason });
      setRejectDialogOpen(false);
      setRejectReason('');
      onStatusChange?.();
    } catch (err) {
      console.error('Reject failed:', err);
    }
  };

  // Don't show admin actions for already admitted applications
  if (application.status === 'admitted') {
    return (
      <Box>
        <Chip label="Admitted" color="success" variant="outlined" size="small" />
      </Box>
    );
  }

  if (application.status === 'rejected') {
    return (
      <Box>
        <Chip label="Rejected" color="error" variant="outlined" size="small" />
      </Box>
    );
  }

  return (
    <>
      <Stack direction="row" spacing={1}>
        <Button
          size="small"
          variant="contained"
          color="success"
          startIcon={approveMutation.isPending ? <CircularProgress size={16} /> : <ApproveIcon />}
          onClick={handleApprove}
          disabled={approveMutation.isPending || rejectMutation.isPending}
        >
          Approve
        </Button>
        <Button
          size="small"
          variant="outlined"
          color="error"
          startIcon={rejectMutation.isPending ? <CircularProgress size={16} /> : <RejectIcon />}
          onClick={() => setRejectDialogOpen(true)}
          disabled={approveMutation.isPending || rejectMutation.isPending}
        >
          Reject
        </Button>
      </Stack>

      <Dialog open={rejectDialogOpen} onClose={() => setRejectDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Reject Application</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
            Rejecting: {application.full_name} ({application.application_number})
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={3}
            label="Reason for Rejection *"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="e.g., Does not meet admission criteria, documents incomplete, etc."
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejectDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleRejectConfirm}
            variant="contained"
            color="error"
            disabled={!rejectReason.trim() || rejectMutation.isPending}
            startIcon={rejectMutation.isPending && <CircularProgress size={16} />}
          >
            {rejectMutation.isPending ? 'Rejecting...' : 'Confirm Rejection'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
