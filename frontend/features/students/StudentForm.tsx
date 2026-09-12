/**
 * Student form component for create and edit.
 *
 * Reused for both:
 * - Create new student
 * - Edit existing student
 */

'use client';

import {
  Box,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Alert,
  Grid,
} from '@mui/material';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Student, CreateStudentInput, UpdateStudentInput } from './hooks';
import {
  createStudentSchema,
  updateStudentSchema,
  CreateStudentFormValues,
  UpdateStudentFormValues,
} from './schemas';

export interface StudentFormProps {
  student?: Student;
  error?: string | null;
  onSubmit: (data: CreateStudentInput | UpdateStudentInput) => Promise<void>;
  onCancel?: () => void;
}

export function StudentForm({
  student,
  error,
  onSubmit,
  onCancel,
}: StudentFormProps) {
  const isCreate = !student;

  const createForm = useForm<CreateStudentFormValues>({
    resolver: zodResolver(createStudentSchema),
    defaultValues: {
      admission_number: '',
      full_name: '',
      date_of_birth: '',
      gender: 'M',
      email: '',
      phone: '',
      batch_id: '',
    },
  });

  const updateForm = useForm<UpdateStudentFormValues>({
    resolver: zodResolver(updateStudentSchema),
    defaultValues: {
      full_name: student?.full_name || '',
      email: student?.email || '',
      phone: student?.phone || '',
      batch_id: student?.batch_id || '',
    },
  });

  const form = isCreate ? createForm : updateForm;
  const control = form.control as unknown as typeof createForm.control;
  const errors = form.formState.errors as Record<string, { message?: string } | undefined>;
  const isSubmitting = form.formState.isSubmitting;

  const submitHandler = form.handleSubmit(async (data) => {
    await onSubmit(data as CreateStudentInput | UpdateStudentInput);
  });

  return (
    <Box component="form" onSubmit={submitHandler} sx={{ maxWidth: 600 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        {/* Create-only fields */}
        {isCreate && (
          <>
            <Grid item xs={12}>
              <Controller
                name="admission_number"
                control={createForm.control}
                render={({ field }) => (
                  <TextField
                    {...field}
                    fullWidth
                    label="Admission Number"
                    required
                    disabled={isSubmitting}
                    error={!!createForm.formState.errors.admission_number}
                    helperText={createForm.formState.errors.admission_number?.message}
                  />
                )}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <Controller
                name="date_of_birth"
                control={createForm.control}
                render={({ field }) => (
                  <TextField
                    {...field}
                    fullWidth
                    label="Date of Birth"
                    type="date"
                    required
                    disabled={isSubmitting}
                    InputLabelProps={{ shrink: true }}
                    error={!!createForm.formState.errors.date_of_birth}
                    helperText={createForm.formState.errors.date_of_birth?.message}
                  />
                )}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth disabled={isSubmitting}>
                <InputLabel>Gender</InputLabel>
                <Controller
                  name="gender"
                  control={createForm.control}
                  render={({ field }) => (
                    <Select {...field} label="Gender">
                      <MenuItem value="M">Male</MenuItem>
                      <MenuItem value="F">Female</MenuItem>
                      <MenuItem value="O">Other</MenuItem>
                    </Select>
                  )}
                />
              </FormControl>
            </Grid>
          </>
        )}

        {/* Common fields */}
        <Grid item xs={12}>
          <Controller
            name="full_name"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Full Name"
                required
                disabled={isSubmitting}
                error={!!errors.full_name}
                helperText={errors.full_name?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="email"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Email"
                type="email"
                disabled={isSubmitting}
                error={!!errors.email}
                helperText={errors.email?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="phone"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Phone"
                disabled={isSubmitting}
                error={!!errors.phone}
                helperText={errors.phone?.message}
              />
            )}
          />
        </Grid>

        {/* Batch selection */}
        <Grid item xs={12}>
          <Controller
            name="batch_id"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Batch ID"
                disabled={isSubmitting}
                helperText={errors.batch_id?.message || 'Leave empty for no batch assignment'}
                error={!!errors.batch_id}
              />
            )}
          />
        </Grid>

        {/* Buttons */}
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
