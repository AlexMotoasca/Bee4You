import * as Crypto from 'expo-crypto';

/** Client-generated record id (UUID v4). Every new row gets one before it is written. */
export function newId(): string {
  return Crypto.randomUUID();
}

/** Timestamp for client_updated_at / created_at etc. The server accepts ISO with "T". */
export function nowIso(): string {
  return new Date().toISOString();
}

/**
 * PowerSync delivers timestamptz as "2026-11-25 09:30:00.000Z" while rows written on the
 * phone use "2026-11-25T09:30:00.000Z". Accept both.
 */
export function parseDbDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value.includes('T') ? value : value.replace(' ', 'T'));
  return Number.isNaN(date.getTime()) ? null : date;
}
