/**
 * Login page — POST credentials to Django via /api/auth/login/ route handler.
 */

export const dynamic = 'force-dynamic';

import { Suspense } from 'react';
import { Container, Box, CircularProgress } from '@mui/material';
import { LoginForm } from './LoginForm';

export default function LoginPage() {
  return (
    <Container maxWidth="sm">
      <Box sx={{ py: 8 }}>
        <Suspense
          fallback={
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
              <CircularProgress />
            </Box>
          }
        >
          <LoginForm />
        </Suspense>
      </Box>
    </Container>
  );
}
