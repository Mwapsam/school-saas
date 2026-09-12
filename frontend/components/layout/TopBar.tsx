'use client';

import { useRouter } from 'next/navigation';
import { useState, type MouseEvent } from 'react';
import Image from 'next/image';
import {
  AppBar,
  Toolbar,
  IconButton,
  Typography,
  Avatar,
  Menu,
  MenuItem,
  Box,
  Divider,
  ListItemIcon,
  Stack,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import LogoutIcon from '@mui/icons-material/Logout';
import SettingsIcon from '@mui/icons-material/Settings';
import { useTenantStore } from '@/lib/tenant/store';
import { spacing, colors } from '@/design-system/tokens';

export function TopBar({ onMenuClick }: { onMenuClick: () => void }) {
  const router = useRouter();
  const bootstrap = useTenantStore((state) => state.bootstrap);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const handleMenuOpen = (event: MouseEvent<HTMLElement>) => setAnchorEl(event.currentTarget);
  const handleMenuClose = () => setAnchorEl(null);

  async function handleLogout() {
    handleMenuClose();
    await fetch('/api/auth/logout', { method: 'POST' });
    router.push('/auth/login');
  }

  const initials = bootstrap?.user.full_name
    ?.split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <AppBar
      position="fixed"
      sx={{
        zIndex: (theme) => theme.zIndex.drawer + 1,
        backgroundColor: colors.background.surface,
        color: colors.text.primary,
        borderBottom: `1px solid ${colors.border.default}`,
        boxShadow: `0px 1px 3px ${colors.border.light}`,
      }}
    >
      <Toolbar sx={{ gap: spacing.component, minHeight: 64 }}>
        {/* Mobile menu button */}
        <IconButton
          edge="start"
          onClick={onMenuClick}
          sx={{ display: { md: 'none' } }}
          aria-label="open navigation"
        >
          <MenuIcon />
        </IconButton>

        {/* Logo and tenant name */}
        <Stack direction="row" alignItems="center" spacing={spacing.element} sx={{ flexGrow: 1 }}>
          {bootstrap?.tenant.logo_url && (
            <Box sx={{ display: 'flex', alignItems: 'center', height: 40 }}>
              <Image
                src={bootstrap.tenant.logo_url}
                alt={bootstrap.tenant.name}
                height={40}
                width="auto"
                style={{ maxWidth: 120, objectFit: 'contain' }}
              />
            </Box>
          )}
          <Typography variant="h6" noWrap sx={{ fontWeight: 600, display: { xs: 'none', sm: 'block' } }}>
            {bootstrap?.tenant.name || 'School Management Platform'}
          </Typography>
        </Stack>

        {/* User menu */}
        {bootstrap && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: spacing.element }}>
            <IconButton
              onClick={handleMenuOpen}
              size="small"
              aria-label="account menu"
              sx={{ ml: 'auto' }}
            >
              <Avatar
                sx={{
                  width: 36,
                  height: 36,
                  fontSize: 14,
                  fontWeight: 600,
                  // Was colors.action.primary — that token no longer exists now that
                  // primary is tenant-derived (buildPaletteConfig). Reading it from
                  // the live theme means the avatar automatically picks up each
                  // school's actual brand color instead of a fixed default blue.
                  backgroundColor: (theme) => theme.palette.primary.main,
                  // contrastText is the WCAG-luminance-checked pick from
                  // buildPaletteConfig, so this stays readable even if a tenant's
                  // brand color is light (colors.text.inverse was always white,
                  // which would fail on a pale brand color).
                  color: (theme) => theme.palette.primary.contrastText,
                }}
              >
                {initials}
              </Avatar>
            </IconButton>

            <Menu
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={handleMenuClose}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            >
              <MenuItem disabled sx={{ opacity: '1 !important' }}>
                <Box>
                  <Typography variant="body2" fontWeight={600} sx={{ color: colors.text.primary }}>
                    {bootstrap.user.full_name}
                  </Typography>
                  <Typography variant="caption" sx={{ color: colors.text.secondary }}>
                    {bootstrap.user.email}
                  </Typography>
                </Box>
              </MenuItem>
              <Divider />
              <MenuItem onClick={() => { handleMenuClose(); router.push('/dashboard/settings/branding'); }}>
                <ListItemIcon>
                  <SettingsIcon fontSize="small" />
                </ListItemIcon>
                Settings
              </MenuItem>
              <MenuItem onClick={handleLogout}>
                <ListItemIcon>
                  <LogoutIcon fontSize="small" />
                </ListItemIcon>
                Logout
              </MenuItem>
            </Menu>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
}