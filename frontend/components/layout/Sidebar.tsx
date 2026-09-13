/**
 * Sidebar navigation — dynamically shows modules based on bootstrap data.
 *
 * Supports collapsible (icons-only) mode with smooth transitions.
 * Field usage matches the real BootstrapData shape:
 * - bootstrap.tenant.{name, logo_url} for branding
 * - bootstrap.user.{full_name, username} for the footer
 */

'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import {
  Avatar,
  Box,
  Collapse,
  IconButton,
  InputAdornment,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  TextField,
  Typography,
  Stack,
  Tooltip,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import type { SvgIconComponent } from '@mui/icons-material';
import {
  School as AcademicsIcon,
  AttachMoney as FinanceIcon,
  People as HRIcon,
  PersonAdd as AdmissionsIcon,
  Hotel as HostelIcon,
  DirectionsBus as TransportIcon,
  MenuBook as LibraryIcon,
  Settings as SettingsIcon,
  AutoStories as CrestIcon,
  ExpandMore as ExpandMoreIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
} from '@mui/icons-material';
import { useTenantStore } from '@/lib/tenant/store';
import { colors, motion } from '@/design-system/tokens';

export interface NavSection {
  label: string;
  href: string;
  capability: string;
}

export interface NavModule {
  key: string;
  label: string;
  icon: SvgIconComponent;
  sections: NavSection[];
}

export const NAV_MODULES: NavModule[] = [
  {
    key: 'academics',
    label: 'Academics',
    icon: AcademicsIcon,
    sections: [
      { label: 'Students', href: '/dashboard/students', capability: 'students.view' },
      { label: 'Batches', href: '/dashboard/batches', capability: 'academics.batches.view' },
      { label: 'Courses', href: '/dashboard/courses', capability: 'academics.courses.view' },
    ],
  },
  {
    key: 'finance',
    label: 'Finance',
    icon: FinanceIcon,
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
    icon: HRIcon,
    sections: [
      { label: 'Employees', href: '/dashboard/employees', capability: 'hr.employees.view' },
      { label: 'Leave', href: '/dashboard/employees/leave', capability: 'hr.leave.view' },
      { label: 'Attendance', href: '/dashboard/employees/attendance', capability: 'hr.attendance.view' },
    ],
  },
  {
    key: 'admissions',
    label: 'Admissions',
    icon: AdmissionsIcon,
    sections: [
      { label: 'New Application', href: '/dashboard/admissions/multi-step', capability: 'admissions.application.manage' },
      { label: 'Applicants', href: '/dashboard/admissions/applicants', capability: 'admissions.application.manage' },
      { label: 'Applications', href: '/dashboard/admissions', capability: 'admissions.application.view' },
      { label: 'Management', href: '/dashboard/admissions/manage', capability: 'admissions.application.manage' },
      { label: 'Batch Assignment', href: '/dashboard/admissions/batch-assignment', capability: 'admissions.application.manage' },
      { label: 'Report', href: '/dashboard/admissions/report', capability: 'admissions.application.view' },
      { label: 'Status Check', href: '/dashboard/admissions/status-check', capability: 'admissions.application.view' },
      { label: 'Inquiries', href: '/dashboard/inquiries', capability: 'admissions.enquiry.view' },
    ],
  },
  {
    key: 'hostel',
    label: 'Hostel',
    icon: HostelIcon,
    sections: [
      { label: 'Rooms', href: '/dashboard/hostel-rooms', capability: 'hostel.rooms.view' },
      { label: 'Assignments', href: '/dashboard/hostel-assignments', capability: 'hostel.rooms.view' },
    ],
  },
  {
    key: 'transport',
    label: 'Transport',
    icon: TransportIcon,
    sections: [
      { label: 'Routes', href: '/dashboard/routes', capability: 'transport.routes.view' },
      { label: 'Vehicles', href: '/dashboard/vehicles', capability: 'transport.routes.view' },
      { label: 'Staff', href: '/dashboard/transport-staff', capability: 'transport.staff.view' },
    ],
  },
  {
    key: 'library',
    label: 'Library',
    icon: LibraryIcon,
    sections: [
      { label: 'Books', href: '/dashboard/books', capability: 'library.view' },
      { label: 'Borrowing', href: '/dashboard/borrowing', capability: 'library.view' },
    ],
  },
];

