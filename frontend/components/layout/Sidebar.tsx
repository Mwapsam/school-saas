/**
 * Sidebar navigation — dynamically shows modules based on bootstrap data.
 *
 * Only renders sections for enabled modules.
 * Only renders links for which user has capability.
 */

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Box, List, ListItem, ListItemButton, ListItemText, Typography, Divider } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';

export interface NavSection {
  label: string;
  href: string;
  capability: string;
}

export interface NavModule {
  key: string;
  label: string;
  sections: NavSection[];
}

export const NAV_MODULES: NavModule[] = [
    {
      key: 'academics',
      label: 'Academics',
      sections: [
        { label: 'Students', href: '/dashboard/students', capability: 'students.view' },
        { label: 'Batches', href: '/dashboard/batches', capability: 'academics.batches.view' },
        { label: 'Courses', href: '/dashboard/courses', capability: 'academics.courses.view' },
      ],
    },
    {
      key: 'finance',
      label: 'Finance',
      sections: [
        { label: 'Invoices', href: '/dashboard/invoices', capability: 'finance.invoices.view' },
        { label: 'Fees', href: '/dashboard/invoices/fees', capability: 'finance.fees.view' },
        { label: 'Fee Categories', href: '/dashboard/invoices/fee-categories', capability: 'finance.fees.view' },
        { label: 'Fee Discounts', href: '/dashboard/invoices/fee-discounts', capability: 'finance.discounts.view' },
        { label: 'Transactions', href: '/dashboard/invoices/transactions', capability: 'finance.transactions.view' },
        { label: 'Day Book', href: '/dashboard/invoices/day-book', capability: 'finance.transactions.view' },
        { label: 'Student Ledger', href: '/dashboard/invoices/student-ledger', capability: 'finance.transactions.view' },
      ],
    },
    {
      key: 'hr',
      label: 'HR',
      sections: [
        { label: 'Employees', href: '/dashboard/employees', capability: 'hr.employees.view' },
        { label: 'Leave', href: '/dashboard/employees/leave', capability: 'hr.leave.view' },
        { label: 'Attendance', href: '/dashboard/employees/attendance', capability: 'hr.attendance.view' },
      ],
    },
    {
      key: 'admissions',
      label: 'Admissions',
      sections: [
        { label: 'New Application', href: '/dashboard/admissions/multi-step', capability: 'admissions.application.manage' },
        { label: 'Applicants', href: '/dashboard/admissions/applicants', capability: 'admissions.application.manage' },
        { label: 'Applications', href: '/dashboard/admissions', capability: 'admissions.application.view' },
        { label: 'Inquiries', href: '/dashboard/inquiries', capability: 'admissions.enquiry.view' },
      ],
    },
    {
      key: 'hostel',
      label: 'Hostel',
      sections: [
        { label: 'Rooms', href: '/dashboard/hostel-rooms', capability: 'hostel.rooms.view' },
        { label: 'Assignments', href: '/dashboard/hostel-assignments', capability: 'hostel.rooms.view' },
      ],
    },
    {
      key: 'transport',
      label: 'Transport',
      sections: [
        { label: 'Routes', href: '/dashboard/routes', capability: 'transport.routes.view' },
        { label: 'Vehicles', href: '/dashboard/vehicles', capability: 'transport.routes.view' },
        { label: 'Staff', href: '/dashboard/transport-staff', capability: 'transport.staff.view' },
      ],
    },
    {
      key: 'library',
      label: 'Library',
      sections: [
        { label: 'Books', href: '/dashboard/books', capability: 'library.view' },
        { label: 'Borrowing', href: '/dashboard/borrowing', capability: 'library.view' },
      ],
    },
  ];

export function Sidebar({ onNavigate }: { onNavigate?: () => void } = {}) {
  const { bootstrap, can, isModuleEnabled } = useTenantStore();
  const pathname = usePathname();

  if (!bootstrap) {
    return null;
  }

  const enabledModules = NAV_MODULES.filter((m) => isModuleEnabled(m.key));

  if (enabledModules.length === 0) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="textSecondary">
          No modules enabled
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
      {enabledModules.map((module, idx) => (
        <Box key={module.key} sx={{ flex: '0 0 auto' }}>
          {/* Module section heading */}
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              px: 2,
              py: 1.5,
              fontWeight: 700,
              color: 'text.secondary',
              textTransform: 'uppercase',
              fontSize: '0.7rem',
              letterSpacing: 1,
            }}
          >
            {module.label}
          </Typography>

          {/* Navigation items */}
          <List sx={{ py: 0, px: 0 }}>
            {module.sections
              .filter((s) => can(s.capability))
              .map((section) => {
                const isActive =
                  pathname === section.href || pathname?.startsWith(`${section.href}/`);
                return (
                  <ListItem key={section.href} disablePadding>
                    <Link href={section.href} passHref legacyBehavior>
                      <ListItemButton
                        component="a"
                        selected={isActive}
                        onClick={onNavigate}
                        sx={{
                          pl: 2,
                          pr: 2,
                          py: 1,
                          mx: 1,
                          mb: 0.5,
                          borderRadius: 1,
                          color: 'text.primary',
                          transition: 'all 120ms ease-in-out',

                          '&:hover': {
                            backgroundColor: 'action.hover',
                            color: 'text.primary',
                          },

                          '&.Mui-selected': {
                            backgroundColor: 'primary.main',
                            color: 'primary.contrastText',
                            fontWeight: 600,

                            '&:hover': {
                              backgroundColor: 'primary.dark',
                            },
                          },
                        }}
                      >
                        <ListItemText
                          primary={section.label}
                          primaryTypographyProps={{
                            variant: 'body2',
                            sx: { fontWeight: isActive ? 600 : 500 },
                          }}
                        />
                      </ListItemButton>
                    </Link>
                  </ListItem>
                );
              })}
          </List>

          {/* Divider between modules */}
          {idx < enabledModules.length - 1 && <Divider sx={{ my: 1 }} />}
        </Box>
      ))}
    </Box>
  );
}
