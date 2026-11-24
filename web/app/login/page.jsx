"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";
import { useSession } from "../session";

export default function Connexion() {
  const [role, setRole] = useState("agent");
  const [mdp, setMdp] = useState("");
  const [dossier, setDossier] = useState("");
  const [demo, setDemo] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [charge, setCharge] = useState(false);
  const { setSession } = useSession();
  const router = useRouter();

  useEffect(() => { api.demo().then(setDemo).catch(() => setDemo(null)); }, []);

  async function envoyer(e) {
    e.preventDefault(); setCharge(true); setErreur(null);
    try {
      const s = await api.login({ username: role, password: mdp, dossier_id: role === "client" ? dossier.trim() : null });
      setMdp(""); setSession(s);
      router.replace(role === "client" ? "/client" : "/agent");
    } catch (err) { setErreur(err.status === 401 ? "Identifiants invalides." : String(err.message || err)); }
    finally { setCharge(false); }
  }

  return (
    <div className="card card-pad" style={{ maxWidth: 520, margin: "2rem auto" }}>
      <h2>Ouvrir un espace</h2>
      <p className="muted small">Environnement de démonstration, données entièrement fictives.</p>
      <form onSubmit={envoyer} className="stack">
        <label htmlFor="role">Espace</label>
        <select id="role" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="agent">Agent — diagnostic et suivi</option>
          <option value="client">Client — comprendre ma demande</option>
        </select>
        {role === "client" && (
          <>
            <label htmlFor="dossier">Numéro de dossier</label>
            <input id="dossier" required pattern="DOS-[A-Z]{3}-[0-9]{6}" placeholder="DOS-PUB-000001"
                   value={dossier} onChange={(e) => setDossier(e.target.value)} list="demo-dossiers" />
            {demo && <datalist id="demo-dossiers">{demo.scenarios.map((x) => <option key={x.dossier_id} value={x.dossier_id}>{x.label_fr}</option>)}</datalist>}
          </>
        )}
        <label htmlFor="mdp">Mot de passe</label>
        <input id="mdp" type="password" required autoComplete="current-password" value={mdp}
               onChange={(e) => setMdp(e.target.value)} />
        {erreur && <div className="danger" role="alert">{erreur}</div>}
        <button className="primary" disabled={charge}>{charge ? "Connexion…" : "Accéder à mon espace"}</button>
      </form>
    </div>
  );
}
