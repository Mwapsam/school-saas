/**
 * Zod validation schemas for Employee create/update forms.
 */

import { z } from 'zod';

export const createEmployeeSchema = z.object({
  employee_id: z.string().min(1, 'Employee ID is required'),
  full_name: z.string().min(1, 'Full name is required'),
  email: z.string().min(1, 'Email is required').email('Enter a valid email'),
  phone: z.string().optional().or(z.literal('')),
  department: z.string().optional().or(z.literal('')),
  position: z.string().optional().or(z.literal('')),
  hire_date: z.string().min(1, 'Hire date is required'),
});

export const updateEmployeeSchema = z.object({
  full_name: z.string().min(1, 'Full name is required').optional(),
  email: z.string().email('Enter a valid email').optional().or(z.literal('')),
  phone: z.string().optional().or(z.literal('')),
  department: z.string().optional().or(z.literal('')),
  position: z.string().optional().or(z.literal('')),
  is_active: z.boolean().optional(),
});

export type CreateEmployeeFormValues = z.infer<typeof createEmployeeSchema>;
export type UpdateEmployeeFormValues = z.infer<typeof updateEmployeeSchema>;
