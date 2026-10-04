/** Labelled text input matching the web login, with an optional reveal toggle. */

import { useState } from 'react';
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  type TextInputProps,
  type ViewStyle,
} from 'react-native';

import { Colors, Fonts, FontSizes, Radius, Spacing } from '@/constants/theme';

interface BrandTextFieldProps extends TextInputProps {
  label: string;
  error?: string | null;
  /** Renders a Show/Hide toggle and masks the value. */
  password?: boolean;
  containerStyle?: ViewStyle;
}

export function BrandTextField({
  label,
  error,
  password = false,
  containerStyle,
  onFocus,
  onBlur,
  ...rest
}: BrandTextFieldProps) {
  const [focused, setFocused] = useState(false);
  const [hidden, setHidden] = useState(password);
  const hasError = !!error;

  return (
    <View style={containerStyle}>
      <Text style={styles.label}>{label}</Text>

      {/*
        The TextInput's parent View must stay static. On the New Architecture,
        restyling a field's parent during the focus event resigns its first
        responder and drops the keyboard — so the focus ring is a sibling
        overlay whose opacity is toggled instead of a border on the wrapper.
      */}
      <View style={styles.inputRow}>
        <View style={[styles.inputWrap, hasError && styles.inputWrapError]}>
          <TextInput
            style={styles.input}
            placeholderTextColor={Colors.ink3}
            secureTextEntry={password && hidden}
            onFocus={(e) => {
              setFocused(true);
              onFocus?.(e);
            }}
            onBlur={(e) => {
              setFocused(false);
              onBlur?.(e);
            }}
            {...rest}
          />

          {password && (
            <Pressable
              hitSlop={{ top: 12, bottom: 12, left: 8, right: 8 }}
              accessibilityRole="button"
              accessibilityLabel={hidden ? 'Show password' : 'Hide password'}
              style={styles.toggleHit}
              onPress={() => setHidden((prev) => !prev)}>
              <Text style={styles.toggle}>{hidden ? 'Show' : 'Hide'}</Text>
            </Pressable>
          )}
        </View>

        <View
          pointerEvents="none"
          style={[styles.focusRing, { opacity: focused && !hasError ? 1 : 0 }]}
        />
      </View>

      {hasError && <Text style={styles.errorText}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  label: {
    fontFamily: Fonts.medium,
    fontSize: FontSizes.xs,
    color: Colors.ink2,
    marginBottom: Spacing[1.5],
  },
  inputRow: {
    position: 'relative',
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    height: 52,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.hairline,
    backgroundColor: Colors.bg,
    paddingHorizontal: Spacing[3],
  },
  inputWrapError: {
    borderColor: Colors.danger,
  },
  input: {
    flex: 1,
    fontFamily: Fonts.regular,
    fontSize: FontSizes.base,
    color: Colors.ink,
    paddingVertical: 0,
  },
  focusRing: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderRadius: Radius.md,
    borderWidth: 1.5,
    borderColor: Colors.brand,
    shadowColor: Colors.brandSolid,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.35,
    shadowRadius: 4,
    elevation: 2,
  },
  // Enlarges the tap target to the ~44pt accessible minimum vertically.
  toggleHit: {
    paddingVertical: 14,
    paddingLeft: 12,
  },
  toggle: {
    fontFamily: Fonts.semibold,
    fontSize: FontSizes.sm,
    color: Colors.brand,
  },
  errorText: {
    fontFamily: Fonts.regular,
    fontSize: FontSizes.xs,
    color: Colors.danger,
    marginTop: Spacing[1.5],
  },
});
