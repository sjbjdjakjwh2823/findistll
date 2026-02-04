import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !key) {
    // Return a dummy client for development/demo
    return {
      auth: {
        signInWithOAuth: () => Promise.resolve({ error: null }),
        signInWithOtp: () => Promise.resolve({ error: null }),
        signOut: () => Promise.resolve({ error: null }),
      }
    } as any;
  }

  return createBrowserClient(url, key)
}
