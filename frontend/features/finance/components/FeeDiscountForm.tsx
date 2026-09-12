/**
 * Fee discount form component for create and edit.
 *
 * Reused for both:
 * - Create new fee discount
 * - Edit existing fee discount
 */

'use client';

import {
  Box,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  FormControlLabel,
  Switch,
  CircularProgress,
  Alert,
  Grid,
} from '@mui/material';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { FeeDiscount, CreateFeeDiscountInput, UpdateFeeDiscountInput, useFeeCategoryList } from '../hooks';
import { feeDiscountSchema, FeeDiscountFormValues } from '../schemas';

export interface FeeDiscountFormProps {
  feeDiscount?: FeeDiscount;
  error?: string | null;
  onSubmit: (data: CreateFeeDiscountInput | UpdateFeeDiscountInput) => Promise<void>;
  onCancel?: () => void;
}

export function FeeDiscountForm({
  feeDiscount,
  error,
  onSubmit,
  onCancel,
}: FeeDiscountFormProps) {
  const isCreate = !feeDiscount;

  const { data: feeCategoriesData } = useFeeCategoryList({ page_size: 100 });

  const form = useForm<FeeDiscountFormValues>({
    resolver: zodResolver(feeDiscountSchema),
    defaultValues: {
      fee_category: feeDiscount?.fee_category || '',
      name: feeDiscount?.name || '',
      discount_type: feeDiscount?.discount_type || 'batch',
      discount_mode: feeDiscount?.discount_mode || 'percentage',
      discount_value: feeDiscount?.discount_value ?? undefined,
      is_active: feeDiscount?.is_active ?? true,
    },
  });

  const { control, formState } = form;
  const { errors, isSubmitting } = formState;

  const submitHandler = form.handleSubmit(async (data) => {
    await onSubmit(data as CreateFeeDiscountInput | UpdateFeeDiscountInput);
  });

  return (
    <Box component="form" onSubmit={submitHandler} sx={{ maxWidth: 600 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        <Grid item xs={12}>
          <FormControl fullWidth disabled={isSubmitting} error={!!errors.fee_category}>
            <InputLabel>Fee Category</InputLabel>
            <Controller
              name="fee_category"
              control={control}
              render={({ field }) => (
                <Select {...field} label="Fee Category">
                  {(feeCategoriesData?.results || []).map((category) => (
                    <MenuItem key={category.id} value={category.id}>
                      {category.name}
                    </MenuItem>
                  ))}
                </Select>
              )}
            />
          </FormControl>
        </Grid>

        <Grid item xs={12}>
          <Controller
            name="name"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Name"
                required
                disabled={isSubmitting}
                error={!!errors.name}
                helperText={errors.name?.message}
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <FormControl fullWidth disabled={isSubmitting}>
            <InputLabel>Discount Type</InputLabel>
            <Controller
              name="discount_type"
              control={control}
              render={({ field }) => (
                <Select {...field} label="Discount Type">
                  <MenuItem value="batch">Batch Discount</MenuItem>
                  <MenuItem value="individual">Individual Discount</MenuItem>
                </Select>
              )}
            />
          </FormControl>
        </Grid>

        <Grid item xs={12} sm={6}>
          <FormControl fullWidth disabled={isSubmitting}>
            <InputLabel>Discount Mode</InputLabel>
            <Controller
              name="discount_mode"
              control={control}
              render={({ field }) => (
                <Select {...field} label="Discount Mode">
                  <MenuItem value="percentage">Percentage</MenuItem>
                  <MenuItem value="amount">Fixed Amount</MenuItem>
                </Select>
              )}
            />
          </FormControl>
        </Grid>

        <Grid item xs={12} sm={6}>
          <Controller
            name="discount_value"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                fullWidth
                label="Discount Value"
                type="number"
                required
                disabled={isSubmitting}
                error={!!errors.discount_value}
                helperText={errors.discount_value?.message}
                onChange={(e) => field.onChange(e.target.value === '' ? undefined : Number(e.target.value))}
              />
            )}
          />
        </Grid>

        <Grid item xs={12}>
          <Controller
            name="is_active"
            control={control}
            render={({ field }) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={!!field.value}
                    onChange={(e) => field.onChange(e.target.checked)}
                    disabled={isSubmitting}
                  />
                }
                label="Active"
              />
            )}
          />
        </Grid>

        <Grid item xs={12} sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
          {onCancel && (
            <Button onClick={onCancel} disabled={isSubmitting}>
              Cancel
            </Button>
          )}
          <Button
            type="submit"
            variant="contained"
            disabled={isSubmitting}
            sx={{ minWidth: 120 }}
          >
            {isSubmitting ? <CircularProgress size={24} /> : isCreate ? 'Create' : 'Save'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
