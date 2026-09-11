/**
 * Invoice form component for create and edit.
 */

'use client';

import { useState } from 'react';
import {
  Box,
  Button,
  TextField,
  CircularProgress,
  Alert,
  Grid,
} from '@mui/material';
import { Invoice, CreateInvoiceInput, UpdateInvoiceInput } from './hooks';

export interface InvoiceFormProps {
  invoice?: Invoice;
  error?: string | null;
  onSubmit: (data: CreateInvoiceInput | UpdateInvoiceInput) => Promise<void>;
  onCancel?: () => void;
}

export function InvoiceForm({
  invoice,
  error,
  onSubmit,
  onCancel,
}: InvoiceFormProps) {
  const [formData, setFormData] = useState<CreateInvoiceInput | UpdateInvoiceInput>(
    invoice
      ? {
          amount: invoice.amount,
          due_date: invoice.due_date,
          status: invoice.status,
          notes: invoice.notes,
        }
      : {
          student_id: '',
          invoice_number: '',
          amount: 0,
          due_date: '',
          notes: '',
        }
  );

  const [submitting, setSubmitting] = useState(false);

  const isCreate = !invoice;

  const handleChange = (field: string, value: any) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit(formData);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit} sx={{ maxWidth: 600 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        {isCreate && (
          <>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Student ID"
                value={(formData as CreateInvoiceInput).student_id || ''}
                onChange={(e) => handleChange('student_id', e.target.value)}
                required
                disabled={submitting}
              />
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Invoice Number"
                value={(formData as CreateInvoiceInput).invoice_number || ''}
                onChange={(e) => handleChange('invoice_number', e.target.value)}
                required
                disabled={submitting}
              />
            </Grid>
          </>
        )}

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Amount"
            type="number"
            inputProps={{ step: '0.01' }}
            value={formData.amount || 0}
            onChange={(e) => handleChange('amount', parseFloat(e.target.value))}
            required
            disabled={submitting}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Due Date"
            type="date"
            value={formData.due_date || ''}
            onChange={(e) => handleChange('due_date', e.target.value)}
            required
            disabled={submitting}
            InputLabelProps={{ shrink: true }}
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Notes"
            multiline
            rows={3}
            value={formData.notes || ''}
            onChange={(e) => handleChange('notes', e.target.value)}
            disabled={submitting}
          />
        </Grid>

        <Grid item xs={12} sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
          {onCancel && (
            <Button onClick={onCancel} disabled={submitting}>
              Cancel
            </Button>
          )}
          <Button
            type="submit"
            variant="contained"
            disabled={submitting}
            sx={{ minWidth: 120 }}
          >
            {submitting ? <CircularProgress size={24} /> : isCreate ? 'Create' : 'Save'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
