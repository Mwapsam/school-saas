'use client';

import { forwardRef } from 'react';
import { Button, CircularProgress, type ButtonProps } from '@mui/material';

export interface LoadingButtonProps extends ButtonProps {
  loading?: boolean;
}

/**
 * Button with integrated loading state.
 * When `loading=true`, shows a spinner and disables interaction.
 * The label stays in the DOM (visibility:hidden) to keep button width stable.
 */
export const LoadingButton = forwardRef<HTMLButtonElement, LoadingButtonProps>(
  ({ loading = false, disabled, children, ...props }, ref) => {
    const isDisabled = disabled || loading;

    return (
      <Button
        ref={ref}
        disabled={isDisabled}
        {...props}
        sx={{
          position: 'relative',
          ...props.sx,
        }}
      >
        {loading ? (
          <>
            <CircularProgress
              size={20}
              color="inherit"
              sx={{
                position: 'absolute',
                left: '50%',
                transform: 'translateX(-50%)',
              }}
            />
            <span style={{ visibility: 'hidden' }}>{children}</span>
          </>
        ) : (
          children
        )}
      </Button>
    );
  },
);

LoadingButton.displayName = 'LoadingButton';
