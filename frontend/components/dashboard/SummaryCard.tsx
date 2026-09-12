'use client';

import Link from 'next/link';
import { Card, CardActionArea, CardContent, Box, Typography, Skeleton } from '@mui/material';
import type { SvgIconComponent } from '@mui/icons-material';

export interface SummaryCardProps {
  icon: SvgIconComponent;
  label: string;
  count: number | undefined;
  loading?: boolean;
  href: string;
}

/**
 * A single dashboard summary tile: icon, count, label, linking to the
 * relevant list page. Used in a responsive Grid on the dashboard home page.
 */
export function SummaryCard({ icon: Icon, label, count, loading, href }: SummaryCardProps) {
  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardActionArea component={Link} href={href} sx={{ height: '100%' }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 48,
                height: 48,
                borderRadius: 2,
                bgcolor: 'primary.light',
                color: 'primary.contrastText',
              }}
            >
              <Icon />
            </Box>
            <Box>
              {loading ? (
                <Skeleton width={48} height={36} />
              ) : (
                <Typography variant="h5" component="div" fontWeight={600}>
                  {count ?? '—'}
                </Typography>
              )}
              <Typography variant="body2" color="text.secondary">
                {label}
              </Typography>
            </Box>
          </Box>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}
