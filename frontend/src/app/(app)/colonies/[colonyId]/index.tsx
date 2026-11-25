import { router, Stack, useLocalSearchParams } from 'expo-router';

import { BigButton, ListRow, Loading, Muted, Screen, SectionTitle } from '@/components/ui';
import { type HistoryRow, useColony, useColonyHistory } from '@/features/colonies/colonies';
import { format, formatDay, type Locale, useI18n } from '@/i18n';
import type { Strings } from '@/i18n/en';
import { parseDbDate } from '@/lib/ids';

/** Hive profile + history. History survives moves: each entry keeps its own apiary. */
export default function ColonyScreen() {
  const { t, locale } = useI18n();
  const { colonyId } = useLocalSearchParams<{ colonyId: string }>();
  const { colony, isLoading } = useColony(colonyId);
  const { data: history } = useColonyHistory(colonyId);

  if (isLoading) return <Loading label={t.common.loading} />;
  if (!colony) return <Muted>{t.common.error}</Muted>;

  const facts = [
    colony.number !== null ? `#${colony.number}` : null,
    t.colonies.modes[colony.mode] ?? colony.mode,
    t.colonies.statuses[colony.status] ?? colony.status,
  ].filter(Boolean);

  return (
    <Screen>
      <Stack.Screen options={{ title: colony.label }} />
      <Muted>{facts.join(' · ')}</Muted>
      <Muted>
        {colony.apiary_name
          ? format(t.colonies.currentlyAt, { apiary: colony.apiary_name })
          : t.colonies.notPlaced}
      </Muted>

      <BigButton
        variant="secondary"
        label={t.colonies.move}
        onPress={() => router.push({ pathname: '/colonies/[colonyId]/move', params: { colonyId } })}
      />

      <SectionTitle>{t.colonies.history}</SectionTitle>
      {history.length === 0 ? (
        <Muted>{t.colonies.historyEmpty}</Muted>
      ) : (
        history.map((h) => <HistoryItem key={`${h.kind}:${h.id}`} row={h} t={t} locale={locale} />)
      )}
    </Screen>
  );
}

function HistoryItem({ row, t, locale }: { row: HistoryRow; t: Strings; locale: Locale }) {
  const day = (value: string | null) => formatDay(parseDbDate(value), locale, t.common.today);
  if (row.kind === 'placement') {
    const when = row.ended_at
      ? format(t.history.placedRange, { from: day(row.at), to: day(row.ended_at) })
      : format(t.history.placedSince, { from: day(row.at) });
    return (
      <ListRow title={format(t.history.placedAt, { apiary: row.apiary_name ?? '—' })} subtitle={when} />
    );
  }
  const title =
    row.kind === 'treatment' ? t.history.treatment : row.kind === 'harvest' ? t.history.harvest : t.history.note;
  const subtitle = [day(row.at), row.apiary_name, row.detail].filter(Boolean).join(' · ');
  return <ListRow title={title} subtitle={subtitle} />;
}
