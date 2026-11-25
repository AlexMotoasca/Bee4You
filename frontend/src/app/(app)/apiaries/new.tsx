import * as Haptics from 'expo-haptics';
import { router, Stack } from 'expo-router';
import { useState } from 'react';

import { BigButton, Choice, ErrorText, Field, Screen } from '@/components/ui';
import { APIARY_KINDS, type ApiaryKind, createApiary } from '@/features/apiaries/apiaries';
import { useUserId } from '@/features/auth/AuthProvider';
import { useI18n } from '@/i18n';

export default function NewApiaryScreen() {
  const { t } = useI18n();
  const userId = useUserId();
  const [name, setName] = useState('');
  const [kind, setKind] = useState<ApiaryKind>('permanent');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    if (!name.trim()) {
      setError(t.apiaries.nameRequired);
      return;
    }
    setBusy(true);
    try {
      const id = await createApiary(userId, { name, kind, notes: notes || null });
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      router.replace({ pathname: '/apiaries/[apiaryId]', params: { apiaryId: id } });
    } catch (e) {
      setError(e instanceof Error ? e.message : t.common.error);
      setBusy(false);
    }
  }

  return (
    <Screen>
      <Stack.Screen options={{ title: t.apiaries.newTitle }} />
      <Field
        label={t.apiaries.name}
        placeholder={t.apiaries.namePlaceholder}
        value={name}
        onChangeText={setName}
        maxLength={120}
        autoFocus
        error={error}
      />
      <Choice
        label={t.apiaries.kind}
        value={kind}
        onChange={setKind}
        options={APIARY_KINDS.map((k) => ({ value: k, label: t.apiaries.kinds[k] }))}
      />
      <Field
        label={`${t.apiaries.notes} (${t.common.optional})`}
        value={notes}
        onChangeText={setNotes}
        maxLength={2000}
        multiline
      />
      {error && name.trim() ? <ErrorText>{error}</ErrorText> : null}
      <BigButton label={t.common.save} onPress={save} busy={busy} />
    </Screen>
  );
}
