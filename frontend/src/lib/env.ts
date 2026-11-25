/**
 * The only place EXPO_PUBLIC_* variables are read. Expo inlines them at build time, which
 * only works with static `process.env.NAME` access (no destructuring, no brackets).
 * Everything here is visible inside the app: never put secrets in frontend/.env.
 */

function required(name: string, value: string | undefined): string {
  if (!value || !value.trim()) {
    throw new Error(`Missing ${name}. Copy frontend/.env.example to frontend/.env and fill it in.`);
  }
  return value.trim().replace(/\/+$/, '');
}

export const env = {
  supabaseUrl: required('EXPO_PUBLIC_SUPABASE_URL', process.env.EXPO_PUBLIC_SUPABASE_URL),
  supabaseKey: required('EXPO_PUBLIC_SUPABASE_KEY', process.env.EXPO_PUBLIC_SUPABASE_KEY),
  powersyncUrl: required('EXPO_PUBLIC_POWERSYNC_URL', process.env.EXPO_PUBLIC_POWERSYNC_URL),
  apiUrl: required('EXPO_PUBLIC_API_URL', process.env.EXPO_PUBLIC_API_URL),
} as const;
