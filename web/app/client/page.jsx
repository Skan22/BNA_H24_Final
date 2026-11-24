"use client";
import { useState } from "react";
import { api, ETAPES, ETAPE_COURTE, DISPOSITIONS } from "../../lib/api";
import { useSession } from "../session";

const LANGUES = [["fr", "Français"], ["ar", "العربية"], ["en", "English"]];

function Duree({ h }) {
  return h > 0 ? <span className="pill" style={{ marginLeft: ".5rem" }}>{h < 24 ? `${h} h` : `${Math.round(h / 24)} j`}</span> : null;
}

export default function EspaceClient() {
  const { session } = useSession();
  const [question, setQuestion] = useState("");
  const [locale, setLocale] = useState("fr");
  const [diag, setDiag] = useState(null);
  const [preuve, setPreuve] = useState(null);
  const [charge, setCharge] = useState(false);
  const [erreur, setErreur] = useState(null);

  async function demander() {
    setCharge(true); setErreur(null); setPreuve(null);
    try { setDiag(await api.diagnose({ question: question || null, locale })); }
    catch (e) { setErreur(String(e.message || e)); }
    finally { setCharge(false); }
  }
  async function voirPreuve() {
    if (preuve) { setPreuve(null); return; }
    try { setPreuve(await api.explanation(diag.reference)); } catch (e) { setErreur(String(e.message || e)); }
  }

  if (!session) return null;
  const texte = diag && (locale === "ar" ? diag.explanation_client.ar : locale === "en" ? diag.explanation_client.en
                         : diag.explanation_client.fr);
  // La liste d'actions est affichée dans sa propre carte : on ne la répète pas dans la bulle d'explication.
  const intro = texte && texte.replace(/\n\nCe qu'il vous reste à faire :[\s\S]*$/, "");
  const aFaire = diag ? diag.unblock_path.filter((s) => s.owner === "client") : [];
  const enAttente = diag ? diag.unblock_path.filter((s) => s.owner !== "client") : [];
  const idxEtape = diag ? ETAPES.indexOf(diag.step) : -1;

  return (
    <div className="stack">
      <div className="card card-pad">
        <h2>Où en est ma demande ?</h2>
        <p className="muted small">Dossier <code>{session.dossier_id}</code></p>
        <div className="row">
          <label className="sr-only" htmlFor="q" style={{ position: "absolute", left: -9999 }}>Votre question</label>
          <input id="q" placeholder="Une question ? (facultatif)" value={question} maxLength={2000}
                 onChange={(e) => setQuestion(e.target.value)} style={{ flex: 1, minWidth: 220 }} />
          <select aria-label="Langue" value={locale} onChange={(e) => setLocale(e.target.value)} style={{ width: 130 }}>
            {LANGUES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <button className="primary" onClick={demander} disabled={charge}>{charge ? "Analyse…" : "Savoir pourquoi"}</button>
        </div>
        <p className="small muted" style={{ margin: ".6rem 0 0" }}>
          N'écrivez ici aucun mot de passe ni code reçu par SMS.
        </p>
        {erreur && <div className="danger" role="alert" style={{ marginTop: ".8rem" }}>{erreur}</div>}
      </div>

      {diag && (
        <div aria-live="polite" className="stack">
          <div className="card card-pad">
            <h3>Votre parcours</h3>
            <div className="stepper">
              {ETAPES.map((e, i) => (
                <div key={e} className={i < idxEtape ? "done" : i === idxEtape ? "now" : ""}>{ETAPE_COURTE[e]}</div>
              ))}
            </div>
            <div className="bubble" lang={locale} dir={locale === "ar" ? "rtl" : "ltr"}>
              {intro || diag.explanation_client.fr}
            </div>
            {locale !== "fr" && diag.explanation_client.traduction === "gabarit" && (
              <p className="small muted" role="note">
                {locale === "ar"
                  ? "نص مختصر جاهز مسبقًا (الخطوة وسبب التوقف). التفاصيل الكاملة بالفرنسية أدناه."
                  : "Short pre-written text (step and reason). Full details are in French below."}
              </p>
            )}
            {locale !== "fr" && <details><summary>Texte français</summary><p>{diag.explanation_client.fr}</p></details>}
          </div>

          {aFaire.length > 0 && (
            <div className="card card-pad">
              <h3>Ce qu'il vous reste à faire</h3>
              <ol className="actions">{aFaire.map((s) => <li key={s.order}>{s.action}<Duree h={s.eta_hours} /></li>)}</ol>
            </div>
          )}
          {enAttente.length > 0 && (
            <div className="card card-pad">
              <h3>Ce qui avance de notre côté</h3>
              <ul className="muted" style={{ paddingLeft: "1.1rem", margin: 0 }}>
                {enAttente.map((s) => <li key={s.order}>{s.action}
                  <span className="small"> ({s.owner === "agence" ? "votre agence" : "nos équipes"})</span></li>)}
              </ul>
            </div>
          )}
          {diag.human_validation_required && (
            <div className="warn">Un conseiller BNA doit examiner votre dossier avant la suite. Aucune décision n'est prise automatiquement.</div>
          )}

          <div className="card card-pad">
            <button onClick={voirPreuve}>{preuve ? "Masquer" : "Pourquoi cette réponse ?"}</button>
            {preuve && (
              <div style={{ marginTop: ".8rem" }}>
                <p className="muted">{preuve.summary}</p>
                {preuve.steps.map((s) => <ClientPreuve key={s.step} step={s} reference={diag.reference} />)}
                <details><summary>Limites</summary><ul>{preuve.limitations.map((l) => <li key={l}>{l}</li>)}</ul></details>
              </div>
            )}
          </div>
          <p className="small muted">Référence à rappeler à votre agence : <code>{diag.reference}</code>.</p>
        </div>
      )}
    </div>
  );
}

function ClientPreuve({ step, reference }) {
  const [simu, setSimu] = useState(null);
  const [err, setErr] = useState(null);
  async function simuler() {
    setErr(null);
    try { setSimu(await api.preview(reference, { step: step.step })); } catch (e) { setErr(String(e.message || e)); }
  }
  return (
    <div className="preuve">
      <b>{step.title}</b>
      <ul className="small" style={{ paddingLeft: "1.1rem" }}>
        {step.next_steps.map((n) => <li key={n.action}>{n.action} <span className="muted">({n.owner}{n.eta_hours ? `, ~${n.eta_hours} h` : ""})</span></li>)}
      </ul>
      {step.sources.map((s) => <div className="small muted" key={s.anchor}>{s.titre} — {s.extrait}</div>)}
      <button className="small" onClick={simuler} style={{ marginTop: ".5rem" }}>Et si c'était réglé ?</button>
      {err && <div className="danger small" role="alert">{err}</div>}
      {simu && (
        <div className="simu small" aria-live="polite">
          <div>{DISPOSITIONS[simu.simulated_disposition]}.</div>
          {simu.remaining.length > 0 && <div>Il resterait : {simu.remaining.join(", ")}.</div>}
          {simu.human_validation_required && <div>Un conseiller devrait encore vérifier.</div>}
          <div className="muted">{simu.disclaimer}</div>
        </div>
      )}
    </div>
  );
}
