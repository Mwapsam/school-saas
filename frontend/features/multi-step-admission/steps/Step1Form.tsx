'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Grid, Button, CircularProgress, Alert, FormControlLabel, Checkbox, Paper, Typography, Divider } from '@mui/material';
import DOMPurify from 'isomorphic-dompurify';
import { step1Schema, type Step1FormData } from '../schemas';
import { useGetAdmissionTerms } from '../hooks';

interface Step1FormProps {
  initialData?: any;
  onSubmit: (data: Step1FormData) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  onNext?: () => void;
}

const DEFAULT_TERMS = `
<h6 style="font-weight: bold; margin-bottom: 1rem;">CONDITIONS FOR ADMISSION</h6>

<p><strong><u>1. Admission</u></strong></p>
<p>Upon receipt of a completed registration form accompanied by the registration fee, the child's name will be entered on the waiting list. Where appropriate, a placement test will be given to determine the most suitable level for the child, after which a place will be offered. The place will be secured by payment of one term's fees, which <strong>must be paid in full before admission to class. Failure to pay fees on time may lead to loss of the place.</strong></p>

<p><strong><u>2. Fees</u></strong></p>
<p>Fees are payable termly before the term starts, with a penalty being charged for payments made after the given deadline. Refunds for whatever reason, e.g., illness or holiday, will not be possible.</p>

<p><strong><u>3. Withdrawal</u></strong></p>
<p>In the event of you wishing to withdraw your child at the end of a term, you must give at least 30 days' notice in writing to the school. Failure to do so will result in payment of fees for the following term regardless of whether your child attends or not. If you withdraw your child during the term, you will be liable for the fees for the remainder of that term. The school reserves the right to discontinue any child who persistently behaves in a manner considered harmful to the general learning environment. This includes the persistent and wilful damage to school property.</p>

<p><strong><u>4. Calendar and Timetable</u></strong></p>
<p>Exact term dates will be announced before the end of the preceding term. Classes will normally run from Monday to Friday starting at 7:45 and ending at 12:30 (preschool), and primary classes end at 13:00. Children should be delivered at the school before 7:30 hours, and it is expected that all children should be collected by 13:30 hours at the latest unless they are attending afternoon activities. Persistent late collection of children will be charged to cover the cost of supervision.</p>

<p><strong><u>5. Illness and Accidents</u></strong></p>
<p>In case of emergencies, every effort will be made to contact parents/guardians. You are therefore requested to inform the school promptly of any change of address or telephone numbers at home or at work. In the event that you cannot be contacted, the school will automatically seek further medical advice if deemed necessary. If the child contracts or comes into contact with any infectious disease, parents must inform the school immediately. A doctor's confirmation of fitness may be required before readmission. Whilst every effort will be made to avoid accidents, and supervision will be provided as far as possible at all times, the school will not accept liability for any accidents that may occur on the school premises, including all car parking areas.</p>

<p><strong><u>6. Losses</u></strong></p>
<p>The school cannot take responsibility for loss or damage to any of the child's personal property or the property belonging to anyone within the school premises, including all car parking areas. However, every effort will be made to prevent any losses from occurring.</p>

<p><strong><u>7. Clothing and Equipment</u></strong></p>
<p>Children must wear school uniforms at all times unless otherwise instructed. Requirements for any special clothing will be announced when required. All clothes and items carried by the child should be clearly labelled.</p>
`;

export function Step1Form({ initialData, onSubmit, isLoading, error, onNext }: Step1FormProps) {
  const { data: termsData } = useGetAdmissionTerms();

  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
  } = useForm<Step1FormData>({
    resolver: zodResolver(step1Schema),
    defaultValues: {
      terms_agreement: initialData?.terms_agreement || false,
    },
  });

  const termsAgreed = watch('terms_agreement');

  const handleFormSubmit = async (data: Step1FormData) => {
    try {
      await onSubmit(data);
      onNext?.();
    } catch (err) {
      console.error('Failed to save step 1:', err);
    }
  };

  // Use dynamic terms if available, otherwise fallback to default
  const termsHTML = termsData && termsData.length > 0
    ? termsData.map(t => `<div style="margin-bottom: 2rem;"><h6 style="font-weight: bold; margin-bottom: 1rem;">${t.title}</h6><div>${t.terms_content}</div></div>`).join('')
    : DEFAULT_TERMS;

  return (
    <Box component="form" onSubmit={handleSubmit(handleFormSubmit)} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Grid container spacing={3}>
        {/* Terms & Conditions Display */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3, maxHeight: '400px', overflowY: 'auto', backgroundColor: '#f5f5f5' }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
              Terms and Conditions for Admission
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <Box
              sx={{
                '& h6': { fontWeight: 'bold', marginTop: '1rem', marginBottom: '0.5rem' },
                '& p': { marginBottom: '0.75rem', lineHeight: '1.6' },
                '& strong': { fontWeight: 600 },
                '& u': { textDecoration: 'underline' },
              }}
              dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(termsHTML) }}
            />
          </Paper>
        </Grid>

        {/* Agreement Checkbox */}
        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Checkbox
                {...register('terms_agreement')}
                disabled={isLoading}
                required
              />
            }
            label="I have read the terms and conditions and agree to abide by them. *"
          />
          {errors.terms_agreement && (
            <Alert severity="error" sx={{ mt: 1 }}>{errors.terms_agreement.message}</Alert>
          )}
        </Grid>

        {/* Submit Button */}
        <Grid item xs={12}>
          <Button
            type="submit"
            variant="contained"
            disabled={isLoading || !termsAgreed}
            startIcon={isLoading && <CircularProgress size={20} />}
          >
            {isLoading ? 'Saving...' : 'Continue to Step 2'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
