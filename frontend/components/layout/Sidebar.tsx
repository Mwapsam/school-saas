/**
 * Sidebar navigation — dynamically shows modules based on bootstrap data.
 *
 * Only renders sections for enabled modules.
 * Only renders links for which user has capability.
 */

'use client';

import Link from 'next/link';
import { Box, List, ListItem, ListItemButton, ListItemText, Typography, Divider } from '@mui/material';
import { useTenantStore } from '@/lib/tenant/store';

export function Sidebar() {
  const { bootstrap, can, isModuleEnabled } = useTenantStore();

  if (!bootstrap) {
    return null;
  }

  const modules = [
    {
      key: 'academics',
      label: 'Academics',
      sections: [
        { label: 'Students', href: '/dashboard/students', capability: 'students.view' },
        { label: 'Batches', href: '/dashboard/batches', capability: 'batches.view' },
        { label: 'Courses', href: '/dashboard/courses', capability: 'courses.view' },
      ],
    },
    {
      key: 'finance',
      label: 'Finance',
      sections: [
        { label: 'Invoices', href: '/dashboard/invoices', capability: 'finance.invoices.view' },
        { label: 'Fees', href: '/dashboard/fees', capability: 'finance.fees.view' },
        { label: 'Transactions', href: '/dashboard/transactions', capability: 'finance.transactions.view' },
      ],
    },
    {
      key: 'hr',
      label: 'HR',
      sections: [
        { label: 'Employees', href: '/dashboard/employees', capability: 'hr.employees.view' },
        { label: 'Leave', href: '/dashboard/leave-requests', capability: 'hr.leave.view' },
        { label: 'Attendance', href: '/dashboard/attendance', capability: 'hr.attendance.view' },
      ],
    },
    {
      key: 'admissions',
      label: 'Admissions',
      sections: [
        { label: 'Applications', href: '/dashboard/admissions', capability: 'admissions.view' },
        { label: 'Inquiries', href: '/dashboard/inquiries', capability: 'admissions.view' },
      ],
    },
    {
      key: 'hostel',
      label: 'Hostel',
      sections: [
        { label: 'Rooms', href: '/dashboard/hostel-rooms', capability: 'hostel.view' },
        { label: 'Assignments', href: '/dashboard/hostel-assignments', capability: 'hostel.view' },
      ],
    },
    {
      key: 'transport',
      label: 'Transport',
      sections: [
        { label: 'Routes', href: '/dashboard/routes', capability: 'transport.view' },
        { label: 'Vehicles', href: '/dashboard/vehicles', capability: 'transport.view' },
        { label: 'Staff', href: '/dashboard/transport-staff', capability: 'transport.view' },
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

  const enabledModules = modules.filter((m) => isModuleEnabled(m.key));

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
    <Box sx={{ width: '100%' }}>
      {enabledModules.map((module, idx) => (
        <Box key={module.key}>
          <Typography
            variant="subtitle2"
            sx={{
              px: 2,
              py: 1.5,
              fontWeight: 600,
              color: '#666',
              textTransform: 'uppercase',
              fontSize: '0.75rem',
              letterSpacing: 0.5,
            }}
          >
            {module.label}
          </Typography>
          <List sx={{ py: 0 }}>
            {module.sections
              .filter((s) => can(s.capability))
              .map((section) => (
                <ListItem key={section.href} disablePadding>
                  <Link href={section.href} passHref legacyBehavior>
                    <ListItemButton
                      component="a"
                      sx={{
                        pl: 4,
                        py: 1,
                        '&:hover': {
                          backgroundColor: '#f5f5f5',
                        },
                      }}
                    >
                      <ListItemText
                        primary={section.label}
                        primaryTypographyProps={{ variant: 'body2' }}
                      />
                    </ListItemButton>
                  </Link>
                </ListItem>
              ))}
          </List>
          {idx < enabledModules.length - 1 && <Divider sx={{ my: 1 }} />}
        </Box>
      ))}
    </Box>
  );
}
