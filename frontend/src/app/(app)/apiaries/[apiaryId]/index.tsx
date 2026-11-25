import { router, Stack, useLocalSearchParams } from 'expo-router';

import { BigButton, ListRow, Loading, Muted, Screen, SectionTitle } from '@/components/ui';
import { useApiary } from '@/features/apiaries/apiaries';
import { useColoniesAt } from '@/features/colonies/colonies';
import { useI18n } from '@/i18n';

/** One apiary: the hives placed here now. */
export default function ApiaryScreen() {
  const { t } = useI18n();
  const { apiaryId } = useLocalSearchParams<{ apiaryId: string }>();
  const { apiary, isLoading } = useApiary(apiaryId);
  const { data: colonies } = useColoniesAt(apiaryId);

  if (isLoading) return <Loading label={t.common.loading} />;

  return (
    <Screen>
      <Stack.Screen options={{ title: apiary?.name ?? '' }} />
      {apiary ? <Muted>{t.apiaries.kinds[apiary.kind] ?? apiary.kind}</Muted> : null}
      {apiary?.notes ? <Muted>{apiary.notes}</Muted> : null}

      <SectionTitle>{t.colonies.hivesHere}</SectionTitle>
      {colonies.length === 0 ? (
        <Muted>{t.colonies.empty}</Muted>
      ) : (
        colonies.map((c) => (
          <ListRow
            key={c.id}
            title={c.label}
            subtitle={c.status === 'active' ? null : t.colonies.statuses[c.status]}
            right={c.number !== null ? `#${c.number}` : null}
            onPress={() => router.push({ pathname: '/colonies/[colonyId]', params: { colonyId: c.id } })}
          />
        ))
      )}

      <BigButton
        label={`+ ${t.colonies.add}`}
        onPress={() => router.push({ pathname: '/colonies/new', params: { apiaryId } })}
      />
    </Screen>
  );
}
