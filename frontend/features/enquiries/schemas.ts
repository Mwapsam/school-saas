import { z } from 'zod';

export const enquiryFormSchema = z.object({
  first_name: z.string().min(1, 'First name is required').max(100),
  last_name: z.string().min(1, 'Last name is required').max(100),
  date_of_birth: z.string().optional().nullable(),
  email: z.string().email('Invalid email').optional().nullable(),
  phone: z.string().optional().nullable(),
  address_line1: z.string().optional().nullable(),
  address_line2: z.string().optional().nullable(),
  city: z.string().optional().nullable(),
  state: z.string().optional().nullable(),
  postal_code: z.string().optional().nullable(),
  guardian_first_name: z.string().optional().nullable(),
  guardian_last_name: z.string().optional().nullable(),
  guardian_relation: z.string().optional().nullable(),
  guardian_email: z.string().email('Invalid email').optional().nullable(),
  guardian_phone: z.string().optional().nullable(),
  guardian_address_line1: z.string().optional().nullable(),
  guardian_address_line2: z.string().optional().nullable(),
  guardian_occupation: z.string().optional().nullable(),
  guardian_income: z.string().optional().nullable(),
  guardian_education: z.string().optional().nullable(),
  enquired_date: z.string().optional(),
  course: z.string().optional().nullable(),
  academic_year: z.string().optional().nullable(),
  counselor: z.string().optional().nullable(),
  source_of_info: z.string().optional().nullable(),
  remarks: z.string().optional().nullable(),
});

export const enquiryUpdateSchema = enquiryFormSchema.extend({
  stage: z.string().optional().nullable(),
  is_processed: z.boolean().optional(),
  is_rejected: z.boolean().optional(),
  is_viewed: z.boolean().optional(),
  is_email_enabled: z.boolean().optional(),
});

export type EnquiryFormData = z.infer<typeof enquiryFormSchema>;
export type EnquiryUpdateData = z.infer<typeof enquiryUpdateSchema>;
