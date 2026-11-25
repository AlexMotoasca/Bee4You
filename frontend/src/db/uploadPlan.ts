/**
 * Pure decision logic for the upload connector (FrontendArchitect.md §4.4), kept separate
 * so it can be unit-tested without PowerSync or the network.
 */

export type UploadOp = {
  op: 'PUT' | 'PATCH' | 'DELETE';
  table: string;
  id: string;
  data?: Record<string, unknown>;
};

export type OpResult = {
  id: string;
  table: string;
  status: 'applied' | 'conflict' | 'rejected';
  error?: string | null;
};

export type Rejection = { op: UploadOp; error: string };

export type UploadDecision =
  /** Throw so PowerSync retries the same batch later (it's idempotent on the server). */
  | { action: 'retry'; refreshAuth: boolean; reason: string }
  /** Remove the batch from the queue; keep any rejections for the Sync screen. */
  | { action: 'complete'; rejections: Rejection[] };

export function decideUpload(
  ops: UploadOp[],
  status: number,
  body: unknown,
  rawText: string,
): UploadDecision {
  if (status === 401) return { action: 'retry', refreshAuth: true, reason: 'login expired' };
  if (status >= 500 || status === 408 || status === 429) {
    return { action: 'retry', refreshAuth: false, reason: `server ${status}` };
  }
  if (status >= 200 && status < 300) {
    const results = (body as { results?: OpResult[] } | null)?.results ?? [];
    const byKey = new Map(ops.map((o) => [`${o.table}:${o.id}`, o]));
    const rejections: Rejection[] = [];
    for (const r of results) {
      if (r.status !== 'rejected') continue;
      const op = byKey.get(`${r.table}:${r.id}`) ?? { op: 'PUT', table: r.table, id: r.id };
      rejections.push({ op, error: r.error ?? 'rejected' });
    }
    return { action: 'complete', rejections };
  }
  // Any other 4xx: the request itself is wrong (a bug). Never jam the queue: keep it visible.
  const error = `HTTP ${status}: ${rawText.slice(0, 300)}`;
  return { action: 'complete', rejections: ops.map((op) => ({ op, error })) };
}
