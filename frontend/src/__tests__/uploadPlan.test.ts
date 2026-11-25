import { decideUpload, type UploadOp } from '@/db/uploadPlan';

const ops: UploadOp[] = [
  { op: 'PUT', table: 'apiaries', id: 'a1', data: { name: 'Pădure' } },
  { op: 'PUT', table: 'colonies', id: 'c1', data: { label: '' } },
  { op: 'DELETE', table: 'harvests', id: 'h1' },
];

describe('decideUpload (FrontendArchitect.md §4.4)', () => {
  it('completes when everything is applied', () => {
    const body = { results: ops.map((o) => ({ id: o.id, table: o.table, status: 'applied' })) };
    expect(decideUpload(ops, 200, body, '')).toEqual({ action: 'complete', rejections: [] });
  });

  it('completes and keeps rejected ops for the Sync screen', () => {
    const body = {
      results: [
        { id: 'a1', table: 'apiaries', status: 'applied' },
        { id: 'c1', table: 'colonies', status: 'rejected', error: 'label: too short' },
        { id: 'h1', table: 'harvests', status: 'conflict' },
      ],
    };
    const decision = decideUpload(ops, 200, body, '');
    expect(decision.action).toBe('complete');
    if (decision.action !== 'complete') throw new Error('unreachable');
    expect(decision.rejections).toEqual([{ op: ops[1], error: 'label: too short' }]);
  });

  it('retries with a token refresh on 401', () => {
    expect(decideUpload(ops, 401, null, '')).toMatchObject({ action: 'retry', refreshAuth: true });
  });

  it.each([500, 502, 503, 408, 429])('retries on %i', (status) => {
    expect(decideUpload(ops, status, null, '')).toMatchObject({ action: 'retry', refreshAuth: false });
  });

  it('never jams the queue on other 4xx: completes and keeps every op', () => {
    const decision = decideUpload(ops, 422, null, '{"detail":"bad"}');
    expect(decision.action).toBe('complete');
    if (decision.action !== 'complete') throw new Error('unreachable');
    expect(decision.rejections).toHaveLength(3);
    expect(decision.rejections[0]?.error).toContain('HTTP 422');
  });
});
