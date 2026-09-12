/**
 * Zod validation schemas for Employee create/update forms.
 */

import { z } from 'zod';

export const createEmployeeSchema = z.object({
  employee_number: z.string().min(1, 'Employee number is required'),
  first_name: z.string().min(1, 'First name is required'),
  last_name: z.string().min(1, 'Last name is required'),
  middle_name: z.string().optional().or(z.literal('')),
  email: z.string().email('Enter a valid email').optional().or(z.literal('')),
  mobile_phone: z.string().optional().or(z.literal('')),
  employee_department: z.string().optional().or(z.literal('')),
  employee_position: z.string().optional().or(z.literal('')),
  joining_date: z.string().min(1, 'Joining date is required'),
});

export const updateEmployeeSchema = z.object({
  first_name: z.string().min(1, 'First name is required').optional(),
  last_name: z.string().min(1, 'Last name is required').optional(),
  middle_name: z.string().optional().or(z.literal('')),
  email: z.string().optional().or(z.literal('')),
  mobile_phone: z.string().optional().or(z.literal('')),
  employee_department: z.string().optional().or(z.literal('')),
  employee_position: z.string().optional().or(z.literal('')),
  status: z.boolean().optional(),
});

export type CreateEmployeeFormValues = z.infer<typeof createEmployeeSchema>;
export type UpdateEmployeeFormValues = z.infer<typeof updateEmployeeSchema>;
