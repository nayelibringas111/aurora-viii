import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, configureAuth } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import type { Me } from "@/types";

type Mode = "supabase" | "local";
interface AuthState {
  mode: Mode | null;
  me: Me | null;
  loading: boolean;
  configError: string | null;
  signInLocal: (email: string, name: string) => Promise<void>;
  signInPassword: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, name: string) => Promise<string>;
  signOut: () => Promise<void>;
  refreshMe: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);
const LOCAL_KEY = "aurora8.token";

const store = {
  get: () => { try { return localStorage.getItem(LOCAL_KEY); } catch { return null; } },
  set: (v: string | null) => { try { v ? localStorage.setItem(LOCAL_KEY, v) : localStorage.removeItem(LOCAL_KEY); } catch { /* almacenamiento no disponible */ } },
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);
  const memToken = useRef<string | null>(store.get());
  const modeRef = useRef<Mode | null>(null);

  const refreshMe = useCallback(async () => {
    try { setMe(await api.get<Me>("/me")); } catch { setMe(null); }
  }, []);

  useEffect(() => {
    configureAuth(async () => {
      if (modeRef.current === "supabase" && supabase) {
        const { data } = await supabase.auth.getSession();
        return data.session?.access_token ?? null;
      }
      return memToken.current;
    }, () => { memToken.current = null; store.set(null); setMe(null); });

    (async () => {
      try {
        const cfg = await api.get<{ auth_mode: Mode }>("/auth/config");
        modeRef.current = cfg.auth_mode;
        setMode(cfg.auth_mode);
        if (cfg.auth_mode === "supabase" && !supabase) {
          setConfigError("La API usa Supabase Auth, pero faltan VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY en el frontend.");
        } else {
          await refreshMe();
        }
      } catch (e) {
        setConfigError(e instanceof Error ? e.message : "No se pudo contactar con la API");
      } finally {
        setLoading(false);
      }
    })();
    const sub = supabase?.auth.onAuthStateChange((event) => {
      if (modeRef.current !== "supabase") return;
      if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED") refreshMe();
      if (event === "SIGNED_OUT") setMe(null);
    });
    return () => sub?.data.subscription.unsubscribe();
  }, [refreshMe]);

  const value = useMemo<AuthState>(() => ({
    mode, me, loading, configError, refreshMe,
    signInLocal: async (email, name) => {
      const r = await api.post<{ access_token: string }>("/auth/local-login", { email, display_name: name });
      memToken.current = r.access_token;
      store.set(r.access_token);
      await refreshMe();
    },
    signInPassword: async (email, password) => {
      if (!supabase) throw new Error("Supabase no está configurado");
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw new Error(error.message === "Invalid login credentials" ? "Correo o contraseña incorrectos" : error.message);
      await refreshMe();
    },
    signUp: async (email, password, name) => {
      if (!supabase) throw new Error("Supabase no está configurado");
      const { data, error } = await supabase.auth.signUp({ email, password, options: { data: { full_name: name }, emailRedirectTo: window.location.origin } });
      if (error) throw new Error(error.message);
      if (data.session) { await refreshMe(); return "Cuenta creada."; }
      return "Revisa tu correo para confirmar la cuenta y luego ingresa.";
    },
    signOut: async () => {
      if (mode === "supabase" && supabase) await supabase.auth.signOut();
      memToken.current = null;
      store.set(null);
      setMe(null);
    },
  }), [mode, me, loading, configError, refreshMe]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth fuera de AuthProvider");
  return v;
}
