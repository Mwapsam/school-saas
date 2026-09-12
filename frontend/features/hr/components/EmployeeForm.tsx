/**
 * Employee form component for create and edit.
 *
 * Reused for both:
 * - Create new employee
 * - Edit existing employee
 */

'use client';

import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  Box,
  Button,
  TextField,
  CircularProgress,
  Alert,
  Grid,
  FormControlLabel,
  Switch,
} from '@mui/material';
import { Employee, CreateEmployeeInput, UpdateEmployeeInput } from '../hooks';
import {
  createEmployeeSchema,
  updateEmployeeSchema,
  CreateEmployeeFormValues,
  UpdateEmployeeFormValues,
} from '../schemas';

export interface EmployeeFormProps {
  employee?: Employee;
  error?: string | null;
  onSubmit: (data: CreateEmployeeInput | UpdateEmployeeInput) => Promise<void>;
  onCancel?: () => void;
}

export function EmployeeForm({ employee, error, onSubmit, onCancel }: EmployeeFormProps) {
  const isCreate = !employee;

  const {
    control,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<CreateEmployeeFormValues | UpdateEmployeeFormValues>({
    resolver: zodResolver(isCreate ? createEmployeeSchema : updateEmployeeSchema) as any,
    defaultValues: employee
      ? {
          full_name: employee.full_name,
          email: employee.email || '',
          phone: employee.phone || '',
          department: employee.department || '',
          position: employee.position || '',
          is_active: employee.is_active,
        }
      : {
          employee_id: '',
          full_name: '',
          email: '',
          phone: '',
          department: '',
          position: '',
          hire_date: '',
        },
  });

  const submitting = isSubmitting;

  const onValid = async (data: CreateEmployeeFormValues | UpdateEmployeeFormValues) => {
    await onSubmit(data as CreateEmployeeInput | UpdateEmployeeInput);
  };

  return (
    <Box component="form" onSubmit={handleSubmit(onValid)} sx={{ maxWidth: 600 }}>
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
                name="employee_id"
                control={control}
                render={({ field, fieldState }) => (
                  <TextField
                    {...field}
                    fullWidth
                    label="Employee ID"
                    required
                    disabled={submitting}
                    error={!!fieldState.error}
                    helperText={fieldState.error?.message}
                  />
                )}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <Controller
                name="hire_date"
                control={control}
                render={({ field, fieldState }) => (
                  <TextField
                    {...field}
                    fullWidth
                    label="Hire Date"
                    type="date"
                    required
                    disabled={submitting}
                    InputLabelProps={{ shrink: true }}
                    error={!!fieldState.error}
                    helperText={fieldState.error?.message}
                  />
                )}
              />
            </Grid>
          </>
        )}

        {/* Common fields */}
        <Grid item xs={12}>
          <Controller
            name="full_name"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Full Name"
                required
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="email"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Email"
                type="email"
                required={isCreate}
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="phone"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Phone"
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="department"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Department"
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="position"
            control={control}
            render={({ field, fieldState }) => (
              <TextField
                {...field}
                fullWidth
                label="Position"
                disabled={submitting}
                error={!!fieldState.error}
                helperText={fieldState.error?.message}
              />
            )}
          />
        </Grid>

        {/* Edit-only fields */}
        {!isCreate && (
          <Grid item xs={12}>
            <Controller
              name="is_active"
              control={control}
              render={({ field }) => (
                <FormControlLabel
                  control={
                    <Switch
                      checked={!!field.value}
                      onChange={(e) => field.onChange(e.target.checked)}
                      disabled={submitting}
                    />
                  }
                  label="Active"
                />
              )}
            />
          </Grid>
        )}

        {/* Buttons */}
        <Grid item xs={12} sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
          {onCancel && (
            <Button onClick={onCancel} disabled={submitting}>
              Cancel
            </Button>
          )}
          <Button type="submit" variant="contained" disabled={submitting} sx={{ minWidth: 120 }}>
            {submitting ? <CircularProgress size={24} /> : isCreate ? 'Create' : 'Save'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
