"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "../lib/api";

const Ctx = createContext({ session: null, setSession: () => {}, logout: async () => {} });
export const useSession = () => useContext(Ctx);

// Pages accessibles à chaque rôle : le serveur reste l'autorité, ceci évite seulement les écrans vides.
const ACCES = { client: ["/client"], agent: ["/agent", "/jury"] };

export function SessionProvider({ children }) {
  const [session, setSession] = useState(undefined);   // undefined = en cours de restauration
  const path = usePathname();
  const router = useRouter();

  useEffect(() => { api.me().then(setSession).catch(() => setSession(null)); }, []);
  useEffect(() => {
    if (session === undefined || path === "/login") return;
    if (session === null) router.replace("/login");
    else if (path !== "/" && !(ACCES[session.role] || []).includes(path)) {
      router.replace(session.role === "client" ? "/client" : "/agent");
    }
  }, [session, path, router]);

  async function logout() {
    try { await api.logout(); } catch { /* session déjà expirée */ }
    setSession(null);
    router.replace("/login");
  }
  return <Ctx.Provider value={{ session, setSession, logout }}>{children}</Ctx.Provider>;
}
