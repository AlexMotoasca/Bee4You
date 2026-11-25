import * as SecureStore from 'expo-secure-store';
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { en, type Strings } from './en';
import { ro } from './ro';

export type Locale = 'ro-RO' | 'en-US';
export const LOCALES: readonly Locale[] = ['ro-RO', 'en-US'];

const STRINGS: Record<Locale, Strings> = { 'ro-RO': ro, 'en-US': en };
const STORE_KEY = 'ui.locale';

export function toLocale(value: string | null | undefined): Locale {
  return value?.toLowerCase().startsWith('en') ? 'en-US' : 'ro-RO';
}

/** "{n} hives" -> "3 hives". */
export function format(template: string, params: Record<string, string | number> = {}): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) =>
    key in params ? String(params[key]) : `{${key}}`,
  );
}

type I18n = { locale: Locale; t: Strings; setLocale: (locale: Locale) => void };

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('ro-RO');

  useEffect(() => {
    SecureStore.getItemAsync(STORE_KEY)
      .then((saved) => saved && setLocaleState(toLocale(saved)))
      .catch(() => undefined);
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    SecureStore.setItemAsync(STORE_KEY, next).catch(() => undefined);
  }, []);

  const value = useMemo(() => ({ locale, t: STRINGS[locale], setLocale }), [locale, setLocale]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used inside <I18nProvider>');
  return ctx;
}

/** Short date in the user's language: "azi" / "3 iun. 2026". */
export function formatDay(date: Date | null, locale: Locale, todayWord: string): string {
  if (!date) return '—';
  const now = new Date();
  if (date.toDateString() === now.toDateString()) return todayWord;
  return date.toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' });
}
