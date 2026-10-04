/** Primary / secondary button matching the web login's buttons. */

import {
  Pressable,
  StyleSheet,
  Text,
  View,
  type PressableProps,
  type ViewStyle,
} from 'react-native';

import { Colors, Fonts, FontSizes, Radius, Shadows } from '@/constants/theme';

interface BrandButtonProps extends Omit<PressableProps, 'style' | 'children'> {
  title: string;
  variant?: 'primary' | 'secondary';
  /** Rendered before the label — the Microsoft tile, in practice. */
  icon?: React.ReactNode;
  style?: ViewStyle;
}

export function BrandButton({
  title,
  variant = 'primary',
  icon,
  disabled,
  style,
  ...rest
}: BrandButtonProps) {
  const isPrimary = variant === 'primary';

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!disabled }}
      disabled={disabled}
      style={({ pressed }) => [
        styles.base,
        isPrimary ? styles.primary : styles.secondary,
        pressed && !disabled && (isPrimary ? styles.primaryPressed : styles.secondaryPressed),
        disabled && styles.disabled,
        style,
      ]}
      {...rest}>
      <View style={styles.content}>
        {icon}
        <Text
          style={[
            styles.label,
            isPrimary ? styles.labelPrimary : styles.labelSecondary,
            !!icon && styles.labelWithIcon,
          ]}>
          {title}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    height: 50,
    borderRadius: Radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  primary: {
    backgroundColor: Colors.brandSolid,
    ...Shadows.sm,
  },
  primaryPressed: {
    backgroundColor: Colors.brandStrong,
  },
  secondary: {
    backgroundColor: Colors.surface2,
    borderWidth: 1,
    borderColor: Colors.hairline,
  },
  secondaryPressed: {
    borderColor: Colors.ink3,
  },
  disabled: {
    opacity: 0.6,
  },
  label: {
    fontFamily: Fonts.semibold,
    fontSize: FontSizes.base,
  },
  labelWithIcon: {
    marginLeft: 10,
    fontFamily: Fonts.medium,
    fontSize: FontSizes.sm,
  },
  labelPrimary: {
    color: Colors.white,
  },
  labelSecondary: {
    color: Colors.ink,
  },
});
