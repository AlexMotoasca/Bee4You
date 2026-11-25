import { useQuery } from '@powersync/react-native';
import { useEffect, useRef } from 'react';

import { db } from '@/db/powersync';
import { type Locale, toLocale, useI18n } from '@/i18n';
import { nowIso } from '@/lib/ids';

type ProfileRow = { id: string; locale: string | null; display_name: string | null };

export function useProfile(userId: string) {
  const result = useQuery<ProfileRow>(
    'SELECT id, locale, display_name FROM profiles WHERE id = ?',
    [userId],
  );
  return result.data[0] ?? null;
}

/**
 * The profile's locale (synced across devices) drives the UI and voice language.
 * Adopt it once when the profile first arrives; after that the Settings screen changes both.
 */
export function useProfileLocaleSync(userId: string) {
  const profile = useProfile(userId);
  const { setLocale } = useI18n();
  const adopted = useRef(false);
  useEffect(() => {
    if (profile?.locale && !adopted.current) {
      adopted.current = true;
      setLocale(toLocale(profile.locale));
    }
  }, [profile?.locale, setLocale]);
}

/** Change language: UI now, profile (and so voice + other devices) via sync. */
export async function saveLocale(userId: string, locale: Locale): Promise<void> {
  const now = nowIso();
  await db.execute(
    'UPDATE profiles SET locale = ?, updated_at = ?, client_updated_at = ? WHERE id = ?',
    [locale, now, now, userId],
  );
}
