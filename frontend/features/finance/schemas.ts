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

/**
 * Zod schemas for Fee Category create/update forms.
 */
export const feeCategorySchema = z.object({
  name: z.string().min(1, 'Name is required'),
  description: z.string().optional().or(z.literal('')),
  is_active: z.boolean().optional(),
});

export type FeeCategoryFormValues = z.infer<typeof feeCategorySchema>;

/**
 * Zod schemas for Fee Discount create/update forms.
 */
export const feeDiscountSchema = z.object({
  fee_category: z.string().min(1, 'Fee category is required'),
  name: z.string().min(1, 'Name is required'),
  discount_type: z.enum(['batch', 'individual']),
  discount_value: z.number({ message: 'Discount value is required' }).positive('Discount value must be greater than 0'),
  is_active: z.boolean().optional(),
});

export type FeeDiscountFormValues = z.infer<typeof feeDiscountSchema>;
