/**
 * Zod validation schema for Admission Application create form.
 */

import { z } from 'zod';

export const createAdmissionApplicationSchema = z.object({
  student_name: z.string().min(1, 'Student name is required'),
  email: z.string().min(1, 'Email is required').email('Enter a valid email'),
  phone: z.string().optional().or(z.literal('')),
  notes: z.string().optional().or(z.literal('')),
});

export type CreateAdmissionApplicationFormValues = z.infer<typeof createAdmissionApplicationSchema>;
