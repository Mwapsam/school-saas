/**
 * Student form component for create and edit.
 *
 * Reused for both:
 * - Create new student
 * - Edit existing student
 */

'use client';

import { useState } from 'react';
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
import { Student, CreateStudentInput, UpdateStudentInput } from './hooks';

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
  const [formData, setFormData] = useState<CreateStudentInput | UpdateStudentInput>(
    student
      ? {
          full_name: student.full_name,
          email: student.email || '',
          phone: student.phone || '',
          batch_id: student.batch_id,
        }
      : {
          admission_number: '',
          full_name: '',
          date_of_birth: '',
          gender: 'M',
          email: '',
          phone: '',
        }
  );

  const [submitting, setSubmitting] = useState(false);

  const isCreate = !student;

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
        {/* Create-only fields */}
        {isCreate && (
          <>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Admission Number"
                value={(formData as CreateStudentInput).admission_number || ''}
                onChange={(e) => handleChange('admission_number', e.target.value)}
                required
                disabled={submitting}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Date of Birth"
                type="date"
                value={(formData as CreateStudentInput).date_of_birth || ''}
                onChange={(e) => handleChange('date_of_birth', e.target.value)}
                required
                disabled={submitting}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth disabled={submitting}>
                <InputLabel>Gender</InputLabel>
                <Select
                  value={(formData as CreateStudentInput).gender || 'M'}
                  onChange={(e) => handleChange('gender', e.target.value)}
                  label="Gender"
                >
                  <MenuItem value="M">Male</MenuItem>
                  <MenuItem value="F">Female</MenuItem>
                  <MenuItem value="O">Other</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </>
        )}

        {/* Common fields */}
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Full Name"
            value={formData.full_name || ''}
            onChange={(e) => handleChange('full_name', e.target.value)}
            required
            disabled={submitting}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Email"
            type="email"
            value={formData.email || ''}
            onChange={(e) => handleChange('email', e.target.value)}
            disabled={submitting}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Phone"
            value={formData.phone || ''}
            onChange={(e) => handleChange('phone', e.target.value)}
            disabled={submitting}
          />
        </Grid>

        {/* Batch selection */}
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Batch ID"
            value={formData.batch_id || ''}
            onChange={(e) => handleChange('batch_id', e.target.value)}
            disabled={submitting}
            helperText="Leave empty for no batch assignment"
          />
        </Grid>

        {/* Buttons */}
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
