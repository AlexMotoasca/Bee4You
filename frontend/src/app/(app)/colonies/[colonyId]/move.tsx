import * as Haptics from 'expo-haptics';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { ErrorText, ListRow, Loading, Muted, Screen, SectionTitle } from '@/components/ui';
import { useApiaries } from '@/features/apiaries/apiaries';
import { useUserId } from '@/features/auth/AuthProvider';
import { moveColony, useColony } from '@/features/colonies/colonies';
import { format, useI18n } from '@/i18n';

/** Move a hive to another apiary, dated now. The old site stays in its history. */
export default function MoveColonyScreen() {
  const { t } = useI18n();
  const userId = useUserId();
  const { colonyId } = useLocalSearchParams<{ colonyId: string }>();
  const { colony, isLoading } = useColony(colonyId);
  const { data: apiaries } = useApiaries();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (isLoading || !colony) return <Loading label={t.common.loading} />;

  const targets = apiaries.filter((a) => a.id !== colony.apiary_id);

  async function moveTo(apiaryId: string) {
    if (busy) return;
    setBusy(true);
    try {
      await moveColony(userId, colonyId, apiaryId);
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      router.back();
    } catch (e) {
      setError(e instanceof Error ? e.message : t.common.error);
      setBusy(false);
    }
  }

  return (
    <Screen>
      <Stack.Screen options={{ title: format(t.move.title, { hive: colony.label }) }} />
      {colony.apiary_name ? (
        <Muted>{format(t.colonies.currentlyAt, { apiary: colony.apiary_name })}</Muted>
      ) : null}
      <SectionTitle>{t.move.pick}</SectionTitle>
      {targets.length === 0 ? (
        <Muted>{t.move.noOther}</Muted>
      ) : (
        targets.map((a) => <ListRow key={a.id} title={a.name} onPress={() => moveTo(a.id)} />)
      )}
      {error ? <ErrorText>{error}</ErrorText> : null}
    </Screen>
  );
}
