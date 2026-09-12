/**
 * Zod schemas for Invoice create/update forms.
 */

import { z } from 'zod';

export const createInvoiceSchema = z.object({
  student_id: z.string().min(1, 'Student is required'),
  invoice_number: z.string().min(1, 'Invoice number is required'),
  amount: z.number({ message: 'Amount is required' }).positive('Amount must be greater than 0'),
  due_date: z.string().min(1, 'Due date is required'),
  notes: z.string().optional().or(z.literal('')),
});

export const updateInvoiceSchema = z.object({
  amount: z.number({ message: 'Amount is required' }).positive('Amount must be greater than 0').optional(),
  due_date: z.string().min(1, 'Due date is required').optional(),
  status: z.string().optional(),
  notes: z.string().optional().or(z.literal('')),
});

export type CreateInvoiceFormValues = z.infer<typeof createInvoiceSchema>;
export type UpdateInvoiceFormValues = z.infer<typeof updateInvoiceSchema>;
