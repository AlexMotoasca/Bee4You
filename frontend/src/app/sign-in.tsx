import { useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet, Text } from 'react-native';

import { BigButton, ErrorText, Field, Muted, Screen } from '@/components/ui';
import { useAuth } from '@/features/auth/AuthProvider';
import { useI18n } from '@/i18n';
import { colors, font, space } from '@/theme/tokens';

export default function SignInScreen() {
  const { t } = useI18n();
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<'signIn' | 'signUp'>('signIn');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  async function submit() {
    setError(null);
    setInfo(null);
    if (!email.includes('@') || password.length < 6) {
      setError(t.auth.missingFields);
      return;
    }
    setBusy(true);
    try {
      const failure =
        mode === 'signIn' ? await signIn(email.trim(), password) : await signUp(email.trim(), password);
      if (failure) setError(failure);
      else if (mode === 'signUp') setInfo(t.auth.checkEmail);
      // On success the root layout switches to the app automatically.
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen>
        <Text style={styles.brand}>🐝 {t.appName}</Text>
        <Muted>{t.auth.title}</Muted>
        <Field
          label={t.auth.email}
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          textContentType="emailAddress"
        />
        <Field
          label={t.auth.password}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete={mode === 'signIn' ? 'current-password' : 'new-password'}
          textContentType={mode === 'signIn' ? 'password' : 'newPassword'}
          onSubmitEditing={submit}
        />
        {error ? <ErrorText>{error}</ErrorText> : null}
        {info ? <Muted>{info}</Muted> : null}
        <BigButton label={mode === 'signIn' ? t.auth.signIn : t.auth.signUp} onPress={submit} busy={busy} />
        <BigButton
          variant="secondary"
          label={mode === 'signIn' ? t.auth.switchToSignUp : t.auth.switchToSignIn}
          onPress={() => setMode(mode === 'signIn' ? 'signUp' : 'signIn')}
        />
      </Screen>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  brand: { fontSize: font.huge, fontWeight: '800', color: colors.text, marginTop: space.xxl },
});
