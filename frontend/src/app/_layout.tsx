import { PowerSyncContext } from '@powersync/react-native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { Loading } from '@/components/ui';
import { db } from '@/db/powersync';
import { AuthProvider, useAuth } from '@/features/auth/AuthProvider';
import { I18nProvider, useI18n } from '@/i18n';

export default function RootLayout() {
  return (
    <PowerSyncContext.Provider value={db}>
      <I18nProvider>
        <AuthProvider>
          <StatusBar style="dark" />
          <RootStack />
        </AuthProvider>
      </I18nProvider>
    </PowerSyncContext.Provider>
  );
}

function RootStack() {
  const { session, loading } = useAuth();
  const { t } = useI18n();
  if (loading) return <Loading label={t.common.loading} />;
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Protected guard={!!session}>
        <Stack.Screen name="(app)" />
      </Stack.Protected>
      <Stack.Protected guard={!session}>
        <Stack.Screen name="sign-in" />
      </Stack.Protected>
    </Stack>
  );
}
