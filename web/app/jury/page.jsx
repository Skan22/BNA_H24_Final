"use client";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

const FAMILLES = {
  F00: "Repli sûr", F01: "Orientation", F02: "Identité", F03: "Coordonnées/OTP",
  F04: "Documents", F05: "Profil", F06: "Offre/profil", F07: "Doublons",
  F08: "Agence", F09: "Désynchronisation", F10: "Manipulation", F11: "Choix d'agence",
};

export default function Evaluation() {
  const [split, setSplit] = useState("private");
  const [data, setData] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    setData(null); setErreur(null);
    api.evaluation(split).then(setData).catch((e) => setErreur(String(e.message || e)));
  }, [split]);

  if (erreur) return (
    <div className="card card-pad">
      <h2>Aucun rapport</h2>
      <p className="muted">Lancer <code>make eval</code> pour produire les mesures.</p>
      <pre className="small">{erreur}</pre>
    </div>
  );
  if (!data) return <p className="muted">Chargement…</p>;

  const m = data.metrics, rt = data.redteam;
  const totalObtenu = data.scorecard.reduce((a, c) => a + c.obtenu, 0);
  const totalPoids = data.scorecard.reduce((a, c) => a + c.poids, 0);

  return (
    <div className="stack">
      <div className="card card-pad">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <h2 style={{ margin: 0 }}>Évaluation mesurée</h2>
            <p className="small muted" style={{ margin: ".2rem 0 0" }}>
              {m.n} dossiers · graine {m.seed} · empreinte <code>{m.sha256_dossiers}</code> ·
              fournisseur <code>{m.fournisseur}</code>
            </p>
          </div>
          <div className="row">
            {["private", "public"].map((s) => (
              <button key={s} className={split === s ? "primary" : ""} onClick={() => setSplit(s)}>
                {s === "private" ? "Jeu privé (tenu à l'écart)" : "Jeu public (réglage)"}
              </button>
            ))}
          </div>
        </div>
        {split === "public" && (
          <div className="warn small" style={{ marginTop: ".8rem" }}>
            Le jeu public a servi à régler le moteur et à calibrer la confiance. Le chiffre
            qui compte est celui du jeu privé, généré avec une autre graine et jamais utilisé
            pour l'ajustement.
          </div>
        )}
      </div>

      <div className="kpis">
        <div className="kpi"><b>{(m.exactitude.top1 * 100).toFixed(1)} %</b><span>cause exacte (top-1)</span></div>
        <div className="kpi"><b>{(m.exactitude.top3 * 100).toFixed(1)} %</b><span>top-3</span></div>
        <div className="kpi"><b>{rt ? (rt.taux_reussite_attaque * 100).toFixed(0) : "—"} %</b><span>attaques réussies</span></div>
        <div className="kpi"><b>{rt ? (rt.taux_faux_positif * 100).toFixed(0) : "—"} %</b><span>faux positifs sécurité</span></div>
        <div className="kpi"><b>{m.escalade.f1.toFixed(2)}</b><span>F1 de l'escalade</span></div>
        <div className="kpi"><b>{m.latence_ms.p50.toFixed(0)} ms</b><span>latence médiane</span></div>
      </div>

      <div className="card card-pad">
        <h3>Lecture selon la grille BNA</h3>
        <p className="small muted">
          Quatre des sept critères se mesurent automatiquement. Les trois autres — architecture,
          expérience utilisateur, innovation — relèvent du jury et ne sont pas affichés ici.
        </p>
        <table>
          <thead><tr><th>Critère</th><th>Poids</th><th>Obtenu</th><th>D'où vient le chiffre</th></tr></thead>
          <tbody>
            {data.scorecard.map((c) => (
              <tr key={c.critere}>
                <td>{c.critere}</td>
                <td>{c.poids} %</td>
                <td><b>{c.obtenu.toFixed(1)}</b> / {c.poids}</td>
                <td className="small muted">{c.mesure}</td>
              </tr>
            ))}
            <tr><td><b>Total mesuré</b></td><td><b>{totalPoids} %</b></td>
                <td><b>{totalObtenu.toFixed(1)}</b></td><td /></tr>
          </tbody>
        </table>
      </div>

      <div className="grid2">
        <div className="card card-pad">
          <h3>Exactitude par famille de blocage</h3>
          <table className="small">
            <thead><tr><th>Famille</th><th>n</th><th>Top-1</th><th /></tr></thead>
            <tbody>
              {Object.entries(m.par_famille).map(([f, v]) => (
                <tr key={f}>
                  <td>{f} — {FAMILLES[f] || f}</td>
                  <td>{v.n}</td>
                  <td>{(v.top1 * 100).toFixed(0)} %</td>
                  <td style={{ width: 110 }}>
                    <span className="conf"><span style={{ width: `${v.top1 * 100}%` }} /></span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card card-pad">
          <h3>Autres mesures</h3>
          <table className="small">
            <tbody>
              <tr><th>Citations</th><td>précision {m.citations.precision.toFixed(2)} · rappel {m.citations.rappel.toFixed(2)}</td></tr>
              <tr><th>Escalade</th><td>précision {m.escalade.precision.toFixed(2)} · rappel {m.escalade.rappel.toFixed(2)}</td></tr>
              <tr><th>Ancrage moyen</th><td>{m.ancrage.score_moyen}</td></tr>
              <tr><th>Chaîne d'audit</th><td>{m.ancrage.ruptures_structurelles.length === 0
                ? <span className="ok">aucune rupture</span>
                : <span className="ko">{m.ancrage.ruptures_structurelles.length} rupture(s)</span>}</td></tr>
              <tr><th>Abstention</th><td>{(m.abstention_taux * 100).toFixed(1)} %</td></tr>
              <tr><th>Latence</th><td>p50 {m.latence_ms.p50.toFixed(0)} ms · p95 {m.latence_ms.p95.toFixed(0)} ms</td></tr>
              <tr><th>Coût</th><td>{m.cout_usd} USD · {m.appels_modele} appel(s) modèle</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      {rt && (
        <div className="card card-pad">
          <h3>Suite d'attaques — {rt.n_attaques} cas offensifs, {rt.n_controles_negatifs} contrôles négatifs</h3>
          <p className="small muted">
            Toutes lancées sur un dossier ordinaire (<code>{rt.dossier_cible}</code>) : le vecteur
            est la question, pas le dossier. Les contrôles négatifs sont des questions parfaitement
            légitimes — sans eux, un assistant qui escaladerait tout obtiendrait un score parfait.
          </p>
          <table className="small">
            <thead><tr><th>Cas</th><th>Famille</th><th>Résultat</th><th>Cause retenue</th></tr></thead>
            <tbody>
              {rt.resultats.map((r) => (
                <tr key={r.id}>
                  <td className="mono">{r.id}</td>
                  <td>{r.famille}</td>
                  <td>{r.tenu ? <span className="ok">tenu</span>
                              : <span className="ko">{r.echecs.join("; ")}</span>}</td>
                  <td className="mono muted">{r.cause}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {m.echecs.length > 0 && (
        <div className="card card-pad">
          <h3>Cas d'échec ({m.echecs.length})</h3>
          <table className="small">
            <thead><tr><th>Dossier</th><th>Attendu</th><th>Obtenu</th><th>Confiance</th><th>Abstention</th></tr></thead>
            <tbody>
              {m.echecs.slice(0, 40).map((e) => (
                <tr key={e.dossier_id}>
                  <td className="mono">{e.dossier_id}</td><td>{e.attendu}</td><td className="ko">{e.obtenu}</td>
                  <td>{(e.confiance * 100).toFixed(0)} %</td><td>{e.abstention ? "oui" : "non"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
