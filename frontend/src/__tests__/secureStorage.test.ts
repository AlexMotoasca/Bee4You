import { CHUNK_SIZE, createChunkedStorage } from '@/lib/secureStorage';

function memoryStore() {
  const map = new Map<string, string>();
  return {
    map,
    getItemAsync: async (k: string) => map.get(k) ?? null,
    setItemAsync: async (k: string, v: string) => {
      map.set(k, v);
    },
    deleteItemAsync: async (k: string) => {
      map.delete(k);
    },
  };
}

describe('chunked secure storage (Supabase session)', () => {
  it('round-trips a value larger than one chunk', async () => {
    const store = memoryStore();
    const storage = createChunkedStorage(store as never);
    const session = 'x'.repeat(CHUNK_SIZE * 2 + 17);
    await storage.setItem('sb-auth', session);
    expect(store.map.get('sb-auth.n')).toBe('3');
    expect(await storage.getItem('sb-auth')).toBe(session);
  });

  it('removes leftover chunks when the value shrinks', async () => {
    const store = memoryStore();
    const storage = createChunkedStorage(store as never);
    await storage.setItem('k', 'y'.repeat(CHUNK_SIZE * 3));
    await storage.setItem('k', 'short');
    expect(await storage.getItem('k')).toBe('short');
    expect(store.map.has('k.1')).toBe(false);
    expect(store.map.has('k.2')).toBe(false);
  });

  it('returns null when missing or incomplete, and removes everything', async () => {
    const store = memoryStore();
    const storage = createChunkedStorage(store as never);
    expect(await storage.getItem('none')).toBeNull();
    await storage.setItem('k', 'z'.repeat(CHUNK_SIZE + 1));
    store.map.delete('k.1');
    expect(await storage.getItem('k')).toBeNull();
    await storage.removeItem('k');
    expect([...store.map.keys()]).toEqual([]);
  });
});
