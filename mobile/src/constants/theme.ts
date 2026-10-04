/**
 * BrainVar Trajectory Explorer — design tokens
 *
 * The same values as the web app's custom properties in
 * `frontend/src/index.css`, restated as objects because React Native has no
 * cascade to inherit them from. Names match the CSS variables so the two can
 * be diffed by eye: `--surface-2` is `Colors.surface2`, and so on.
 *
 * Dark only. The web app has a light theme behind a toggle; the phone app
 * ships one scheme until there is a reason for the second.
 */

import { Platform, TextStyle, ViewStyle } from 'react-native';

export const Colors = {
  /** Neutral ramp — TailAdmin gray, as on the web. */
  bg: '#101828', //        gray-900, the page
  surface: '#171f2e', //   cards
  surface2: '#1d2939', //  gray-800, elevated: inputs
  ink: '#f2f4f7', //       gray-100
  ink2: '#d0d5dd', //      gray-300
  ink3: '#98a2b3', //      gray-400
  hairline: '#1d2939',
  hairlineStrong: '#344054',

  /** Brand — lifted one step in dark so it stays legible on a dark ground. */
  brand: '#7592ff', //       brand-400
  brandStrong: '#9cb9ff', // brand-300, pressed
  brandSolid: '#465fff', //  brand-500, filled buttons keep the true brand

  danger: '#fda29b',
  dangerSolid: '#d92d20',
  /** RN has no color-mix(), so the soft fills are pre-resolved. */
  dangerSoft: 'rgba(240, 68, 56, 0.16)',
  brandSoft: 'rgba(70, 95, 255, 0.18)',

  white: '#ffffff',
  transparent: 'transparent',
} as const;

/**
 * Keys map 1:1 to the @expo-google-fonts/outfit weights loaded in the root
 * layout. Keep in sync with the `useFonts` call there.
 */
export const Fonts = {
  regular: 'Outfit_400Regular',
  medium: 'Outfit_500Medium',
  semibold: 'Outfit_600SemiBold',
  bold: 'Outfit_700Bold',
} as const;

export const FontSizes = {
  xs: 12,
  sm: 14,
  base: 16,
  lg: 18,
  xl: 20,
  '2xl': 24,
  '3xl': 30,
} as const;

/** 4px spacing scale. */
export const Spacing = {
  1: 4,
  1.5: 6,
  2: 8,
  3: 12,
  4: 16,
  5: 20,
  6: 24,
  8: 32,
  10: 40,
  12: 48,
} as const;

export const Radius = {
  sm: 8,
  md: 9, // inputs and buttons, as the web login card uses
  lg: 12,
  xl: 16, // the login card itself
  full: 9999,
} as const;

export const Shadows: Record<'sm' | 'lg', ViewStyle> = {
  sm: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.2,
    shadowRadius: 3,
    elevation: 2,
  },
  lg: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.35,
    shadowRadius: 20,
    elevation: 10,
  },
};

export const Typography = {
  title: {
    fontFamily: Fonts.bold,
    fontSize: FontSizes['2xl'],
    color: Colors.ink,
  } satisfies TextStyle,
  body: {
    fontFamily: Fonts.regular,
    fontSize: FontSizes.sm,
    color: Colors.ink2,
  } satisfies TextStyle,
  label: {
    fontFamily: Fonts.medium,
    fontSize: FontSizes.sm,
    color: Colors.ink2,
  } satisfies TextStyle,
};

export const isIOS = Platform.OS === 'ios';
