/**
 * Zod schemas for Invoice create/update forms.
 */

import { z } from 'zod';

// Invoices have no create/update form — FamilyInvoice is entirely
// system-generated (see features/finance/hooks.ts Invoice doc comment).

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