const EXPANDED_WIDTH = 280;
const COLLAPSED_WIDTH = 72;

function initials(name?: string | null) {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || name[0]!.toUpperCase();
}

function isActivePath(pathname: string | null, href: string) {
  return pathname === href || (pathname?.startsWith(`${href}/`) ?? false);
}

export function Sidebar({
  onNavigate,
  collapsed: controlledCollapsed,
  onCollapsedChange,
}: {
  onNavigate?: () => void;
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
} = {}) {
  const { bootstrap, can, isModuleEnabled } = useTenantStore();
  const pathname = usePathname();
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [internalCollapsed, setInternalCollapsed] = useState(false);

  const collapsed = controlledCollapsed ?? internalCollapsed;
  const setCollapsed = (value: boolean) => {
    if (onCollapsedChange) onCollapsedChange(value);
    else setInternalCollapsed(value);
  };

  const visibleModules = useMemo(() => {
    return NAV_MODULES.map((module) => ({
      ...module,
      sections: module.sections.filter((s) => can(s.capability)),
    })).filter((module) => isModuleEnabled(module.key) && module.sections.length > 0);
  }, [can, isModuleEnabled]);

  // Keep the module that owns the current route open
  useEffect(() => {
    if (collapsed) return;
    const activeModule = visibleModules.find((m) =>
      m.sections.some((s) => isActivePath(pathname, s.href)),
    );
    if (activeModule) {
      setExpanded((prev) =>
        prev.has(activeModule.key) ? prev : new Set(prev).add(activeModule.key),
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, visibleModules.length, collapsed]);

  const normalizedQuery = query.trim().toLowerCase();
  const isSearching = normalizedQuery.length > 0 && !collapsed;

  const displayModules = useMemo(() => {
    if (!isSearching) return visibleModules;
    return visibleModules
      .map((module) => ({
        ...module,
        sections: module.sections.filter((s) =>
          s.label.toLowerCase().includes(normalizedQuery),
        ),
      }))
      .filter((module) => module.sections.length > 0);
  }, [visibleModules, isSearching, normalizedQuery]);

  function toggleModule(key: string) {
    if (collapsed) return;
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  if (!bootstrap) {
    return null;
  }

  const schoolName = bootstrap.tenant.name;
  const logoUrl = bootstrap.tenant.logo_url;
  const userName = bootstrap.user.full_name || bootstrap.user.username;
  const userHandle = bootstrap.user.username;

  if (visibleModules.length === 0) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" sx={{ color: colors.text.secondary }}>
          No modules enabled
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      component="nav"
      aria-label="Main navigation"
      sx={{
        width: collapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH,
        minWidth: collapsed ? COLLAPSED_WIDTH : EXPANDED_WIDTH,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: colors.background.surface,
        borderRight: `1px solid ${colors.border.light}`,
        transition: `width ${motion.slow}ms ${motion.easing}, min-width ${motion.slow}ms ${motion.easing}`,
        overflow: 'hidden',
        '@media (prefers-reduced-motion: reduce)': {
          transition: 'none',
        },
      }}
    >
      {/* Brand + collapse toggle */}
      <Stack
        direction="row"
        alignItems="center"
        justifyContent={collapsed ? 'center' : 'space-between'}
        sx={{
          px: collapsed ? 1 : 2,
          py: 2,
          borderBottom: `1px solid ${colors.border.light}`,
          minHeight: 72,
          flexShrink: 0,
        }}
      >
        <Stack
          direction="row"
          alignItems="center"
          spacing={1.5}
          sx={{
            minWidth: 0,
            opacity: collapsed ? 0 : 1,
            width: collapsed ? 0 : 'auto',
            overflow: 'hidden',
            transition: `opacity ${motion.normal}ms ${motion.easing}, width ${motion.slow}ms ${motion.easing}`,
            '@media (prefers-reduced-motion: reduce)': { transition: 'none' },
          }}
        >
          <Box
            sx={{
              width: 40,
              height: 40,
              borderRadius: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              overflow: 'hidden',
              backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.12),
              color: 'primary.main',
            }}
          >
            {logoUrl ? (
              <Image
                src={logoUrl}
                alt={`${schoolName} logo`}
                width={40}
                height={40}
                style={{ objectFit: 'cover' }}
              />
            ) : (
              <CrestIcon sx={{ fontSize: 22 }} />
            )}
          </Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography
              variant="subtitle1"
              noWrap
              sx={{ fontWeight: 700, lineHeight: 1.25, color: colors.text.primary, fontSize: '1rem' }}
            >
              {schoolName}
            </Typography>
            <Typography variant="caption" sx={{ color: colors.text.secondary, fontSize: '0.75rem' }}>
              School Management System
            </Typography>
          </Box>
        </Stack>

        {/* Always-visible logo when collapsed */}
        {collapsed && (
          <Box
            sx={{
              width: 40,
              height: 40,
              borderRadius: 2,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              overflow: 'hidden',
              backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.12),
              color: 'primary.main',
            }}
          >
            {logoUrl ? (
              <Image
                src={logoUrl}
                alt={`${schoolName} logo`}
                width={40}
                height={40}
                style={{ objectFit: 'cover' }}
              />
            ) : (
              <CrestIcon sx={{ fontSize: 22 }} />
            )}
          </Box>
        )}

        {!collapsed && (
          <Tooltip title="Collapse sidebar" placement="right">
            <IconButton
              size="small"
              onClick={() => setCollapsed(true)}
              aria-label="Collapse sidebar"
              sx={{
                color: colors.text.secondary,
                border: `1px solid ${colors.border.light}`,
                borderRadius: 1.5,
                width: 32,
                height: 32,
                '&:hover': {
                  backgroundColor: colors.background.default,
                  color: colors.text.primary,
                },
              }}
            >
              <ChevronLeftIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>
        )}
      </Stack>

      {/* Expand button when collapsed */}
      {collapsed && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 1, flexShrink: 0 }}>
          <Tooltip title="Expand sidebar" placement="right">
            <IconButton
              size="small"
              onClick={() => setCollapsed(false)}
              aria-label="Expand sidebar"
              sx={{
                color: colors.text.secondary,
                border: `1px solid ${colors.border.light}`,
                borderRadius: 1.5,
                width: 36,
                height: 36,
                '&:hover': {
                  backgroundColor: colors.background.default,
                  color: colors.text.primary,
                },
              }}
            >
              <ChevronRightIcon sx={{ fontSize: 20 }} />
            </IconButton>
          </Tooltip>
        </Box>
      )}

      {/* Search — only when expanded */}
      {!collapsed && (
        <Box
          sx={{
            px: 2,
            pt: 1.75,
            pb: 1.25,
            borderBottom: `1px solid ${colors.border.light}`,
            flexShrink: 0,
          }}
        >
          <TextField
            size="small"
            fullWidth
            placeholder="Find a page…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Filter navigation items"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ fontSize: 18, color: colors.text.secondary }} />
                </InputAdornment>
              ),
              endAdornment: query ? (
                <InputAdornment position="end">
                  <IconButton
                    size="small"
                    aria-label="Clear filter"
                    onClick={() => setQuery('')}
                    edge="end"
                  >
                    <ClearIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                </InputAdornment>
              ) : null,
              sx: {
                borderRadius: 2,
                fontSize: 14,
                backgroundColor: colors.background.default,
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: colors.border.light,
                },
              },
            }}
          />
        </Box>
      )}

      {/* Nav list */}
      <Box
        sx={{
          px: collapsed ? 1 : 1.5,
          py: 1.5,
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          scrollBehavior: 'smooth',
          '&::-webkit-scrollbar': { width: 1 },
          '&::-webkit-scrollbar-track': { backgroundColor: 'transparent' },
          '&::-webkit-scrollbar-thumb': {
            backgroundColor: colors.border.default,
            borderRadius: 0,
            '&:hover': { backgroundColor: colors.border.light },
          },
        }}
      >
        {isSearching && displayModules.length === 0 && (
          <Box sx={{ px: 1.5, py: 3, textAlign: 'center' }}>
            <Typography variant="body2" sx={{ color: colors.text.secondary, fontWeight: 500 }}>
              No pages match “{query}”
            </Typography>
            <Typography variant="caption" sx={{ color: colors.text.secondary, display: 'block', mt: 0.5 }}>
              Try a different keyword
            </Typography>
          </Box>
        )}

        {displayModules.map((module) => {
          const ModuleIcon = module.icon;
          const isOpen = !collapsed && (isSearching || expanded.has(module.key));
          const hasActiveItem = module.sections.some((s) => isActivePath(pathname, s.href));

          const moduleButton = (
            <ListItemButton
              onClick={() => {
                if (collapsed) {
                  // In collapsed mode a click expands the sidebar and opens the module
                  setCollapsed(false);
                  setExpanded((prev) => new Set(prev).add(module.key));
                } else {
                  toggleModule(module.key);
                }
              }}
              aria-expanded={isOpen}
              sx={{
                px: collapsed ? 1 : 1.5,
                py: 1.25, // more vertical space
                borderRadius: 0,
                gap: 1.5,
                justifyContent: collapsed ? 'center' : 'flex-start',
                minHeight: 48,
                ...(hasActiveItem
                  ? {
                      backgroundColor: (theme) =>
                        alpha(theme.palette.primary.main, 0.08),
                    }
                  : {}),
                '&:hover': {
                  backgroundColor: hasActiveItem ? (theme) => alpha(theme.palette.primary.main, 0.12) : alpha(colors.text.primary, 0.04),
                },
                '&.Mui-focusVisible': {
                  outline: `2px solid`,
                  outlineColor: (theme) => theme.palette.primary.main,
                  outlineOffset: 2,
                },
              }}
            >
              <Box
                sx={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  backgroundColor: colors.gray[100],
                  color: hasActiveItem ? (theme) => theme.palette.primary.main : colors.text.secondary,
                }}
              >
                <ModuleIcon sx={{ fontSize: 18 }} />
              </Box>

              {!collapsed && (
                <>
                  <Typography
                    variant="body1"
                    sx={{
                      fontWeight: 650,
                      color: hasActiveItem ? (theme) => theme.palette.primary.main : colors.text.primary,
                      flex: 1,
                      letterSpacing: 0.15,
                      fontSize: '0.95rem',
                    }}
                  >
                    {module.label}
                  </Typography>

                  <Box
                    sx={{
                      minWidth: 22,
                      height: 20,
                      px: 0.75,
                      borderRadius: 1,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      backgroundColor: colors.background.default,
                      border: `1px solid ${colors.border.light}`,
                    }}
                  >
                    <Typography
                      component="span"
                      sx={{
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        color: colors.text.secondary,
                        lineHeight: 1,
                      }}
                    >
                      {module.sections.length}
                    </Typography>
                  </Box>

                  <ExpandMoreIcon
                    sx={{
                      fontSize: 20,
                      color: colors.text.secondary,
                      transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                      transition: `transform ${motion.normal}ms ${motion.easing}`,
                      '@media (prefers-reduced-motion: reduce)': {
                        transition: 'none',
                      },
                    }}
                  />
                </>
              )}
            </ListItemButton>
          );

          return (
            <Box key={module.key} sx={{ mb: collapsed ? 0.75 : 1.25 }}>
              {collapsed ? (
                <Tooltip title={module.label} placement="right" arrow>
                  {moduleButton}
                </Tooltip>
              ) : (
                moduleButton
              )}

              <Collapse in={isOpen} timeout={180} unmountOnExit>
                <List
                  sx={{
                    py: 0.75,
                    pl: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 0.5, // more space between leaf items
                    ml: '18px',
                    borderLeft: `2px solid ${colors.border.light}`,
                  }}
                >
                  {module.sections.map((section) => {
                    const isActive = isActivePath(pathname, section.href);

                    return (
                      <ListItem key={section.href} disablePadding>
                        <ListItemButton
                          component={Link}
                          href={section.href}
                          selected={isActive}
                          onClick={onNavigate}
                          aria-current={isActive ? 'page' : undefined}
                          sx={{
                            pl: 2.25,
                            pr: 1.5,
                            py: 1, // taller hit area
                            ml: -0.25,
                            borderLeft: '2px solid',
                            borderLeftColor: isActive ? (theme) => theme.palette.primary.main : 'transparent',
                            borderRadius: '0 10px 10px 0',
                            color: isActive ? (theme) => theme.palette.primary.main : colors.text.primary,
                            backgroundColor: isActive
                              ? (theme) => alpha(theme.palette.primary.main, 0.08)
                              : 'transparent',
                            transition: `background-color ${motion.fast}ms ${motion.easing}, border-color ${motion.fast}ms ${motion.easing}`,
                            '@media (prefers-reduced-motion: reduce)': {
                              transition: 'none',
                            },
                            '&:hover': {
                              backgroundColor: isActive
                                ? (theme) => alpha(theme.palette.primary.main, 0.12)
                                : colors.background.default,
                              borderLeftColor: isActive ? (theme) => theme.palette.primary.main : colors.border.default,
                            },
                            '&.Mui-focusVisible': {
                              outline: `2px solid`,
                              outlineColor: (theme) => theme.palette.primary.main,
                              outlineOffset: 1,
                            },
                          }}
                        >
                          <ListItemText
                            primary={section.label}
                            primaryTypographyProps={{
                              variant: 'body2',
                              sx: {
                                fontWeight: isActive ? 600 : 500,
                                color: 'inherit',
                                fontSize: '0.9rem', // larger leaf text
                              },
                            }}
                          />
                        </ListItemButton>
                      </ListItem>
                    );
                  })}
                </List>
              </Collapse>
            </Box>
          );
        })}
      </Box>

      {/* Footer */}
      <Box
        sx={{
          borderTop: `1px solid ${colors.border.light}`,
          px: collapsed ? 1 : 1.5,
          py: 1.5,
          flexShrink: 0,
        }}
      >
        <Stack
          direction="row"
          alignItems="center"
          spacing={1.25}
          justifyContent={collapsed ? 'center' : 'flex-start'}
        >
          <Tooltip title={collapsed ? userName : ''} placement="right">
            <Avatar
              sx={{
                width: 36,
                height: 36,
                fontSize: 14,
                fontWeight: 700,
                bgcolor: (theme) => alpha(theme.palette.primary.main, 0.16),
                color: 'primary.main',
              }}
            >
              {initials(userName)}
            </Avatar>
          </Tooltip>

          {!collapsed && (
            <>
              <Box sx={{ minWidth: 0, flex: 1 }}>
                <Typography
                  variant="body2"
                  noWrap
                  sx={{ fontWeight: 600, color: colors.text.primary, lineHeight: 1.3, fontSize: '0.9rem' }}
                >
                  {userName}
                </Typography>
                <Typography
                  variant="caption"
                  noWrap
                  sx={{ color: colors.text.secondary, display: 'block', lineHeight: 1.2 }}
                >
                  @{userHandle}
                </Typography>
              </Box>

              <Tooltip title="Settings">
                <IconButton
                  component={Link}
                  href="/dashboard/settings/branding"
                  onClick={onNavigate}
                  aria-label="Settings"
                  size="small"
                  sx={{
                    width: 36,
                    height: 36,
                    color: colors.text.secondary,
                    border: `1px solid ${colors.border.light}`,
                    borderRadius: 1.5,
                    '&:hover': {
                      backgroundColor: colors.background.default,
                      color: colors.text.primary,
                      borderColor: colors.border.default,
                    },
                  }}
                >
                  <SettingsIcon sx={{ fontSize: 18 }} />
                </IconButton>
              </Tooltip>
            </>
          )}

          {collapsed && (
            <Tooltip title="Settings" placement="right">
              <IconButton
                component={Link}
                href="/dashboard/settings/branding"
                onClick={onNavigate}
                aria-label="Settings"
                size="small"
                sx={{
                  position: 'absolute',
                  // keep settings reachable; or hide and rely on avatar click if preferred
                  display: 'none',
                }}
              >
                <SettingsIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
      </Box>
    </Box>
  );
}