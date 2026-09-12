'use client';

import { forwardRef } from 'react';
import { Box, Button, Typography, FormHelperText, FormControl, FormLabel } from '@mui/material';
import { CloudUpload as UploadIcon } from '@mui/icons-material';

interface FileUploadFieldProps {
  label: string;
  accept?: string;
  error?: boolean;
  helperText?: string;
  disabled?: boolean;
  onChange: (file: File | null) => void;
  value?: File | string;
  required?: boolean;
}

export const FileUploadField = forwardRef<HTMLInputElement, FileUploadFieldProps>(
  (
    {
      label,
      accept = '*',
      error = false,
      helperText,
      disabled = false,
      onChange,
      value,
      required = false,
    },
    ref
  ) => {
    const fileName = value && typeof value === 'string' ? value : (value instanceof File ? value.name : null);

    return (
      <FormControl fullWidth error={error} disabled={disabled}>
        <FormLabel sx={{ mb: 1, fontWeight: 500, fontSize: '0.875rem', display: 'block' }}>
          {label}
          {required && <span style={{ color: 'error.main' }}> *</span>}
        </FormLabel>

        <Box
          sx={{
            position: 'relative',
            border: '2px dashed',
            borderColor: error ? 'error.main' : 'divider',
            borderRadius: 1,
            p: 2,
            textAlign: 'center',
            cursor: disabled ? 'not-allowed' : 'pointer',
            backgroundColor: disabled ? 'action.disabledBackground' : 'transparent',
            transition: 'all 200ms',
            '&:hover': disabled ? {} : {
              borderColor: 'primary.main',
              backgroundColor: 'action.hover',
            },
          }}
        >
          <input
            ref={ref}
            type="file"
            accept={accept}
            onChange={(e) => onChange(e.target.files?.[0] || null)}
            disabled={disabled}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              opacity: 0,
              cursor: disabled ? 'not-allowed' : 'pointer',
            }}
          />

          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
            <UploadIcon sx={{ fontSize: 32, color: error ? 'error.main' : 'text.secondary' }} />
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {fileName ? `Selected: ${fileName}` : 'Click or drag to upload'}
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                or drag and drop
              </Typography>
            </Box>
          </Box>
        </Box>

        {helperText && (
          <FormHelperText sx={{ mt: 1 }}>
            {helperText}
          </FormHelperText>
        )}
      </FormControl>
    );
  }
);

FileUploadField.displayName = 'FileUploadField';
