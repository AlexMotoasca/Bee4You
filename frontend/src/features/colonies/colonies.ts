import { useQuery } from '@powersync/react-native';

import { db } from '@/db/powersync';
import { newId, nowIso } from '@/lib/ids';

export type ColonyMode = 'stationary' | 'migratory';
export const COLONY_MODES: readonly ColonyMode[] = ['stationary', 'migratory'];
export type ColonyStatus = 'active' | 'dead' | 'sold' | 'merged';

export type ColonyListRow = { id: string; label: string; number: number | null; status: ColonyStatus };

/** Hives currently placed at an apiary (open placement). */
export function useColoniesAt(apiaryId: string) {
  return useQuery<ColonyListRow>(
    `SELECT c.id, c.label, c.number, c.status
       FROM colony_placements p
       JOIN colonies c ON c.id = p.colony_id
      WHERE p.apiary_id = ? AND p.ended_at IS NULL AND p.deleted_at IS NULL
        AND c.deleted_at IS NULL
      ORDER BY c.number IS NULL, c.number, c.label COLLATE NOCASE`,
    [apiaryId],
  );
}

export type ColonyRow = {
  id: string;
  label: string;
  number: number | null;
  mode: ColonyMode;
  status: ColonyStatus;
  apiary_id: string | null;
  apiary_name: string | null;
};

export function useColony(colonyId: string) {
  const result = useQuery<ColonyRow>(
    `SELECT c.id, c.label, c.number, c.mode, c.status,
            p.apiary_id AS apiary_id, a.name AS apiary_name
       FROM colonies c
       LEFT JOIN colony_placements p
         ON p.colony_id = c.id AND p.ended_at IS NULL AND p.deleted_at IS NULL
       LEFT JOIN apiaries a ON a.id = p.apiary_id
      WHERE c.id = ? AND c.deleted_at IS NULL`,
    [colonyId],
  );
  return { ...result, colony: result.data[0] ?? null };
}

export type HistoryKind = 'placement' | 'treatment' | 'harvest' | 'note';
export type HistoryRow = {
  kind: HistoryKind;
  id: string;
  at: string;
  ended_at: string | null;
  apiary_name: string | null;
  detail: string | null;
};

/**
 * Everything that happened to a hive, newest first. Each entry shows the apiary where IT
 * happened (its own apiary_id), so history stays right after moves.
 * PowerSync timestamps use a space, local ones a "T": normalize before sorting.
 */
export function useColonyHistory(colonyId: string) {
  return useQuery<HistoryRow>(
    `SELECT * FROM (
       SELECT 'placement' AS kind, p.id, p.started_at AS at, p.ended_at, a.name AS apiary_name,
              NULL AS detail
         FROM colony_placements p LEFT JOIN apiaries a ON a.id = p.apiary_id
        WHERE p.colony_id = ?1 AND p.deleted_at IS NULL
       UNION ALL
       SELECT 'treatment', t.id, t.treated_at, NULL, a.name,
              t.product_name || ' · ' || t.amount || ' ' || t.unit
         FROM treatments t LEFT JOIN apiaries a ON a.id = t.apiary_id
        WHERE t.colony_id = ?1 AND t.deleted_at IS NULL
       UNION ALL
       SELECT 'harvest', h.id, h.harvested_at, NULL, a.name, h.quantity || ' ' || h.unit
         FROM harvests h LEFT JOIN apiaries a ON a.id = h.apiary_id
        WHERE h.colony_id = ?1 AND h.deleted_at IS NULL
       UNION ALL
       SELECT 'note', n.id, n.noted_at, NULL, a.name, n.text
         FROM colony_notes n LEFT JOIN apiaries a ON a.id = n.apiary_id
        WHERE n.colony_id = ?1 AND n.deleted_at IS NULL
     ) ORDER BY replace(at, ' ', 'T') DESC`,
    [colonyId],
  );
}

export type NewColony = { label: string; number: number | null; mode: ColonyMode; apiaryId: string };

/** Hive + its first placement, in one local transaction. */
export async function createColony(userId: string, input: NewColony): Promise<string> {
  const colonyId = newId();
  const now = nowIso();
  await db.writeTransaction(async (tx) => {
    await tx.execute(
      `INSERT INTO colonies (id, owner_id, label, number, mode, status, created_at, updated_at,
                             client_updated_at)
       VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)`,
      [colonyId, userId, input.label.trim(), input.number, input.mode, now, now, now],
    );
    await tx.execute(
      `INSERT INTO colony_placements (id, owner_id, colony_id, apiary_id, started_at, created_at,
                                      updated_at, client_updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [newId(), userId, colonyId, input.apiaryId, now, now, now, now],
    );
  });
  return colonyId;
}

/**
 * A move = close the open placement + open a new one, in one transaction
 * (FrontendArchitect.md §4.2). The server sorts out moves made offline on two phones.
 */
export async function moveColony(userId: string, colonyId: string, toApiaryId: string): Promise<void> {
  const now = nowIso();
  await db.writeTransaction(async (tx) => {
    await tx.execute(
      `UPDATE colony_placements SET ended_at = ?, updated_at = ?, client_updated_at = ?
        WHERE colony_id = ? AND ended_at IS NULL AND deleted_at IS NULL`,
      [now, now, now, colonyId],
    );
    await tx.execute(
      `INSERT INTO colony_placements (id, owner_id, colony_id, apiary_id, started_at, created_at,
                                      updated_at, client_updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      [newId(), userId, colonyId, toApiaryId, now, now, now, now],
    );
  });
}

/** Parse the optional hive number field: '' -> null, '12' -> 12, invalid -> undefined. */
export function parseHiveNumber(raw: string): number | null | undefined {
  const value = raw.trim();
  if (!value) return null;
  if (!/^\d{1,6}$/.test(value)) return undefined;
  return Number.parseInt(value, 10);
}
