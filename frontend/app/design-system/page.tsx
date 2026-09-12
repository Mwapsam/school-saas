'use client';

import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Stack,
  TextField,
  Select,
  MenuItem,
  Chip,
  Badge,
  Alert,
  Divider,
  Switch,
  Checkbox,
  Radio,
  RadioGroup,
  FormControlLabel,
} from '@mui/material';
import { Plus as PlusIcon } from 'lucide-react';
import { Page } from '@/components/page/Page';
import { PageHeader } from '@/components/page/PageHeader';
import { PageContent } from '@/components/page/PageContent';
import { EmptyState } from '@/components/feedback';
import { colors, spacing, typography, radius, shadows, motion } from '@/design-system/tokens';

/**
 * Design System Playground
 *
 * Development-only route for visually testing all design system components and tokens.
 * This page demonstrates every primitive, state, and pattern in the system.
 */
export default function DesignSystemPage() {
  return (
    <Page>
      <PageHeader
        title="Design System"
        description="Visual test laboratory for all design system components and tokens."
      />

      <PageContent>
        {/* Typography */}
        <Card sx={{ mb: spacing.section, p: spacing.card }}>
          <Typography variant="h2" sx={{ mb: spacing.component }}>
            Typography
          </Typography>
          <Divider sx={{ mb: spacing.component }} />

          <Stack spacing={spacing.element}>
            <Box>
              <Typography variant="h1">Display (32px / 700)</Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                The largest typography level, rarely used
              </Typography>
            </Box>

            <Box>
              <Typography variant="h1">Heading 1 (28px / 700)</Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Page titles
              </Typography>
            </Box>

            <Box>
              <Typography variant="h2">Heading 2 (24px / 650)</Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Section headings
              </Typography>
            </Box>

            <Box>
              <Typography variant="h3">Heading 3 (20px / 650)</Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Subsection headings
              </Typography>
            </Box>

            <Box>
              <Typography variant="body1">Body (15px / 400)</Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                Primary content text
              </Typography>
            </Box>

            <Box>
              <Typography variant="body2">Body Small (14px / 400)</Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Secondary content text
              </Typography>
            </Box>

            <Box>
              <Typography variant="caption">Caption (12px / 500)</Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Helper text, labels, and hints
              </Typography>
            </Box>
          </Stack>
        </Card>

        {/* Colors */}
        <Card sx={{ mb: spacing.section, p: spacing.card }}>
          <Typography variant="h2" sx={{ mb: spacing.component }}>
            Colors
          </Typography>
          <Divider sx={{ mb: spacing.component }} />

          <Stack spacing={spacing.component}>
            {/* Background */}
            <Box>
              <Typography variant="h3" sx={{ mb: spacing.element }}>
                Backgrounds
              </Typography>
              <Stack direction="row" spacing={spacing.element}>
                <Box
                  sx={{
                    p: spacing.component,
                    bg: colors.background.default,
                    border: `1px solid ${colors.border.default}`,
                    borderRadius: radius.md,
                    minWidth: 200,
                  }}
                >
                  <Typography variant="body2">Default</Typography>
                  <Typography variant="caption">{colors.background.default}</Typography>
                </Box>
                <Box
                  sx={{
                    p: spacing.component,
                    bg: colors.background.surface,
                    border: `1px solid ${colors.border.default}`,
                    borderRadius: radius.md,
                    minWidth: 200,
                  }}
                >
                  <Typography variant="body2">Surface</Typography>
                  <Typography variant="caption">{colors.background.surface}</Typography>
                </Box>
              </Stack>
            </Box>

            {/* Text */}
            <Box>
              <Typography variant="h3" sx={{ mb: spacing.element }}>
                Text Colors
              </Typography>
              <Stack spacing={spacing.element}>
                <Typography sx={{ color: colors.text.primary }}>Primary Text</Typography>
                <Typography sx={{ color: colors.text.secondary }}>Secondary Text</Typography>
                <Typography sx={{ color: colors.text.muted }}>Muted Text</Typography>
                <Typography sx={{ color: colors.text.disabled }}>Disabled Text</Typography>
              </Stack>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant="h3" sx={{ mb: spacing.element }}>
                Status Colors
              </Typography>
              <Stack direction="row" spacing={spacing.element}>
                <Chip label="Success" sx={{ backgroundColor: colors.status.success, color: 'white' }} />
                <Chip label="Warning" sx={{ backgroundColor: colors.status.warning, color: 'white' }} />
                <Chip label="Error" sx={{ backgroundColor: colors.status.error, color: 'white' }} />
                <Chip label="Info" sx={{ backgroundColor: colors.status.info, color: 'white' }} />
                <Chip label="Pending" sx={{ backgroundColor: colors.status.pending, color: 'white' }} />
              </Stack>
            </Box>
          </Stack>
        </Card>

        {/* Buttons */}
        <Card sx={{ mb: spacing.section, p: spacing.card }}>
          <Typography variant="h2" sx={{ mb: spacing.component }}>
            Buttons
          </Typography>
          <Divider sx={{ mb: spacing.component }} />

          <Stack spacing={spacing.component}>
            <Box>
              <Typography variant="h3" sx={{ mb: spacing.element }}>
                Contained
              </Typography>
              <Stack direction="row" spacing={spacing.element}>
                <Button variant="contained">Primary</Button>
                <Button variant="contained" disabled>
                  Disabled
                </Button>
              </Stack>
            </Box>

            <Box>
              <Typography variant="h3" sx={{ mb: spacing.element }}>
                Outlined
              </Typography>
              <Stack direction="row" spacing={spacing.element}>
                <Button variant="outlined">Secondary</Button>
                <Button variant="outlined" disabled>
                  Disabled
                </Button>
              </Stack>
            </Box>

            <Box>
              <Typography variant="h3" sx={{ mb: spacing.element }}>
                Text
              </Typography>
              <Stack direction="row" spacing={spacing.element}>
                <Button variant="text">Text Button</Button>
                <Button variant="text" disabled>
                  Disabled
                </Button>
              </Stack>
            </Box>

            <Box>
              <Typography variant="h3" sx={{ mb: spacing.element }}>
                With Icons
              </Typography>
              <Stack direction="row" spacing={spacing.element}>
                <Button variant="contained" startIcon={<PlusIcon size={16} />}>
                  New Item
                </Button>
              </Stack>
            </Box>
          </Stack>
        </Card>

        {/* Form Elements */}
        <Card sx={{ mb: spacing.section, p: spacing.card }}>
          <Typography variant="h2" sx={{ mb: spacing.component }}>
            Form Elements
          </Typography>
          <Divider sx={{ mb: spacing.component }} />

          <Stack spacing={spacing.component}>
            <Box>
              <Typography variant="h3" sx={{ mb: spacing.element }}>
                Text Input
              </Typography>
              <TextField
                label="Name"
                placeholder="Enter your name"
                fullWidth
                sx={{ maxWidth: 300 }}
              />
            </Box>

            <Box>
              <Typography variant="h3" sx={{ mb: spacing.element }}>
                Select
              </Typography>
              <Select defaultValue="option1" sx={{ minWidth: 200 }}>
                <MenuItem value="option1">Option 1</MenuItem>
                <MenuItem value="option2">Option 2</MenuItem>
                <MenuItem value="option3">Option 3</MenuItem>
              </Select>
            </Box>

            <Box>
              <Typography variant="h3" sx={{ mb: spacing.element }}>
                Checkbox
              </Typography>
              <FormControlLabel control={<Checkbox />} label="I agree to the terms" />
            </Box>

            <Box>
              <Typography variant="h3" sx={{ mb: spacing.element }}>
                Radio
              </Typography>
              <RadioGroup>
                <FormControlLabel control={<Radio />} label="Option 1" />
                <FormControlLabel control={<Radio />} label="Option 2" />
              </RadioGroup>
            </Box>

            <Box>
              <Typography variant="h3" sx={{ mb: spacing.element }}>
                Switch
              </Typography>
              <FormControlLabel control={<Switch />} label="Enable notifications" />
            </Box>
          </Stack>
        </Card>

        {/* Cards */}
        <Card sx={{ mb: spacing.section, p: spacing.card }}>
          <Typography variant="h2" sx={{ mb: spacing.component }}>
            Cards & Surfaces
          </Typography>
          <Divider sx={{ mb: spacing.component }} />

          <Stack spacing={spacing.component}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h3" sx={{ mb: spacing.element }}>
                  Card Title
                </Typography>
                <Typography variant="body1" sx={{ color: 'text.secondary' }}>
                  This is a card surface with content.
                </Typography>
              </CardContent>
            </Card>
          </Stack>
        </Card>

        {/* Alerts */}
        <Card sx={{ mb: spacing.section, p: spacing.card }}>
          <Typography variant="h2" sx={{ mb: spacing.component }}>
            Alerts
          </Typography>
          <Divider sx={{ mb: spacing.component }} />

          <Stack spacing={spacing.element}>
            <Alert severity="success">This is a success alert message.</Alert>
            <Alert severity="warning">This is a warning alert message.</Alert>
            <Alert severity="error">This is an error alert message.</Alert>
            <Alert severity="info">This is an informational alert message.</Alert>
          </Stack>
        </Card>

        {/* Empty State */}
        <Card sx={{ mb: spacing.section, overflow: 'hidden' }}>
          <Box sx={{ p: spacing.card }}>
            <Typography variant="h2" sx={{ mb: spacing.component }}>
              Empty State
            </Typography>
            <Divider sx={{ mb: spacing.component }} />
          </Box>

          <EmptyState
            title="No items to display"
            description="When a list or table is empty, show this state."
            action={{
              label: 'Create Item',
              onClick: () => alert('Create action clicked'),
            }}
          />
        </Card>

        {/* Spacing Scale */}
        <Card sx={{ mb: spacing.section, p: spacing.card }}>
          <Typography variant="h2" sx={{ mb: spacing.component }}>
            Spacing Scale
          </Typography>
          <Divider sx={{ mb: spacing.component }} />

          <Stack spacing={spacing.element}>
            <Typography variant="body2">
              Base unit: 4px. All spacing values are MUI multipliers (1 = 4px, 2 = 8px, etc.)
            </Typography>

            <Stack spacing={spacing.element}>
              {Object.entries(spacing).map(([key, value]) => (
                <Box key={key} sx={{ display: 'flex', alignItems: 'center', gap: spacing.element }}>
                  <Typography variant="caption" sx={{ minWidth: 100 }}>
                    {key}
                  </Typography>
                  <Box
                    sx={{
                      width: `${value * 4}px`,
                      height: '20px',
                      backgroundColor: colors.action.primary,
                      borderRadius: radius.sm,
                    }}
                  />
                  <Typography variant="caption">{value * 4}px</Typography>
                </Box>
              ))}
            </Stack>
          </Stack>
        </Card>

        {/* Border Radius */}
        <Card sx={{ mb: spacing.section, p: spacing.card }}>
          <Typography variant="h2" sx={{ mb: spacing.component }}>
            Border Radius
          </Typography>
          <Divider sx={{ mb: spacing.component }} />

          <Stack direction="row" spacing={spacing.component}>
            <Box
              sx={{
                width: 100,
                height: 100,
                backgroundColor: colors.action.primary,
                borderRadius: radius.sm,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Typography variant="caption" sx={{ color: 'white', textAlign: 'center' }}>
                sm ({radius.sm}px)
              </Typography>
            </Box>
            <Box
              sx={{
                width: 100,
                height: 100,
                backgroundColor: colors.action.primary,
                borderRadius: radius.md,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Typography variant="caption" sx={{ color: 'white', textAlign: 'center' }}>
                md ({radius.md}px)
              </Typography>
            </Box>
            <Box
              sx={{
                width: 100,
                height: 100,
                backgroundColor: colors.action.primary,
                borderRadius: radius.lg,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Typography variant="caption" sx={{ color: 'white', textAlign: 'center' }}>
                lg ({radius.lg}px)
              </Typography>
            </Box>
            <Box
              sx={{
                width: 100,
                height: 100,
                backgroundColor: colors.action.primary,
                borderRadius: radius.xl,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Typography variant="caption" sx={{ color: 'white', textAlign: 'center' }}>
                xl ({radius.xl}px)
              </Typography>
            </Box>
          </Stack>
        </Card>

        {/* Shadows */}
        <Card sx={{ mb: spacing.section, p: spacing.card }}>
          <Typography variant="h2" sx={{ mb: spacing.component }}>
            Elevation / Shadows
          </Typography>
          <Divider sx={{ mb: spacing.component }} />

          <Stack direction="row" spacing={spacing.component}>
            <Box
              sx={{
                width: 120,
                height: 120,
                backgroundColor: colors.background.surface,
                border: `1px solid ${colors.border.default}`,
                borderRadius: radius.md,
                boxShadow: shadows.none,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                textAlign: 'center',
              }}
            >
              <Typography variant="caption">No Shadow</Typography>
            </Box>

            <Box
              sx={{
                width: 120,
                height: 120,
                backgroundColor: colors.background.surface,
                borderRadius: radius.md,
                boxShadow: shadows.subtle,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                textAlign: 'center',
              }}
            >
              <Typography variant="caption">Subtle</Typography>
            </Box>

            <Box
              sx={{
                width: 120,
                height: 120,
                backgroundColor: colors.background.surface,
                borderRadius: radius.md,
                boxShadow: shadows.floating,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                textAlign: 'center',
              }}
            >
              <Typography variant="caption">Floating</Typography>
            </Box>
          </Stack>
        </Card>

        {/* Motion */}
        <Card sx={{ mb: spacing.section, p: spacing.card }}>
          <Typography variant="h2" sx={{ mb: spacing.component }}>
            Motion / Transitions
          </Typography>
          <Divider sx={{ mb: spacing.component }} />

          <Stack spacing={spacing.element}>
            <Typography variant="body2">Fast: {motion.fast}ms</Typography>
            <Typography variant="body2">Normal: {motion.normal}ms</Typography>
            <Typography variant="body2">Slow: {motion.slow}ms</Typography>
            <Typography variant="body2">Easing: {motion.easing}</Typography>
          </Stack>
        </Card>
      </PageContent>
    </Page>
  );
}
