import { z } from 'zod';

export const step1Schema = z.object({
  academic_year: z.string().min(1, 'Academic year is required'),
  course_applied: z.string().min(1, 'Course is required'),
  terms_agreement: z.boolean().refine((val) => val === true, {
    message: 'You must agree to the terms and conditions',
  }),
  preferred_start_date: z.string().optional().nullable(),
});

export const step2Schema = z.object({
  first_name: z.string().min(1, 'First name is required').max(100),
  middle_name: z.string().optional().nullable(),
  last_name: z.string().min(1, 'Last name is required').max(100),
  date_of_birth: z.string().min(1, 'Date of birth is required'),
  gender: z.enum(['male', 'female', 'other'], { message: 'Gender is required' }),
  nationality: z.string().min(1, 'Nationality is required'),
  student_photo: z.any().optional().nullable(),
  student_category: z.string().optional().nullable(),
  religion: z.string().optional().nullable(),
  birth_place: z.string().optional().nullable(),
  mother_tongue: z.string().optional().nullable(),
  preferred_name: z.string().optional().nullable(),
  home_language: z.string().optional().nullable(),
  authorized_pickup_persons: z.string().optional().nullable(),
});

export const step3Schema = z.object({
  address: z.string().optional().nullable(),
  address_line1: z.string().min(1, 'Address is required'),
  address_line2: z.string().optional().nullable(),
  city: z.string().min(1, 'City is required'),
  country: z.string().min(1, 'Country is required'),
  phone: z.string().optional().nullable(),
  mobile: z.string().optional().nullable(),
  email: z.string().email('Invalid email address').optional().nullable(),
});

export const step4Schema = z.object({
  guardian1_first_name: z.string().min(1, 'Guardian first name is required'),
  guardian1_last_name: z.string().min(1, 'Guardian last name is required'),
  guardian1_relation: z.string().min(1, 'Guardian relation is required'),
  guardian1_occupation: z.string().optional().nullable(),
  guardian1_office_address_line1: z.string().optional().nullable(),
  guardian1_office_city: z.string().optional().nullable(),
  guardian1_office_phone1: z.string().optional().nullable(),
  guardian1_mobile: z.string().min(1, 'Guardian mobile is required'),
  guardian1_email: z.string().email('Invalid email').optional().nullable(),
  guardian1_house_plot_no: z.string().optional().nullable(),
  guardian1_road_name: z.string().optional().nullable(),
  guardian1_area_location: z.string().optional().nullable(),
  guardian1_flat_block_name: z.string().optional().nullable(),

  guardian2_first_name: z.string().optional().nullable(),
  guardian2_last_name: z.string().optional().nullable(),
  guardian2_relation: z.string().optional().nullable(),
  guardian2_occupation: z.string().optional().nullable(),
  guardian2_office_address_line1: z.string().optional().nullable(),
  guardian2_office_city: z.string().optional().nullable(),
  guardian2_office_phone1: z.string().optional().nullable(),
  guardian2_mobile: z.string().optional().nullable(),
  guardian2_email: z.string().email('Invalid email').optional().nullable(),
  guardian2_house_plot_no: z.string().optional().nullable(),
  guardian2_road_name: z.string().optional().nullable(),
  guardian2_area_location: z.string().optional().nullable(),
  guardian2_flat_block_name: z.string().optional().nullable(),

  emergency_contact_name: z.string().optional().nullable(),
  emergency_contact_relation: z.string().optional().nullable(),
  emergency_contact_mobile: z.string().optional().nullable(),
  emergency_contact_address: z.string().optional().nullable(),
});

export const step5Schema = z.object({
  previous_school_name: z.string().optional().nullable(),
  previous_school_address: z.string().optional().nullable(),
  previous_school_phone: z.string().optional().nullable(),
  previous_school_email: z.string().email('Invalid email').optional().nullable(),
  expected_start_date: z.string().optional().nullable(),
  has_medical_problems: z.boolean().optional().nullable(),
  recent_hospitalization: z.boolean().optional().nullable(),
  has_allergies: z.boolean().optional().nullable(),
  medical_details: z.string().optional().nullable(),
  religious_observances: z.string().optional().nullable(),
  background_information: z.string().optional().nullable(),
  declaration_agreement: z.boolean().refine((val) => val === true, {
    message: 'You must agree to the declaration',
  }),
  declaration_signature_name: z.string().optional().nullable(),
  fee_acknowledgment: z.boolean().refine((val) => val === true, {
    message: 'You must acknowledge the admission fee requirement',
  }),
});

export type Step1FormData = z.infer<typeof step1Schema>;
export type Step2FormData = z.infer<typeof step2Schema>;
export type Step3FormData = z.infer<typeof step3Schema>;
export type Step4FormData = z.infer<typeof step4Schema>;
export type Step5FormData = z.infer<typeof step5Schema>;
