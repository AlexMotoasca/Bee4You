/**
 * Design tokens. Use these instead of ad-hoc values in components.
 * Field rules: high contrast for direct sunlight, touch targets >= 56 dp, large type.
 */
export const colors = {
  background: '#FFFBF2',
  surface: '#FFFFFF',
  surfaceMuted: '#F5EFE1',
  border: '#E2D6BC',
  text: '#1C1A17',
  textMuted: '#5C5546',
  primary: '#E8A317', // honey
  primaryPressed: '#C98A0C',
  onPrimary: '#1C1A17', // dark text on honey keeps contrast in sunlight
  success: '#2E7D32',
  warning: '#B26A00',
  danger: '#B3261E',
  onDanger: '#FFFFFF',
} as const;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const radius = { sm: 8, md: 12, lg: 16, pill: 999 } as const;

export const font = {
  small: 15,
  body: 18,
  large: 22,
  title: 28,
  huge: 34,
} as const;

/** Minimum touch target for gloved hands. */
export const touch = { min: 56 } as const;
