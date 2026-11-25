import { useQuery, useStatus } from '@powersync/react-native';
import { useEffect, useState } from 'react';

import { db } from '@/db/powersync';

export type SyncState = 'synced' | 'pending' | 'offline' | 'connecting' | 'never';

/** Pending local changes, via PowerSync's documented queue stats (refreshed every 2 s). */
function usePendingUploads(refreshKey: unknown): number {
  const [count, setCount] = useState(0);
  useEffect(() => {
    let alive = true;
    const read = () =>
      db
        .getUploadQueueStats()
        .then((stats) => alive && setCount(stats.count))
        .catch(() => undefined);
    void read();
    const timer = setInterval(read, 2000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [refreshKey]);
  return count;
}

/** Everything the sync badge and Settings need, from local data only. */
export function useSyncSummary() {
  const status = useStatus();
  const pendingCount = usePendingUploads(status.lastSyncedAt?.getTime());
  const rejected = useQuery<{ n: number }>('SELECT count(*) AS n FROM upload_rejections');
  const rejectedCount = rejected.data[0]?.n ?? 0;

  let state: SyncState;
  if (pendingCount > 0) state = status.connected ? 'pending' : 'offline';
  else if (status.connected) state = status.hasSynced ? 'synced' : 'connecting';
  else if (status.connecting) state = 'connecting';
  else state = status.hasSynced ? 'offline' : 'never';

  return {
    state,
    pendingCount,
    rejectedCount,
    hasSynced: status.hasSynced ?? false,
    lastSyncedAt: status.lastSyncedAt ?? null,
  };
}

export type RejectionRow = {
  id: string;
  table_name: string;
  op: string;
  error: string;
  created_at: string;
};

export function useRejections() {
  return useQuery<RejectionRow>(
    'SELECT id, table_name, op, error, created_at FROM upload_rejections ORDER BY created_at DESC',
  );
}
