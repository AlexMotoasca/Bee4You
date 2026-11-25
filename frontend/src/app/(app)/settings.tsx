import { Stack } from 'expo-router';
import { Alert } from 'react-native';

import { SyncBadge } from '@/components/SyncBadge';
import { BigButton, Choice, ListRow, Muted, Screen, SectionTitle } from '@/components/ui';
import { useAuth, useUserId } from '@/features/auth/AuthProvider';
import { saveLocale } from '@/features/profile/profile';
import { useRejections, useSyncSummary } from '@/features/sync/sync';
import { format, formatDay, type Locale, LOCALES, useI18n } from '@/i18n';
import { parseDbDate } from '@/lib/ids';

const LANGUAGE_NAMES: Record<Locale, string> = { 'ro-RO': 'Română', 'en-US': 'English' };

export default function SettingsScreen() {
  const { t, locale, setLocale } = useI18n();
  const userId = useUserId();
  const { session, signOut, pendingUploads } = useAuth();
  const { lastSyncedAt } = useSyncSummary();
  const { data: rejections } = useRejections();

  function changeLanguage(next: Locale) {
    setLocale(next);
    void saveLocale(userId, next); // syncs to other devices and the voice assistant
  }

  async function confirmSignOut() {
    const pending = await pendingUploads();
    if (pending === 0) return signOut();
    Alert.alert(t.settings.signOut, format(t.settings.signOutUnsynced, { n: pending }), [
      { text: t.common.cancel, style: 'cancel' },
      { text: t.settings.signOutAnyway, style: 'destructive', onPress: () => void signOut() },
    ]);
  }

  return (
    <Screen>
      <Stack.Screen options={{ title: t.settings.title }} />

      <Choice
        label={t.settings.language}
        value={locale}
        onChange={changeLanguage}
        options={LOCALES.map((l) => ({ value: l, label: LANGUAGE_NAMES[l] }))}
      />

      <SectionTitle>{t.settings.sync}</SectionTitle>
      <SyncBadge />
      {lastSyncedAt ? (
        <Muted>
          {format(t.settings.lastSynced, {
            when: `${formatDay(lastSyncedAt, locale, t.common.today)} ${lastSyncedAt.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })}`,
          })}
        </Muted>
      ) : null}
      {rejections.length > 0 ? (
        <>
          <SectionTitle>{t.settings.rejected}</SectionTitle>
          {rejections.map((r) => (
            <ListRow
              key={r.id}
              title={`${r.table_name} · ${r.op}`}
              subtitle={`${formatDay(parseDbDate(r.created_at), locale, t.common.today)} · ${r.error}`}
            />
          ))}
        </>
      ) : null}

      <SectionTitle>{t.settings.account}</SectionTitle>
      <Muted>{session?.user.email ?? ''}</Muted>
      <BigButton variant="danger" label={t.settings.signOut} onPress={confirmSignOut} />
    </Screen>
  );
}
