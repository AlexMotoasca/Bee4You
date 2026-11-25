import type { Session } from '@supabase/supabase-js';
import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from 'react';

import { connector } from '@/db/connector';
import { db } from '@/db/powersync';
import { supabase } from '@/lib/supabase';

type Auth = {
  session: Session | null;
  userId: string | null;
  /** True until the stored session has been read at startup. */
  loading: boolean;
  signIn: (email: string, password: string) => Promise<string | null>;
  signUp: (email: string, password: string) => Promise<string | null>;
  /** Number of local changes not uploaded yet (warn before signing out). */
  pendingUploads: () => Promise<number>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Works offline: the session is read from encrypted storage, not the network.
    supabase.auth
      .getSession()
      .then(({ data }) => setSession(data.session))
      .finally(() => setLoading(false));

    const { data } = supabase.auth.onAuthStateChange((event, next) => {
      setSession(next);
      if (event === 'SIGNED_OUT') {
        // Local data belongs to the signed-out user: wipe it.
        void db.disconnectAndClear();
      }
    });
    return () => data.subscription.unsubscribe();
  }, []);

  const userId = session?.user.id ?? null;

  useEffect(() => {
    // One connection per signed-in user; PowerSync refreshes the token via the connector.
    if (userId) void db.connect(connector);
  }, [userId]);

  const value = useMemo<Auth>(
    () => ({
      session,
      userId,
      loading,
      async signIn(email, password) {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        return error?.message ?? null;
      },
      async signUp(email, password) {
        const { error } = await supabase.auth.signUp({ email, password });
        return error?.message ?? null;
      },
      async pendingUploads() {
        const stats = await db.getUploadQueueStats();
        return stats.count;
      },
      async signOut() {
        await supabase.auth.signOut({ scope: 'local' });
      },
    }),
    [session, userId, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): Auth {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

/** For screens inside the signed-in area, where a user always exists. */
export function useUserId(): string {
  const { userId } = useAuth();
  if (!userId) throw new Error('useUserId used while signed out');
  return userId;
}
