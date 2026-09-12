/**
 * Student form component for create and edit.
 *
 * Reused for both:
 * - Create new student
 * - Edit existing student
 *
 * Field selection (v1): core identity + contact fields are collected
 * (admission_no, first_name, middle_name, last_name, admission_date,
 * date_of_birth, gender, email, phone1, phone2) plus a compact "Additional
 * Information" section for address fields, since those are commonly needed
 * but not essential to a fast create flow. Deliberately omitted for now:
 * blood_group, birth_place, nationality, language, religion,
 * student_category, is_sms_enabled, status_description, photo fields - these
 * are real, writable/detail fields but are lower priority for a v1 form and
 * can be added later without shape changes. Batch assignment is intentionally
 * NOT included: Student has no direct batch FK (it's a M2M via BatchStudent)
 * and the API exposes no create/assign endpoint for it on this ViewSet -
 * only BatchViewSet.students (read) and BatchViewSet.transfer_student
 * (moves an already-assigned student). This is a known gap.
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
  Typography,
  Divider,
} from '@mui/material';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { StudentDetail, CreateStudentInput, UpdateStudentInput } from './hooks';
import {
  createStudentSchema,
  updateStudentSchema,
  CreateStudentFormValues,
  UpdateStudentFormValues,
} from './schemas';

export interface StudentFormProps {
  student?: StudentDetail;
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
      admission_no: '',
      first_name: '',
      middle_name: '',
      last_name: '',
      date_of_birth: '',
      gender: 'male',
      admission_date: '',
      email: '',
      phone1: '',
      phone2: '',
      address_line1: '',
      address_line2: '',
      city: '',
      state: '',
      pin_code: '',
    },
  });

  const updateForm = useForm<UpdateStudentFormValues>({
    resolver: zodResolver(updateStudentSchema),
    defaultValues: {
      admission_no: student?.admission_no || '',
      first_name: student?.first_name || '',
      middle_name: student?.middle_name || '',
      last_name: student?.last_name || '',
      date_of_birth: student?.date_of_birth || '',
      gender: student?.gender || 'male',
      admission_date: student?.admission_date || '',
      email: student?.email || '',
      phone1: student?.phone1 || '',
      phone2: student?.phone2 || '',
      address_line1: student?.address_line1 || '',
      address_line2: student?.address_line2 || '',
      city: student?.city || '',
      state: student?.state || '',
      pin_code: student?.pin_code || '',
      is_active: student?.is_active,
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
    <Box component="form" onSubmit={submitHandler} sx={{ maxWidth: 700 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        <Grid item xs={12} sm={4}>
          <Controller
            name="admission_no"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Admission No"
                required={isCreate}
                disabled={isSubmitting}
                error={!!errors.admission_no}
                helperText={errors.admission_no?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={4}>
          <Controller
            name="admission_date"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Admission Date"
                type="date"
                required={isCreate}
                disabled={isSubmitting}
                InputLabelProps={{ shrink: true }}
                error={!!errors.admission_date}
                helperText={errors.admission_date?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={4}>
          <Controller
            name="date_of_birth"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Date of Birth"
                type="date"
                required={isCreate}
                disabled={isSubmitting}
                InputLabelProps={{ shrink: true }}
                error={!!errors.date_of_birth}
                helperText={errors.date_of_birth?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={4}>
          <Controller
            name="first_name"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="First Name"
                required={isCreate}
                disabled={isSubmitting}
                error={!!errors.first_name}
                helperText={errors.first_name?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={4}>
          <Controller
            name="middle_name"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Middle Name"
                disabled={isSubmitting}
                error={!!errors.middle_name}
                helperText={errors.middle_name?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={4}>
          <Controller
            name="last_name"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Last Name"
                required={isCreate}
                disabled={isSubmitting}
                error={!!errors.last_name}
                helperText={errors.last_name?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={4}>
          <FormControl fullWidth disabled={isSubmitting}>
            <InputLabel>Gender</InputLabel>
            <Controller
              name="gender"
              control={control}
              render={({ field }) => (
                <Select {...field} label="Gender" value={field.value || 'male'}>
                  <MenuItem value="male">Male</MenuItem>
                  <MenuItem value="female">Female</MenuItem>
                  <MenuItem value="other">Other</MenuItem>
                </Select>
              )}
            />
          </FormControl>
        </Grid>

        <Grid item xs={12} sm={4}>
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

        <Grid item xs={12} sm={4}>
          <Controller
            name="phone1"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Phone 1"
                disabled={isSubmitting}
                error={!!errors.phone1}
                helperText={errors.phone1?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={4}>
          <Controller
            name="phone2"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Phone 2"
                disabled={isSubmitting}
                error={!!errors.phone2}
                helperText={errors.phone2?.message}
              />
            )}
          />
        </Grid>

        {!isCreate && (
          <Grid item xs={12} sm={4}>
            <FormControl fullWidth disabled={isSubmitting}>
              <InputLabel>Status</InputLabel>
              <Controller
                name="is_active"
                control={updateForm.control}
                render={({ field }) => (
                  <Select
                    {...field}
                    label="Status"
                    value={field.value === undefined ? '' : field.value ? 'active' : 'inactive'}
                    onChange={(e) => field.onChange(e.target.value === 'active')}
                  >
                    <MenuItem value="active">Active</MenuItem>
                    <MenuItem value="inactive">Inactive</MenuItem>
                  </Select>
                )}
              />
            </FormControl>
          </Grid>
        )}

        <Grid item xs={12}>
          <Divider sx={{ my: 1 }} />
          <Typography variant="subtitle2" color="textSecondary" gutterBottom>
            Additional Information
          </Typography>
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="address_line1"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Address Line 1"
                disabled={isSubmitting}
                error={!!errors.address_line1}
                helperText={errors.address_line1?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="address_line2"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Address Line 2"
                disabled={isSubmitting}
                error={!!errors.address_line2}
                helperText={errors.address_line2?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={4}>
          <Controller
            name="city"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="City"
                disabled={isSubmitting}
                error={!!errors.city}
                helperText={errors.city?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={4}>
          <Controller
            name="state"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="State"
                disabled={isSubmitting}
                error={!!errors.state}
                helperText={errors.state?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={4}>
          <Controller
            name="pin_code"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Pin Code"
                disabled={isSubmitting}
                error={!!errors.pin_code}
                helperText={errors.pin_code?.message}
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
