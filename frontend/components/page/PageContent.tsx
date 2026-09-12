'use client';

import { Box, type BoxProps } from '@mui/material';
import { spacing } from '@/design-system/tokens';

interface PageContentProps extends Omit<BoxProps, 'children'> {
  children: React.ReactNode;
}

/**
 * Page content wrapper component.
 *
 * Wraps the main content area of a page, providing consistent spacing.
 * Use this to wrap tables, forms, grids, etc.
 *
 * Usage:
 *   <Page>
 *     <PageHeader title="Students" />
 *     <PageContent>
 *       <DataTable columns={columns} rows={students} />
 *     </PageContent>
 *   </Page>
 */
export function PageContent({ children, ...props }: PageContentProps) {
  return (
    <Box
      sx={{
        mt: spacing.section,
        ...props.sx,
      }}
      {...props}
    >
      {children}
    </Box>
  );
}
