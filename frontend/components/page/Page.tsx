'use client';

import { Box, Container, type ContainerProps } from '@mui/material';
import { spacing } from '@/design-system/tokens';

interface PageProps extends Omit<ContainerProps, 'maxWidth'> {
  children: React.ReactNode;
}

/**
 * Page wrapper component.
 *
 * Provides consistent padding and layout for page content.
 * All pages should wrap their content with this component.
 *
 * Usage:
 *   <Page>
 *     <PageHeader title="Students" />
 *     <PageContent>
 *       page content here
 *     </PageContent>
 *   </Page>
 */
export function Page({ children, ...props }: PageProps) {
  return (
    <Container maxWidth="lg" {...props}>
      <Box
        sx={{
          px: { xs: 2, sm: 3, md: spacing.pageHorizontal },
          py: { xs: 2, sm: 3, md: 4 },
        }}
      >
        {children}
      </Box>
    </Container>
  );
}
