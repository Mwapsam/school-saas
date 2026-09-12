'use client';

import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  Box,
} from '@mui/material';
import { AlertCircle } from 'lucide-react';
import { colors } from '@/design-system/tokens';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  loading?: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
}

/**
 * Styled confirmation dialog component.
 *
 * Replaces all window.confirm() calls throughout the application.
 * Provides consistent styling and UX for confirmation prompts.
 *
 * Usage:
 *   const [open, setOpen] = useState(false);
 *   const [loading, setLoading] = useState(false);
 *
 *   return (
 *     <>
 *       <Button onClick={() => setOpen(true)}>Delete</Button>
 *
 *       <ConfirmDialog
 *         open={open}
 *         title="Delete student?"
 *         description="This action cannot be undone."
 *         confirmLabel="Delete"
 *         destructive
 *         loading={loading}
 *         onConfirm={async () => {
 *           setLoading(true);
 *           try {
 *             await deleteStudent(id);
 *           } finally {
 *             setLoading(false);
 *             setOpen(false);
 *           }
 *         }}
 *         onCancel={() => setOpen(false)}
 *       />
 *     </>
 *   );
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = false,
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-description"
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle id="confirm-dialog-title" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        {destructive && (
          <AlertCircle
            size={20}
            color={colors.status.error}
            style={{ flexShrink: 0 }}
          />
        )}
        {title}
      </DialogTitle>

      {description && (
        <DialogContent>
          <DialogContentText id="confirm-dialog-description">
            {description}
          </DialogContentText>
        </DialogContent>
      )}

      <DialogActions sx={{ p: 2, gap: 1 }}>
        <Button
          onClick={onCancel}
          disabled={loading}
          variant="outlined"
        >
          {cancelLabel}
        </Button>

        <Button
          onClick={onConfirm}
          disabled={loading}
          loading={loading}
          variant={destructive ? 'contained' : 'contained'}
          sx={
            destructive
              ? {
                  backgroundColor: colors.status.error,
                  '&:hover': {
                    backgroundColor: colors.status.error,
                    opacity: 0.9,
                  },
                }
              : {}
          }
        >
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
