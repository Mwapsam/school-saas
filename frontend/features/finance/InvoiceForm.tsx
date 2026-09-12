/**
 * Invoice form component for create and edit.
 */

'use client';

import {
  Box,
  Button,
  TextField,
  CircularProgress,
  Alert,
  Grid,
} from '@mui/material';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Invoice, CreateInvoiceInput, UpdateInvoiceInput } from './hooks';
import {
  createInvoiceSchema,
  updateInvoiceSchema,
  CreateInvoiceFormValues,
  UpdateInvoiceFormValues,
} from './schemas';

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
  const isCreate = !invoice;

  const createForm = useForm<CreateInvoiceFormValues>({
    resolver: zodResolver(createInvoiceSchema),
    defaultValues: {
      student_id: '',
      invoice_number: '',
      amount: 0,
      due_date: '',
      notes: '',
    },
  });

  const updateForm = useForm<UpdateInvoiceFormValues>({
    resolver: zodResolver(updateInvoiceSchema),
    defaultValues: {
      amount: invoice?.amount ?? 0,
      due_date: invoice?.due_date || '',
      status: invoice?.status || '',
      notes: invoice?.notes || '',
    },
  });

  const form = isCreate ? createForm : updateForm;
  const control = form.control as unknown as typeof createForm.control;
  const errors = form.formState.errors as Record<string, { message?: string } | undefined>;
  const isSubmitting = form.formState.isSubmitting;

  const submitHandler = form.handleSubmit(async (data) => {
    await onSubmit(data as CreateInvoiceInput | UpdateInvoiceInput);
  });

  return (
    <Box component="form" onSubmit={submitHandler} sx={{ maxWidth: 600 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        {isCreate && (
          <>
            <Grid item xs={12}>
              <Controller
                name="student_id"
                control={createForm.control}
                render={({ field }) => (
                  <TextField
                    {...field}
                    fullWidth
                    label="Student ID"
                    required
                    disabled={isSubmitting}
                    error={!!createForm.formState.errors.student_id}
                    helperText={createForm.formState.errors.student_id?.message}
                  />
                )}
              />
            </Grid>

            <Grid item xs={12}>
              <Controller
                name="invoice_number"
                control={createForm.control}
                render={({ field }) => (
                  <TextField
                    {...field}
                    fullWidth
                    label="Invoice Number"
                    required
                    disabled={isSubmitting}
                    error={!!createForm.formState.errors.invoice_number}
                    helperText={createForm.formState.errors.invoice_number?.message}
                  />
                )}
              />
            </Grid>
          </>
        )}

        <Grid item xs={12} sm={6}>
          <Controller
            name="amount"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Amount"
                type="number"
                inputProps={{ step: '0.01' }}
                required
                disabled={isSubmitting}
                onChange={(e) => field.onChange(e.target.value === '' ? '' : parseFloat(e.target.value))}
                error={!!errors.amount}
                helperText={errors.amount?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="due_date"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Due Date"
                type="date"
                required
                disabled={isSubmitting}
                InputLabelProps={{ shrink: true }}
                error={!!errors.due_date}
                helperText={errors.due_date?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12}>
          <Controller
            name="notes"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Notes"
                multiline
                rows={3}
                disabled={isSubmitting}
                error={!!errors.notes}
                helperText={errors.notes?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
          {onCancel && (
            <Button onClick={onCancel} disabled={isSubmitting}>
              Cancel
            </Button>
          )}
          <Button
            type="submit"
            variant="contained"
            disabled={isSubmitting}
            sx={{ minWidth: 120 }}
          >
            {isSubmitting ? <CircularProgress size={24} /> : isCreate ? 'Create' : 'Save'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
