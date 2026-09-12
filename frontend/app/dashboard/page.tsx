/**
 * Dashboard home page — entry point after login.
 *
 * Renders a summary grid of counts for each enabled module, sourced from
 * existing list endpoints' pagination `count` field (page_size: 1 so we
 * only pay for the count, not the full page of results).
 *
 * Bootstrap is guaranteed loaded by DashboardShell before this renders, so
 * no loading/error branches are needed here.
 */

'use client';

export const dynamic = 'force-dynamic';

import { Container, Box, Typography, Grid } from '@mui/material';
import SchoolIcon from '@mui/icons-material/School';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import BadgeIcon from '@mui/icons-material/Badge';
import AssignmentIndIcon from '@mui/icons-material/AssignmentInd';
import HotelIcon from '@mui/icons-material/Hotel';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import MenuBookIcon from '@mui/icons-material/MenuBook';

import { useTenantStore } from '@/lib/tenant/store';
import { SummaryCard } from '@/components/dashboard/SummaryCard';
import { useStudentList } from '@/features/students/hooks';
import { useInvoiceList } from '@/features/finance/hooks';
import { useEmployeeList } from '@/features/hr/hooks';
import { useAdmissionApplicationList } from '@/features/admissions/hooks';
import { useHostelRoomList } from '@/features/hostel/hooks';
import { useTransportRouteList } from '@/features/transport/hooks';
import { useLibraryBookList } from '@/features/library/hooks';

export default function DashboardPage() {
  const { bootstrap, isModuleEnabled } = useTenantStore();

  const studentsEnabled = isModuleEnabled('academics');
  const financeEnabled = isModuleEnabled('finance');
  const hrEnabled = isModuleEnabled('hr');
  const admissionsEnabled = isModuleEnabled('admissions');
  const hostelEnabled = isModuleEnabled('hostel');
  const transportEnabled = isModuleEnabled('transport');
  const libraryEnabled = isModuleEnabled('library');

  const students = useStudentList({ page_size: 1 }, { enabled: studentsEnabled });
  const invoices = useInvoiceList({ page_size: 1 }, { enabled: financeEnabled });
  const employees = useEmployeeList({ page_size: 1 }, { enabled: hrEnabled });
  const admissions = useAdmissionApplicationList({ page_size: 1 }, { enabled: admissionsEnabled });
  const hostelRooms = useHostelRoomList({ page_size: 1 }, { enabled: hostelEnabled });
  const routes = useTransportRouteList({ page_size: 1 }, { enabled: transportEnabled });
  const books = useLibraryBookList({ page_size: 1 }, { enabled: libraryEnabled });

  const cards = [
    {
      enabled: studentsEnabled,
      icon: SchoolIcon,
      label: 'Students',
      count: students.data?.count,
      loading: students.isLoading,
      href: '/dashboard/students',
    },
    {
      enabled: financeEnabled,
      icon: ReceiptLongIcon,
      label: 'Invoices',
      count: invoices.data?.count,
      loading: invoices.isLoading,
      href: '/dashboard/invoices',
    },
    {
      enabled: hrEnabled,
      icon: BadgeIcon,
      label: 'Employees',
      count: employees.data?.count,
      loading: employees.isLoading,
      href: '/dashboard/employees',
    },
    {
      enabled: admissionsEnabled,
      icon: AssignmentIndIcon,
      label: 'Admissions',
      count: admissions.data?.count,
      loading: admissions.isLoading,
      href: '/dashboard/admissions',
    },
    {
      enabled: hostelEnabled,
      icon: HotelIcon,
      label: 'Hostel Rooms',
      count: hostelRooms.data?.count,
      loading: hostelRooms.isLoading,
      href: '/dashboard/hostel-rooms',
    },
    {
      enabled: transportEnabled,
      icon: DirectionsBusIcon,
      label: 'Routes',
      count: routes.data?.count,
      loading: routes.isLoading,
      href: '/dashboard/routes',
    },
    {
      enabled: libraryEnabled,
      icon: MenuBookIcon,
      label: 'Books',
      count: books.data?.count,
      loading: books.isLoading,
      href: '/dashboard/books',
    },
  ].filter((c) => c.enabled);

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Welcome, {bootstrap?.user.full_name}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          {bootstrap?.tenant.name}
        </Typography>

        {cards.length === 0 ? (
          <Typography color="text.secondary">No modules enabled for this account.</Typography>
        ) : (
          <Grid container spacing={2}>
            {cards.map((card) => (
              <Grid item xs={12} sm={6} md={4} lg={3} key={card.label}>
                <SummaryCard
                  icon={card.icon}
                  label={card.label}
                  count={card.count}
                  loading={card.loading}
                  href={card.href}
                />
              </Grid>
            ))}
          </Grid>
        )}
      </Box>
    </Container>
  );
}
