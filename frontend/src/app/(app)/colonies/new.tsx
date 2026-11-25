import * as Haptics from 'expo-haptics';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { BigButton, Choice, ErrorText, Field, Muted, Screen } from '@/components/ui';
import { useApiary } from '@/features/apiaries/apiaries';
import { useUserId } from '@/features/auth/AuthProvider';
import {
  COLONY_MODES,
  type ColonyMode,
  createColony,
  parseHiveNumber,
} from '@/features/colonies/colonies';
import { format, useI18n } from '@/i18n';

/** New hive, placed at the apiary it was created from (contextual entry). */
export default function NewColonyScreen() {
  const { t } = useI18n();
  const userId = useUserId();
  const { apiaryId } = useLocalSearchParams<{ apiaryId: string }>();
  const { apiary } = useApiary(apiaryId);
  const [label, setLabel] = useState('');
  const [numberText, setNumberText] = useState('');
  const [mode, setMode] = useState<ColonyMode>('stationary');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    const number = parseHiveNumber(numberText);
    if (!label.trim()) return setError(t.colonies.labelRequired);
    if (number === undefined) return setError(t.colonies.numberInvalid);
    setBusy(true);
    try {
      const id = await createColony(userId, { label, number, mode, apiaryId });
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      router.replace({ pathname: '/colonies/[colonyId]', params: { colonyId: id } });
    } catch (e) {
      setError(e instanceof Error ? e.message : t.common.error);
      setBusy(false);
    }
  }

  return (
    <Screen>
      <Stack.Screen options={{ title: t.colonies.newTitle }} />
      {apiary ? <Muted>{format(t.colonies.currentlyAt, { apiary: apiary.name })}</Muted> : null}
      <Field
        label={t.colonies.label}
        placeholder={t.colonies.labelPlaceholder}
        value={label}
        onChangeText={setLabel}
        maxLength={60}
        autoFocus
      />
      <Field
        label={`${t.colonies.number} (${t.common.optional})`}
        help={t.colonies.numberHelp}
        value={numberText}
        onChangeText={setNumberText}
        keyboardType="number-pad"
        maxLength={6}
      />
      <Choice
        label={t.colonies.mode}
        value={mode}
        onChange={setMode}
        options={COLONY_MODES.map((m) => ({ value: m, label: t.colonies.modes[m] }))}
      />
      {error ? <ErrorText>{error}</ErrorText> : null}
      <BigButton label={t.common.save} onPress={save} busy={busy} />
    </Screen>
  );
}
