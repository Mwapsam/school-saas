/**
 * Zod schemas for Student create/update forms.
 *
 * Mirrors StudentSerializer's writable fields (core/serializers/student_serializers.py).
 * Required on create: admission_no, first_name, last_name, date_of_birth,
 * gender, admission_date (admission_date has no null/blank/default on the
 * model, so it is treated as required here too).
 */

import { z } from 'zod';

export const createStudentSchema = z.object({
  admission_no: z.string().min(1, 'Admission number is required'),
  first_name: z.string().min(1, 'First name is required'),
  middle_name: z.string().optional().or(z.literal('')),
  last_name: z.string().min(1, 'Last name is required'),
  date_of_birth: z.string().min(1, 'Date of birth is required'),
  gender: z.enum(['male', 'female', 'other']),
  admission_date: z.string().min(1, 'Admission date is required'),
  blood_group: z.string().optional().or(z.literal('')),
  email: z.string().email('Invalid email').optional().or(z.literal('')),
  phone1: z.string().optional().or(z.literal('')),
  phone2: z.string().optional().or(z.literal('')),
  address_line1: z.string().optional().or(z.literal('')),
  address_line2: z.string().optional().or(z.literal('')),
  city: z.string().optional().or(z.literal('')),
  state: z.string().optional().or(z.literal('')),
  pin_code: z.string().optional().or(z.literal('')),
  is_active: z.boolean().optional(),
});

export const updateStudentSchema = z.object({
  admission_no: z.string().min(1, 'Admission number is required').optional(),
  first_name: z.string().min(1, 'First name is required').optional(),
  middle_name: z.string().optional().or(z.literal('')),
  last_name: z.string().min(1, 'Last name is required').optional(),
  date_of_birth: z.string().min(1, 'Date of birth is required').optional(),
  gender: z.enum(['male', 'female', 'other']).optional(),
  admission_date: z.string().min(1, 'Admission date is required').optional(),
  blood_group: z.string().optional().or(z.literal('')),
  email: z.string().email('Invalid email').optional().or(z.literal('')),
  phone1: z.string().optional().or(z.literal('')),
  phone2: z.string().optional().or(z.literal('')),
  address_line1: z.string().optional().or(z.literal('')),
  address_line2: z.string().optional().or(z.literal('')),
  city: z.string().optional().or(z.literal('')),
  state: z.string().optional().or(z.literal('')),
  pin_code: z.string().optional().or(z.literal('')),
  is_active: z.boolean().optional(),
});

export type CreateStudentFormValues = z.infer<typeof createStudentSchema>;
export type UpdateStudentFormValues = z.infer<typeof updateStudentSchema>;
