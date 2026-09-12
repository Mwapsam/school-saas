/**
 * MUI theme factory.
 *
 * Creates a theme from design tokens. Handles:
 * - Tenant branding (primary/secondary color overrides)
 * - Component style overrides (theme.components)
 * - Typography scale
 * - Palette mapping
 *
 * This is the heart of the design system — all visual consistency flows from here.
 */

import { createTheme as createMuiTheme, type Theme, ThemeOptions } from '@mui/material/styles';
import { colors, paletteConfig } from '../tokens/colors';
import { fontFamily, muiTypographyVariants } from '../tokens/typography';
import { muiSpacing } from '../tokens/spacing';
import { muiShape } from '../tokens/radius';
import { muiTransitions } from '../tokens/motion';
import { muiElevations } from '../tokens/shadows';
import { spacing, radius } from '../tokens';

interface TenantBrandingOverrides {
  primaryColor?: string;  // hex color
  secondaryColor?: string; // hex color
}

/**
 * Build the MUI theme with component overrides, palette, and typography.
 */
export function buildTheme(branding?: TenantBrandingOverrides): Theme {
  const primaryColor = branding?.primaryColor || colors.action.primary;
  const secondaryColor = branding?.secondaryColor || colors.status.info;

  const themeOptions: ThemeOptions = {
    // Palette
    palette: {
      ...paletteConfig,
      primary: {
        ...paletteConfig.primary,
        main: primaryColor,
      },
      secondary: {
        ...paletteConfig.secondary,
        main: secondaryColor,
      },
    },

    // Typography
    typography: {
      fontFamily: fontFamily.primary,
      ...muiTypographyVariants,
    },

    // Shape
    shape: muiShape,

    // Spacing
    spacing: 4, // 4px base unit

    // Transitions
    transitions: muiTransitions,

    // Component overrides — the secret sauce
    components: {
      // Button
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontSize: 14,
            fontWeight: 600,
            borderRadius: radius.md,
            transition: `all 120ms ${muiTransitions.easing.easeInOut}`,
            '&:focus-visible': {
              outline: `2px solid ${primaryColor}`,
              outlineOffset: '2px',
            },
          },
          containedPrimary: {
            backgroundColor: primaryColor,
            color: colors.text.inverse,
            '&:hover': {
              backgroundColor: colors.action.primaryHover,
              boxShadow: muiElevations[1],
            },
            '&:active': {
              backgroundColor: colors.action.primaryActive,
            },
            '&:disabled': {
              backgroundColor: colors.action.primaryDisabled,
              color: colors.text.disabled,
            },
          },
          containedSecondary: {
            backgroundColor: colors.action.secondary,
            color: colors.text.primary,
            '&:hover': {
              backgroundColor: colors.action.secondaryHover,
              boxShadow: muiElevations[1],
            },
            '&:active': {
              backgroundColor: colors.action.secondaryActive,
            },
          },
          outlinedPrimary: {
            borderColor: primaryColor,
            color: primaryColor,
            '&:hover': {
              borderColor: colors.action.primaryHover,
              backgroundColor: `${primaryColor}08`,
            },
          },
          outlinedSecondary: {
            borderColor: colors.border.default,
            color: colors.text.primary,
            '&:hover': {
              borderColor: colors.text.primary,
              backgroundColor: colors.background.elevated,
            },
          },
          textPrimary: {
            color: primaryColor,
            '&:hover': {
              backgroundColor: `${primaryColor}08`,
            },
          },
        },
        defaultProps: {
          disableElevation: true,
        },
      },

      // Text field
      MuiTextField: {
        styleOverrides: {
          root: {
            '& .MuiInputBase-root': {
              borderRadius: radius.md,
              fontSize: 14,
              transition: `border-color 120ms ${muiTransitions.easing.easeInOut}`,
            },
            '& .MuiOutlinedInput-notchedOutline': {
              borderColor: colors.border.default,
            },
            '& .MuiOutlinedInput-root:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: colors.border.default,
            },
            '& .MuiOutlinedInput-root.Mui-focused .MuiOutlinedInput-notchedOutline': {
              borderColor: primaryColor,
            },
          },
        },
      },

      // Select
      MuiSelect: {
        styleOverrides: {
          root: {
            borderRadius: radius.md,
          },
        },
      },

      // Card
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: radius.lg,
            border: `1px solid ${colors.border.default}`,
            backgroundColor: colors.background.surface,
            boxShadow: 'none',
          },
        },
      },

      // Paper
      MuiPaper: {
        styleOverrides: {
          root: {
            borderRadius: radius.lg,
            backgroundColor: colors.background.surface,
          },
          elevation1: {
            boxShadow: muiElevations[1],
          },
          elevation2: {
            boxShadow: muiElevations[2],
          },
          elevation3: {
            boxShadow: muiElevations[3],
          },
        },
      },

      // Dialog
      MuiDialog: {
        styleOverrides: {
          paper: {
            borderRadius: radius.xl,
            boxShadow: muiElevations[24],
          },
        },
      },

      // Chip
      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: radius.sm,
            fontSize: 12,
          },
          filledPrimary: {
            backgroundColor: `${primaryColor}20`,
            color: primaryColor,
          },
          outlinedPrimary: {
            borderColor: primaryColor,
            color: primaryColor,
          },
        },
      },

      // Badge
      MuiBadge: {
        styleOverrides: {
          badge: {
            borderRadius: radius.full,
            fontSize: 10,
            fontWeight: 700,
          },
        },
      },

      // AppBar
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundColor: colors.background.surface,
            color: colors.text.primary,
            boxShadow: `0px 1px 3px ${colors.border.light}`,
            borderBottom: `1px solid ${colors.border.default}`,
          },
        },
      },

      // Drawer
      MuiDrawer: {
        styleOverrides: {
          paper: {
            backgroundColor: colors.background.surface,
            borderRight: `1px solid ${colors.border.default}`,
          },
        },
      },

      // Tab
      MuiTab: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontSize: 14,
            fontWeight: 600,
            color: colors.text.secondary,
            '&.Mui-selected': {
              color: primaryColor,
            },
          },
        },
      },

      // Menu
      MuiMenu: {
        styleOverrides: {
          paper: {
            borderRadius: radius.lg,
            boxShadow: muiElevations[8],
          },
        },
      },

      // Checkbox
      MuiCheckbox: {
        styleOverrides: {
          root: {
            borderRadius: radius.sm,
            '&.Mui-checked': {
              color: primaryColor,
            },
          },
        },
      },

      // Radio
      MuiRadio: {
        styleOverrides: {
          root: {
            '&.Mui-checked': {
              color: primaryColor,
            },
          },
        },
      },

      // Switch
      MuiSwitch: {
        styleOverrides: {
          root: {
            '& .MuiSwitch-switchBase.Mui-checked': {
              color: primaryColor,
            },
            '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
              backgroundColor: primaryColor,
            },
          },
        },
      },

      // Divider
      MuiDivider: {
        styleOverrides: {
          root: {
            borderColor: colors.border.default,
          },
        },
      },

      // Table
      MuiTable: {
        styleOverrides: {
          root: {
            backgroundColor: colors.background.surface,
          },
        },
      },

      MuiTableHead: {
        styleOverrides: {
          root: {
            '& .MuiTableCell-head': {
              backgroundColor: colors.background.default,
              color: colors.text.secondary,
              fontWeight: 600,
              fontSize: 12,
              textTransform: 'uppercase',
              letterSpacing: 0.5,
            },
          },
        },
      },

      MuiTableCell: {
        styleOverrides: {
          root: {
            borderColor: colors.border.default,
          },
        },
      },

      // Alert
      MuiAlert: {
        styleOverrides: {
          standardSuccess: {
            backgroundColor: colors.status.successLight,
            color: colors.text.primary,
          },
          standardWarning: {
            backgroundColor: colors.status.warningLight,
            color: colors.text.primary,
          },
          standardError: {
            backgroundColor: colors.status.errorLight,
            color: colors.text.primary,
          },
          standardInfo: {
            backgroundColor: colors.status.infoLight,
            color: colors.text.primary,
          },
        },
      },

      // Snackbar
      MuiSnackbarContent: {
        styleOverrides: {
          root: {
            borderRadius: radius.md,
            backgroundColor: colors.text.primary,
            color: colors.text.inverse,
          },
        },
      },
    },
  };

  return createMuiTheme(themeOptions);
}

export default buildTheme;
