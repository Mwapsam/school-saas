/**
 * Zod schemas for Student create/update forms.
 */

import { z } from 'zod';

export const createStudentSchema = z.object({
  admission_number: z.string().min(1, 'Admission number is required'),
  full_name: z.string().min(1, 'Full name is required'),
  date_of_birth: z.string().min(1, 'Date of birth is required'),
  gender: z.enum(['M', 'F', 'O']),
  email: z.string().email('Invalid email').optional().or(z.literal('')),
  phone: z.string().optional().or(z.literal('')),
  batch_id: z.string().optional().or(z.literal('')),
});

export const updateStudentSchema = z.object({
  full_name: z.string().min(1, 'Full name is required').optional(),
  email: z.string().email('Invalid email').optional().or(z.literal('')),
  phone: z.string().optional().or(z.literal('')),
  batch_id: z.string().optional().or(z.literal('')),
  is_active: z.boolean().optional(),
});

export type CreateStudentFormValues = z.infer<typeof createStudentSchema>;
export type UpdateStudentFormValues = z.infer<typeof updateStudentSchema>;
