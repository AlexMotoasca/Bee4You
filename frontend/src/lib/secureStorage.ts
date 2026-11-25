import * as SecureStore from 'expo-secure-store';

/**
 * Encrypted key/value storage for the Supabase session (Keystore on Android, Keychain on iOS).
 * Sessions can be larger than what some devices accept in one SecureStore entry, so values
 * are split into chunks: `<key>.n` holds the chunk count, `<key>.0..n-1` the parts.
 */
export const CHUNK_SIZE = 1800;

type Store = Pick<typeof SecureStore, 'getItemAsync' | 'setItemAsync' | 'deleteItemAsync'>;

export function createChunkedStorage(store: Store = SecureStore) {
  async function count(key: string): Promise<number> {
    const raw = await store.getItemAsync(`${key}.n`);
    const n = raw === null ? 0 : Number.parseInt(raw, 10);
    return Number.isFinite(n) && n > 0 ? n : 0;
  }

  async function removeItem(key: string): Promise<void> {
    const n = await count(key);
    for (let i = 0; i < n; i++) await store.deleteItemAsync(`${key}.${i}`);
    await store.deleteItemAsync(`${key}.n`);
  }

  async function getItem(key: string): Promise<string | null> {
    const n = await count(key);
    if (n === 0) return null;
    const parts: string[] = [];
    for (let i = 0; i < n; i++) {
      const part = await store.getItemAsync(`${key}.${i}`);
      if (part === null) return null; // incomplete write: treat as signed out
      parts.push(part);
    }
    return parts.join('');
  }

  async function setItem(key: string, value: string): Promise<void> {
    const previous = await count(key);
    const n = Math.max(1, Math.ceil(value.length / CHUNK_SIZE));
    for (let i = 0; i < n; i++) {
      await store.setItemAsync(`${key}.${i}`, value.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE));
    }
    await store.setItemAsync(`${key}.n`, String(n));
    for (let i = n; i < previous; i++) await store.deleteItemAsync(`${key}.${i}`);
  }

  return { getItem, setItem, removeItem };
}

export const secureStorage = createChunkedStorage();
