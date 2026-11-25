import { Pressable, StyleSheet, Text } from 'react-native';

import { useSyncSummary } from '@/features/sync/sync';
import { format, useI18n } from '@/i18n';
import { colors, font, radius, space, touch } from '@/theme/tokens';

/** Always-visible sync state: saved on the phone is not the same as uploaded. */
export function SyncBadge({ onPress }: { onPress?: () => void }) {
  const { t } = useI18n();
  const { state, pendingCount, rejectedCount } = useSyncSummary();

  let text: string;
  let color: string = colors.success;
  if (rejectedCount > 0) {
    text = `⚠ ${format(t.sync.attention, { n: rejectedCount })}`;
    color = colors.danger;
  } else if (state === 'synced') {
    text = `✓ ${t.sync.synced}`;
  } else if (state === 'pending') {
    text = `↑ ${format(t.sync.pending, { n: pendingCount })}`;
    color = colors.warning;
  } else if (state === 'offline') {
    text = pendingCount > 0 ? `↑ ${format(t.sync.pending, { n: pendingCount })} · offline` : t.sync.offline;
    color = colors.warning;
  } else if (state === 'connecting') {
    text = t.sync.connecting;
    color = colors.textMuted;
  } else {
    text = t.sync.neverSynced;
    color = colors.textMuted;
  }

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={text}
      onPress={onPress}
      style={[styles.badge, { borderColor: color }]}
    >
      <Text style={[styles.text, { color }]}>{text}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  badge: {
    minHeight: touch.min - space.md,
    justifyContent: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: space.md,
    borderRadius: radius.pill,
    borderWidth: 2,
    backgroundColor: colors.surface,
  },
  text: { fontSize: font.small, fontWeight: '700' },
});
