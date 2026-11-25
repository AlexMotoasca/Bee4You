import { parseHiveNumber } from '@/features/colonies/colonies';
import { en } from '@/i18n/en';
import { ro } from '@/i18n/ro';
import { format, toLocale } from '@/i18n';
import { parseDbDate } from '@/lib/ids';

jest.mock('@powersync/react-native', () => ({ useQuery: jest.fn() }));
jest.mock('@/db/powersync', () => ({ db: {} }));
jest.mock('expo-crypto', () => ({ randomUUID: () => '00000000-0000-4000-8000-000000000000' }));

function keys(obj: object, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === 'object' && v !== null ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

function placeholders(text: string): string[] {
  return [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1] ?? '').sort();
}

describe('Romanian and English strings', () => {
  it('have exactly the same keys', () => {
    expect(keys(ro).sort()).toEqual(keys(en).sort());
  });

  it('use the same {placeholders} in every string', () => {
    const get = (obj: object, path: string) =>
      path.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)[k], obj) as string;
    for (const path of keys(en)) {
      expect([path, placeholders(get(ro, path))]).toEqual([path, placeholders(get(en, path))]);
    }
  });

  it('formats placeholders and maps locales', () => {
    expect(format(ro.apiaries.hives, { n: 3 })).toBe('3 stupi');
    expect(format('{a} – {b}', { a: 'x' })).toBe('x – {b}');
    expect(toLocale('en-GB')).toBe('en-US');
    expect(toLocale('ro-RO')).toBe('ro-RO');
    expect(toLocale(null)).toBe('ro-RO');
  });
});

describe('input parsing', () => {
  it('hive number: empty -> null, digits -> number, junk -> undefined', () => {
    expect(parseHiveNumber('')).toBeNull();
    expect(parseHiveNumber(' 12 ')).toBe(12);
    expect(parseHiveNumber('-3')).toBeUndefined();
    expect(parseHiveNumber('1.5')).toBeUndefined();
    expect(parseHiveNumber('abc')).toBeUndefined();
  });

  it('reads both PowerSync and local timestamp formats', () => {
    expect(parseDbDate('2026-11-25 09:30:00.000Z')?.toISOString()).toBe('2026-11-25T09:30:00.000Z');
    expect(parseDbDate('2026-11-25T09:30:00.000Z')?.toISOString()).toBe('2026-11-25T09:30:00.000Z');
    expect(parseDbDate(null)).toBeNull();
    expect(parseDbDate('garbage')).toBeNull();
  });
});
