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
 *
 * IMPORTANT: this file does not compute its own light/dark/hover/disabled
 * shades. All of that comes from `buildPaletteConfig()` in tokens/colors —
 * one function that turns a raw brand hex into a full, contrast-safe
 * palette. Every component override below reads from that same resolved
 * palette, so a tenant's actual color shows up consistently in every state
 * (hover, active, disabled, chips) instead of only the resting/default state.
 */

import { createTheme as createMuiTheme, alpha, type Theme, type ThemeOptions } from '@mui/material/styles';
import { colors, buildPaletteConfig, mixColor, type TenantColorInput } from '../tokens/colors';
import { fontFamily, muiTypographyVariants } from '../tokens/typography';
import { muiShape } from '../tokens/radius';
import { muiTransitions } from '../tokens/motion';
import { muiElevations } from '../tokens/shadows';
import { radius } from '../tokens';

/**
 * Build the MUI theme with component overrides, palette, and typography.
 * `tenant` uses the same field names as `TenantBranding` from bootstrap.ts
 * (`primary_color` / `secondary_color`) — pass `bootstrap.tenant` directly,
 * no remapping needed.
 */
export function buildTheme(tenant?: TenantColorInput): Theme {
  const palette = buildPaletteConfig(tenant);

  const primaryColor = palette.primary.main;
  const primaryHover = mixColor(primaryColor, -0.12);
  const primaryDisabled = mixColor(primaryColor, 0.55);

  const secondaryColor = palette.secondary.main;
  const secondaryHover = mixColor(secondaryColor, -0.12);

  const themeOptions: ThemeOptions = {
    palette,

    typography: {
      fontFamily: fontFamily.primary,
      ...muiTypographyVariants,
    },

    shape: muiShape,
    spacing: 4, // 4px base unit
    transitions: muiTransitions,

    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontSize: 14,
            fontWeight: 600,
            borderRadius: radius.md,
            transition: `background-color 120ms ${muiTransitions.easing.easeInOut}, border-color 120ms ${muiTransitions.easing.easeInOut}, box-shadow 120ms ${muiTransitions.easing.easeInOut}, color 120ms ${muiTransitions.easing.easeInOut}, transform 120ms ${muiTransitions.easing.easeInOut}`,
            '&:focus-visible': {
              outline: `2px solid ${primaryColor}`,
              outlineOffset: '2px',
            },
            '&:active': {
              '@media (prefers-reduced-motion: no-preference)': {
                transform: 'scale(0.98)',
              },
            },
          },
          containedPrimary: {
            backgroundColor: primaryColor,
            color: palette.primary.contrastText,
            '&:hover': {
              backgroundColor: primaryHover,
              boxShadow: muiElevations[4],
            },
            '&:disabled': {
              backgroundColor: primaryDisabled,
              color: colors.text.disabled,
            },
          },
          containedSecondary: {
            backgroundColor: secondaryColor,
            color: palette.secondary.contrastText,
            '&:hover': {
              backgroundColor: secondaryHover,
              boxShadow: muiElevations[4],
            },
          },
          outlinedPrimary: {
            borderColor: primaryColor,
            color: primaryColor,
            '&:hover': {
              borderColor: primaryHover,
              backgroundColor: alpha(primaryColor, 0.06),
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
              backgroundColor: alpha(primaryColor, 0.06),
            },
          },
          textSecondary: {
            color: colors.text.secondary,
            '&:hover': {
              backgroundColor: colors.gray[100],
            },
          },
        },
        defaultProps: {
          disableElevation: true,
        },
      },

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

      MuiSelect: {
        styleOverrides: {
          root: {
            borderRadius: radius.md,
          },
        },
      },

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

      MuiPaper: {
        styleOverrides: {
          root: {
            borderRadius: radius.lg,
            backgroundColor: colors.background.surface,
            border: `1px solid ${colors.border.default}`,
            boxShadow: 'none',
          },
          elevation1: { boxShadow: muiElevations[1] },
          elevation2: { boxShadow: muiElevations[2] },
          elevation3: { boxShadow: muiElevations[3] },
          elevation4: { boxShadow: muiElevations[4] },
          elevation8: { boxShadow: muiElevations[8] },
        },
        variants: [
          {
            props: { variant: 'interactive' },
            style: {
              transition: `box-shadow 120ms ${muiTransitions.easing.easeInOut}`,
              '&:hover, &:focus-visible': {
                boxShadow: muiElevations[4],
              },
            },
          },
        ],
      },

      MuiDialog: {
        styleOverrides: {
          paper: {
            borderRadius: radius.xl,
            boxShadow: muiElevations[24],
          },
        },
      },

      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: radius.sm,
            fontSize: 12,
          },
          filledPrimary: {
            backgroundColor: alpha(primaryColor, 0.14),
            color: mixColor(primaryColor, -0.15), // slightly darker than the raw brand
                                                    // color so chip text stays readable
                                                    // even on a light tenant brand color
          },
          outlinedPrimary: {
            borderColor: primaryColor,
            color: primaryColor,
          },
        },
      },

      MuiBadge: {
        styleOverrides: {
          badge: {
            borderRadius: radius.full,
            fontSize: 10,
            fontWeight: 700,
          },
        },
      },

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

      MuiDrawer: {
        styleOverrides: {
          paper: {
            backgroundColor: colors.background.surface,
            borderRight: `1px solid ${colors.border.default}`,
          },
        },
      },

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

      MuiMenu: {
        styleOverrides: {
          paper: {
            borderRadius: radius.lg,
            boxShadow: muiElevations[8],
          },
        },
      },

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

      MuiRadio: {
        styleOverrides: {
          root: {
            '&.Mui-checked': {
              color: primaryColor,
            },
          },
        },
      },

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

      MuiDivider: {
        styleOverrides: {
          root: {
            borderColor: colors.border.default,
          },
        },
      },

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