import { Stack } from 'expo-router';

import { useUserId } from '@/features/auth/AuthProvider';
import { useProfileLocaleSync } from '@/features/profile/profile';
import { colors, font } from '@/theme/tokens';

/** Signed-in area. Every screen here reads and writes the local database only. */
export default function AppLayout() {
  useProfileLocaleSync(useUserId());
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: colors.background },
        headerTintColor: colors.text,
        headerTitleStyle: { fontSize: font.large, fontWeight: '700' },
        contentStyle: { backgroundColor: colors.background },
      }}
    />
  );
}
