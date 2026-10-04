import { StatusBar } from 'expo-status-bar';
import { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { BrandButton } from '@/components/brand-button';
import { BrandLogo } from '@/components/brand-logo';
import { BrandTextField } from '@/components/brand-text-field';
import { MicrosoftTile } from '@/components/microsoft-tile';
import { Colors, Fonts, FontSizes, Radius, Shadows, Spacing } from '@/constants/theme';

/**
 * Sign-in screen — presentation only.
 *
 * The fields are controlled so the UI behaves (typing, the password reveal,
 * focus rings), but nothing is submitted anywhere: there is no auth client,
 * no API base and no session storage in this app yet. `onPress` is
 * deliberately a no-op rather than a stub that pretends to sign in, so the
 * absence is visible in the code rather than hidden behind a fake delay.
 *
 * Layout mirrors the web login in `frontend/src/pages/auth/LoginPage.tsx`.
 */
export default function LoginScreen() {
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  return (
    <View style={styles.screen}>
      <StatusBar style="light" />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          contentContainerStyle={[
            styles.scrollContent,
            { paddingTop: insets.top + Spacing[8], paddingBottom: insets.bottom + Spacing[6] },
          ]}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}>
          <View style={styles.card}>
            <BrandLogo size={64} style={styles.logo} />

            <Text style={styles.title}>BrainVar Trajectory Explorer</Text>

            <BrandTextField
              label="Email address"
              placeholder="you@example.com"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              autoComplete="email"
              textContentType="emailAddress"
              returnKeyType="next"
              containerStyle={styles.field}
            />

            <BrandTextField
              label="Password"
              placeholder="Enter your password"
              value={password}
              onChangeText={setPassword}
              password
              autoCapitalize="none"
              autoComplete="password"
              textContentType="password"
              returnKeyType="go"
              containerStyle={styles.field}
            />

            <BrandButton title="Sign in" onPress={() => {}} style={styles.submit} />

            <View style={styles.divider} role="separator">
              <View style={styles.dividerRule} />
              <Text style={styles.dividerText}>or</Text>
              <View style={styles.dividerRule} />
            </View>

            {/* Placeholder for institutional SSO. Research institutions
                commonly issue Microsoft Entra accounts, so this is where that
                flow would start — inert until a tenant is registered, exactly
                as on the web. */}
            <BrandButton
              title="Sign in with your Microsoft account"
              variant="secondary"
              icon={<MicrosoftTile />}
              onPress={() => {}}
            />

            <Text style={styles.note}>
              Accounts are created by an administrator. There is no public sign-up — the
              dataset is available to named researchers only.
            </Text>
          </View>

          <Text style={styles.footer}>
            BrainVar · developing human cortex · 176 RNA-seq samples
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.bg,
  },
  flex: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: Spacing[5],
  },
  card: {
    width: '100%',
    maxWidth: 400,
    alignSelf: 'center',
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.hairline,
    borderRadius: Radius.xl,
    padding: Spacing[6],
    ...Shadows.lg,
  },
  logo: {
    marginBottom: Spacing[6],
  },
  title: {
    fontFamily: Fonts.bold,
    fontSize: FontSizes.xl,
    color: Colors.ink,
    textAlign: 'center',
    letterSpacing: -0.2,
    marginBottom: Spacing[8],
  },
  field: {
    marginBottom: Spacing[5],
  },
  submit: {
    marginTop: Spacing[1],
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[3],
    marginVertical: Spacing[5],
  },
  dividerRule: {
    flex: 1,
    height: 1,
    backgroundColor: Colors.hairline,
  },
  dividerText: {
    fontFamily: Fonts.regular,
    fontSize: FontSizes.xs,
    color: Colors.ink3,
  },
  note: {
    fontFamily: Fonts.regular,
    fontSize: FontSizes.xs,
    lineHeight: 18,
    color: Colors.ink3,
    textAlign: 'center',
    marginTop: Spacing[6],
  },
  footer: {
    fontFamily: Fonts.regular,
    fontSize: FontSizes.xs,
    color: Colors.ink3,
    textAlign: 'center',
    marginTop: Spacing[8],
  },
});
