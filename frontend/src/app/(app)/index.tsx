import { router, Stack } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { SyncBadge } from '@/components/SyncBadge';
import { BigButton, ListRow, Loading, Muted, Screen } from '@/components/ui';
import { useApiaries } from '@/features/apiaries/apiaries';
import { useSyncSummary } from '@/features/sync/sync';
import { format, useI18n } from '@/i18n';
import { colors, font, space, touch } from '@/theme/tokens';

/** Home: the apiary list. Works fully offline (FrontendArchitect.md §6). */
export default function ApiariesScreen() {
  const { t } = useI18n();
  const { data: apiaries, isLoading } = useApiaries();
  const { hasSynced } = useSyncSummary();

  return (
    <Screen>
      <Stack.Screen
        options={{
          title: t.apiaries.title,
          headerRight: () => (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t.settings.title}
              onPress={() => router.push('/settings')}
              style={styles.headerButton}
            >
              <Text style={styles.headerIcon}>⚙</Text>
            </Pressable>
          ),
        }}
      />
      <SyncBadge onPress={() => router.push('/settings')} />

      {isLoading || (!hasSynced && apiaries.length === 0) ? (
        <View style={styles.loadingBox}>
          <Loading label={t.apiaries.downloading} />
        </View>
      ) : apiaries.length === 0 ? (
        <Muted>{t.apiaries.empty}</Muted>
      ) : (
        apiaries.map((a) => (
          <ListRow
            key={a.id}
            title={a.name}
            subtitle={t.apiaries.kinds[a.kind] ?? a.kind}
            right={
              a.colony_count === 1 ? t.apiaries.hivesOne : format(t.apiaries.hives, { n: a.colony_count })
            }
            onPress={() => router.push({ pathname: '/apiaries/[apiaryId]', params: { apiaryId: a.id } })}
          />
        ))
      )}

      <BigButton label={`+ ${t.apiaries.add}`} onPress={() => router.push('/apiaries/new')} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  headerButton: { minWidth: touch.min, minHeight: touch.min, alignItems: 'center', justifyContent: 'center' },
  headerIcon: { fontSize: font.title, color: colors.text },
  loadingBox: { minHeight: 160, gap: space.md },
});
