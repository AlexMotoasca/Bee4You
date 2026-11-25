import { useQuery } from '@powersync/react-native';

import { db } from '@/db/powersync';
import { newId, nowIso } from '@/lib/ids';

export type ApiaryKind = 'permanent' | 'temporary';
export const APIARY_KINDS: readonly ApiaryKind[] = ['permanent', 'temporary'];

export type ApiaryRow = {
  id: string;
  name: string;
  kind: ApiaryKind;
  notes: string | null;
  colony_count: number;
};

/** Hives currently at an apiary = open placements of non-deleted colonies. */
const COLONY_COUNT = `(SELECT count(*) FROM colony_placements p
   JOIN colonies c ON c.id = p.colony_id
  WHERE p.apiary_id = a.id AND p.ended_at IS NULL AND p.deleted_at IS NULL
    AND c.deleted_at IS NULL)`;

export function useApiaries() {
  return useQuery<ApiaryRow>(
    `SELECT a.id, a.name, a.kind, a.notes, ${COLONY_COUNT} AS colony_count
       FROM apiaries a
      WHERE a.deleted_at IS NULL
      ORDER BY a.name COLLATE NOCASE`,
  );
}

export function useApiary(apiaryId: string) {
  const result = useQuery<ApiaryRow>(
    `SELECT a.id, a.name, a.kind, a.notes, ${COLONY_COUNT} AS colony_count
       FROM apiaries a WHERE a.id = ? AND a.deleted_at IS NULL`,
    [apiaryId],
  );
  return { ...result, apiary: result.data[0] ?? null };
}

export type NewApiary = { name: string; kind: ApiaryKind; notes: string | null };

/** Writes locally; the upload connector sends it to the server when online. */
export async function createApiary(userId: string, input: NewApiary): Promise<string> {
  const id = newId();
  const now = nowIso();
  await db.execute(
    `INSERT INTO apiaries (id, owner_id, name, kind, notes, created_at, updated_at, client_updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    [id, userId, input.name.trim(), input.kind, input.notes?.trim() || null, now, now, now],
  );
  return id;
}
