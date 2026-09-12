/**
 * Zod validation schema for Admission Application create form.
 */

import { z } from 'zod';

export const createAdmissionApplicationSchema = z.object({
  first_name: z.string().min(1, 'First name is required'),
  middle_name: z.string().optional().or(z.literal('')),
  last_name: z.string().min(1, 'Last name is required'),
  date_of_birth: z.string().min(1, 'Date of birth is required'),
  gender: z.enum(['male', 'female', 'other'], { message: 'Gender is required' }),
  course_applied: z.string().min(1, 'Course is required'),
  guardian_name: z.string().min(1, 'Guardian name is required'),
  guardian_phone: z.string().min(1, 'Guardian phone is required'),
  guardian_email: z.string().email('Enter a valid email').optional().or(z.literal('')),
  address: z.string().min(1, 'Address is required'),
  remarks: z.string().optional().or(z.literal('')),
});

export type CreateAdmissionApplicationFormValues = z.infer<typeof createAdmissionApplicationSchema>;
