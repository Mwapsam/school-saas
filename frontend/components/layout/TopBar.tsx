'use client';

import { useRouter } from 'next/navigation';
import { useState, type MouseEvent } from 'react';
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
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import LogoutIcon from '@mui/icons-material/Logout';
import { useTenantStore } from '@/lib/tenant/store';

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
      color="inherit"
      elevation={1}
      sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}
    >
      <Toolbar>
        <IconButton
          edge="start"
          onClick={onMenuClick}
          sx={{ mr: 2, display: { md: 'none' } }}
          aria-label="open navigation"
        >
          <MenuIcon />
        </IconButton>

        <Typography variant="h6" noWrap sx={{ flexGrow: 1, fontWeight: 600 }}>
          {bootstrap?.tenant.name || 'School Management Platform'}
        </Typography>

        {bootstrap && (
          <Box>
            <IconButton onClick={handleMenuOpen} size="small" aria-label="account menu">
              <Avatar sx={{ width: 32, height: 32, fontSize: 14 }}>{initials}</Avatar>
            </IconButton>
            <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleMenuClose}>
              <MenuItem disabled sx={{ opacity: '1 !important' }}>
                <Box>
                  <Typography variant="body2" fontWeight={600}>
                    {bootstrap.user.full_name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {bootstrap.user.email}
                  </Typography>
                </Box>
              </MenuItem>
              <Divider />
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
