import {
  type AbstractPowerSyncDatabase,
  type PowerSyncBackendConnector,
  type PowerSyncCredentials,
  UpdateType,
} from '@powersync/react-native';

import { apiRequest } from '@/lib/api';
import { env } from '@/lib/env';
import { newId, nowIso } from '@/lib/ids';
import { getAccessToken, supabase } from '@/lib/supabase';

import { decideUpload, type UploadOp } from './uploadPlan';

const BATCH_SIZE = 500; // backend accepts up to 1000 ops per request

/**
 * Downloads: PowerSync authenticates with the Supabase access token.
 * Uploads: queued local changes go to POST /v1/sync/upload (never straight to Supabase).
 */
export class BackendConnector implements PowerSyncBackendConnector {
  async fetchCredentials(): Promise<PowerSyncCredentials | null> {
    const { data } = await supabase.auth.getSession();
    const session = data.session;
    if (!session) return null;
    return {
      endpoint: env.powersyncUrl,
      token: session.access_token,
      expiresAt: session.expires_at ? new Date(session.expires_at * 1000) : undefined,
    };
  }

  async uploadData(database: AbstractPowerSyncDatabase): Promise<void> {
    const batch = await database.getCrudBatch(BATCH_SIZE);
    if (!batch) return;

    const ops: UploadOp[] = batch.crud.map((entry) => ({
      op: entry.op === UpdateType.PUT ? 'PUT' : entry.op === UpdateType.PATCH ? 'PATCH' : 'DELETE',
      table: entry.table,
      id: entry.id,
      ...(entry.op === UpdateType.DELETE ? {} : { data: entry.opData ?? {} }),
    }));

    const token = await getAccessToken();
    if (!token) throw new Error('Not signed in: uploads wait until the user signs in again');

    // Network errors / timeouts throw here -> PowerSync retries the batch later.
    const res = await apiRequest('/v1/sync/upload', {
      method: 'POST',
      token,
      body: { ops },
      timeoutMs: 60_000,
    });
    const text = await res.text();
    let body: unknown = null;
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }

    const decision = decideUpload(ops, res.status, body, text);
    if (decision.action === 'retry') {
      if (decision.refreshAuth) await supabase.auth.refreshSession();
      throw new Error(`Upload will be retried: ${decision.reason}`);
    }

    for (const { op, error } of decision.rejections) {
      await database.execute(
        `INSERT INTO upload_rejections (id, table_name, record_id, op, data, error, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
        [newId(), op.table, op.id, op.op, JSON.stringify(op.data ?? null), error, nowIso()],
      );
    }
    await batch.complete();
  }
}

export const connector = new BackendConnector();
