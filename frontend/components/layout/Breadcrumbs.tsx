'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import MuiBreadcrumbs from '@mui/material/Breadcrumbs';
import Typography from '@mui/material/Typography';
import { NAV_MODULES } from './Sidebar';

const LABEL_BY_HREF: Record<string, string> = NAV_MODULES.flatMap((m) => m.sections).reduce(
  (acc, section) => {
    acc[section.href] = section.label;
    return acc;
  },
  {} as Record<string, string>
);

function humanize(segment: string): string {
  if (/^[0-9a-fA-F-]{8,}$/.test(segment)) return 'Detail';
  return segment
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function Breadcrumbs() {
  const pathname = usePathname() || '/dashboard';
  const segments = pathname.split('/').filter(Boolean); // e.g. ['dashboard', 'students', 'create']

  const crumbs = segments.map((segment, idx) => {
    const href = '/' + segments.slice(0, idx + 1).join('/');
    const label = LABEL_BY_HREF[href] || humanize(segment);
    return { href, label };
  });

  if (crumbs.length <= 1) return null;

  return (
    <MuiBreadcrumbs aria-label="breadcrumb" sx={{ mb: 2 }}>
      {crumbs.map((crumb, idx) => {
        const isLast = idx === crumbs.length - 1;
        if (isLast) {
          return (
            <Typography key={crumb.href} color="text.primary" variant="body2">
              {crumb.label}
            </Typography>
          );
        }
        return (
          <Link key={crumb.href} href={crumb.href} style={{ textDecoration: 'none' }}>
            <Typography color="text.secondary" variant="body2">
              {crumb.label}
            </Typography>
          </Link>
        );
      })}
    </MuiBreadcrumbs>
  );
}
