"use client";
import { useState } from "react";
import DossierPicker from "../dossier-picker";
import { api, classeConfiance, DISPOSITIONS } from "../../lib/api";

function Confiance({ v }) {
  return (
    <span className="row" style={{ gap: ".45rem" }}>
      <span className={"conf" + classeConfiance(v)} style={{ width: 64 }}>
        <span style={{ width: `${Math.round(v * 100)}%` }} />
      </span>
      <b className="small">{Math.round(v * 100)} %</b>
    </span>
  );
}

function CarteRegle({ anchor }) {
  const [regle, setRegle] = useState(null);
  const [ouvert, setOuvert] = useState(false);

  async function basculer() {
    if (!ouvert && !regle) { try { setRegle(await api.regle(anchor)); } catch { /* ancre absente */ } }
    setOuvert(!ouvert);
  }
  return (
    <div style={{ borderBottom: "1px solid var(--gris-clair)", padding: ".5rem 0" }}>
      <button onClick={basculer} style={{ border: 0, background: "none", padding: 0, textAlign: "left" }}>
        <span className="pill bleu mono">{anchor}</span>{" "}
        <span className="small muted">{regle ? regle.titre : "voir la règle"}</span>
      </button>
      {ouvert && regle && (
        <div className="small" style={{ marginTop: ".5rem", paddingLeft: ".3rem" }}>
          <div style={{ whiteSpace: "pre-wrap" }}>{regle.texte}</div>
          <div className="muted" style={{ marginTop: ".4rem" }}>
            {regle.doc_id} · version {regle.version} · en vigueur au {regle.effective_date}
          </div>
        </div>
      )}
    </div>
  );
}

export default function PosteAgent() {
  const [dossier, setDossier] = useState("");
  const [question, setQuestion] = useState("");
  const [diag, setDiag] = useState(null);
  const [trace, setTrace] = useState(null);
  const [charge, setCharge] = useState(false);
  const [escalade, setEscalade] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [onglet, setOnglet] = useState("diagnostic");
  const [preuve, setPreuve] = useState(null);
  const [simu, setSimu] = useState({});
  const [note, setNote] = useState("");
  const [brouillon, setBrouillon] = useState(null);

  async function analyser() {
    if (!dossier) return;
    setCharge(true); setErreur(null); setEscalade(null); setTrace(null); setPreuve(null); setSimu({});
    setBrouillon(null); setNote("");
    try {
      const d = await api.diagnose({ dossier_id: dossier, question: question || null, locale: "fr" });
      setDiag(d);
      setTrace(await api.trace(d.trace_id));
    } catch (e) { setErreur(String(e.message || e)); }
    finally { setCharge(false); }
  }

  async function preparer() {
    try { setBrouillon(await api.draft(diag.trace_id, note)); } catch (e) { setErreur(String(e.message || e)); }
  }
  // L'acquittement est la session agent elle-même : le serveur ne reçoit aucun « human_ack ».
  async function transmettre() {
    try { setEscalade(await api.confirm(brouillon.id)); } catch (e) { setErreur(String(e.message || e)); }
  }
  async function ouvrirPreuve() {
    setOnglet("preuve");
    if (!preuve) { try { setPreuve(await api.explanation(diag.trace_id)); } catch (e) { setErreur(String(e.message || e)); } }
  }
  async function simuler(causeId) {
    try { setSimu({ ...simu, [causeId]: await api.preview(diag.trace_id, { cause_id: causeId }) }); }
    catch (e) { setErreur(String(e.message || e)); }
  }

  const refus = trace ? trace.entries.filter((e) => e.kind === "tool.call" && !e.payload.allowed) : [];

  return (
    <div className="stack">
      <div className="card card-pad">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>Poste agent</h2>
          {diag && <span className="pill mono">{diag.trace_id}</span>}
        </div>
        <div className="sep" />
        <DossierPicker value={dossier} onChange={(v) => { setDossier(v); setDiag(null); }} />
        <div className="row" style={{ marginTop: ".6rem" }}>
          <input placeholder="Question du client, telle qu'elle a été reçue (facultatif)"
                 value={question} onChange={(e) => setQuestion(e.target.value)}
                 style={{ flex: 1, minWidth: 240 }} />
          <button className="primary" onClick={analyser} disabled={!dossier || charge}>
            {charge ? "Analyse…" : "Analyser"}
          </button>
        </div>
        {erreur && <div className="danger" style={{ marginTop: ".8rem" }}>{erreur}</div>}
      </div>

      {diag && (
        <>
          <div className="row">
            {["diagnostic", "preuve", "explication", "trace"].map((o) => (
              <button key={o} className={onglet === o ? "primary" : ""}
                      onClick={() => (o === "preuve" ? ouvrirPreuve() : setOnglet(o))}>
                {o === "diagnostic" ? "Diagnostic" : o === "preuve" ? "Preuve" : o === "explication" ? "À transmettre" : "Trace"}
              </button>
            ))}
          </div>

          {onglet === "diagnostic" && (
            <div className="grid2">
              <div className="stack">
                <div className="card card-pad">
                  <h3>Causes probables</h3>
                  {diag.causes.map((c, i) => (
                    <div key={c.cause_id} style={{
                      padding: ".6rem 0",
                      borderBottom: i < diag.causes.length - 1 ? "1px solid var(--gris-clair)" : 0,
                    }}>
                      <div className="row" style={{ justifyContent: "space-between" }}>
                        <span>
                          <span className="pill mono">{c.cause_id}</span>{" "}
                          <b>{c.label_fr}</b>
                        </span>
                        <Confiance v={c.confidence} />
                      </div>
                      <div className="small muted" style={{ marginTop: ".25rem" }}>
                        famille {c.family} · responsable : {c.owner} ·
                        règles {c.anchors.join(", ")}
                      </div>
                      {c.family !== "F10" && c.family !== "F00" && (
                        <button className="small" style={{ marginTop: ".4rem" }} onClick={() => simuler(c.cause_id)}>
                          Et si ce blocage était levé ?
                        </button>
                      )}
                      {simu[c.cause_id] && (
                        <div className="simu small" aria-live="polite">
                          <b>{DISPOSITIONS[simu[c.cause_id].simulated_disposition]}</b> — {simu[c.cause_id].assumption}
                          {simu[c.cause_id].remaining.length > 0 && (
                            <div>Reste : {simu[c.cause_id].remaining.map((r) => `${r.cause_id} ${r.label_fr}`).join(" · ")}</div>)}
                          {simu[c.cause_id].human_validation_required && <div>Vérification humaine requise.</div>}
                          <div className="muted">{simu[c.cause_id].disclaimer}</div>
                        </div>
                      )}
                      {i === 0 && c.evidence.length > 0 && (
                        <div className="small" style={{ marginTop: ".4rem" }}>
                          {c.evidence.map((e) => (
                            <div key={e.fact} className="row" style={{ gap: ".4rem" }}>
                              <span className="mono muted" style={{ minWidth: "14rem" }}>{e.fact}</span>
                              <span className="mono">{JSON.stringify(e.value)}</span>
                              <span className="pill">{e.weight > 0 ? "+" : ""}{e.weight}</span>
                              <span className="small muted">{e.source}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                <div className="card card-pad">
                  <h3>Chemin de déblocage le plus court</h3>
                  <ol className="actions">
                    {diag.unblock_path.map((s) => (
                      <li key={s.order}>
                        {s.action}
                        <div className="small muted" style={{ marginTop: ".15rem" }}>
                          {s.owner} · {s.eta_hours} h · {s.anchors.join(", ")}
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              </div>

              <div className="stack">
                <div className="card card-pad">
                  <h3>État constaté</h3>
                  <table className="small">
                    <tbody>
                      <tr><th>Étape</th><td>{diag.step}</td></tr>
                      <tr><th>Statut</th><td>{diag.status}</td></tr>
                      <tr><th>Code</th><td>
                        <code>{diag.error_code || "aucun"}</code>
                        {diag.error_code === "H24-000" &&
                          <div className="muted">Code générique : il ne désigne aucune cause (R-GEN-020).</div>}
                      </td></tr>
                      <tr><th>Confiance</th><td><Confiance v={diag.confidence} /></td></tr>
                      <tr><th>Actions permises</th><td>{diag.allowed_actions.join(", ") || "—"}</td></tr>
                    </tbody>
                  </table>
                </div>

                <div className="card card-pad">
                  <h3>Règles citées</h3>
                  {diag.sources.map((s) => <CarteRegle key={s.anchor} anchor={s.anchor} />)}
                </div>

                {diag.human_validation_required && (
                  <div className="card card-pad">
                    <h3>Escalade</h3>
                    <div className="warn small">
                      Ce cas dépasse ce que l'assistant peut trancher. La note est préparée, elle
                      n'est transmise qu'après votre acquittement (R-ESC-003).
                    </div>
                    <pre className="small" style={{
                      whiteSpace: "pre-wrap", background: "var(--fond)", padding: ".8rem",
                      borderRadius: 8, marginTop: ".7rem",
                    }}>{diag.explanation_agent.escalation_draft}</pre>
                    {!brouillon ? (
                      <>
                        <label htmlFor="note" className="small muted">Note complémentaire (données fictives uniquement)</label>
                        <textarea id="note" maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)}
                                  style={{ width: "100%", minHeight: 60 }} />
                        <button className="primary" onClick={preparer}>Préparer le brouillon</button>
                      </>
                    ) : (
                      <button className="primary" onClick={transmettre} disabled={!!escalade}>
                        {escalade ? `Confirmée (simulation) — ${escalade.reference}` : "J'acquitte et je confirme"}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {onglet === "preuve" && preuve && (
            <div className="card card-pad">
              <h3>Comment cette conclusion est construite</h3>
              <p className="muted small">{preuve.summary}</p>
              {preuve.steps.map((st) => (
                <div className="preuve" key={st.cause_id}>
                  <b>{st.cause_id} — {st.label_fr}</b> <span className="pill">{Math.round(st.confidence * 100)} %</span>
                  <div className="small" style={{ marginTop: ".4rem" }}><b>Faits observés</b></div>
                  {st.facts.map((f) => (
                    <div key={f.fact} className="small mono">{f.fact} = {JSON.stringify(f.value)} <span className="muted">({f.source}, {f.weight > 0 ? "+" : ""}{f.weight})</span></div>
                  ))}
                  <div className="small" style={{ marginTop: ".4rem" }}><b>Règles citées</b></div>
                  {st.rules.map((r) => <div key={r.anchor} className="small"><span className="pill bleu mono">{r.anchor}</span> {r.extrait}</div>)}
                  <div className="small" style={{ marginTop: ".4rem" }}><b>Suite</b>{st.human_validation_required && " — validation humaine"}</div>
                  <ol className="small">{st.next_steps.map((n) => <li key={n.action}>{n.action} <span className="muted">({n.owner}, {n.eta_hours} h)</span></li>)}</ol>
                </div>
              ))}
              <details><summary>Limites de cette explication</summary><ul>{preuve.limitations.map((l) => <li key={l}>{l}</li>)}</ul></details>
            </div>
          )}

          {onglet === "explication" && (
            <div className="grid2">
              <div className="card card-pad">
                <h3>Message prêt à transmettre au client</h3>
                <div className="bubble">{diag.explanation_agent.suggested_message}</div>
                <button style={{ marginTop: ".8rem" }}
                        onClick={() => navigator.clipboard?.writeText(diag.explanation_agent.suggested_message)}>
                  Copier
                </button>
              </div>
              <div className="card card-pad">
                <h3>Synthèse interne</h3>
                <pre className="small" style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                  {diag.explanation_agent.summary}
                </pre>
              </div>
            </div>
          )}

          {onglet === "trace" && trace && (
            <div className="stack">
              <div className="card card-pad">
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <h3 style={{ margin: 0 }}>Journal d'audit</h3>
                  <span className={trace.integrite.ok ? "pill vert" : "pill rouge"}>
                    {trace.integrite.detail}
                  </span>
                </div>
                <p className="small muted">
                  Chaque entrée porte l'empreinte de la précédente. Modifier ou retirer une ligne
                  casse la chaîne, et cela se vérifie (R-SEC-007).
                </p>
                <div className="trace">
                  {trace.entries.map((e) => (
                    <div key={e.seq} className="ev">
                      <b>{e.kind}</b>
                      <span style={{ flex: 1 }}>
                        {e.kind === "tool.call"
                          ? <>
                              {e.payload.tool}{" "}
                              {e.payload.allowed
                                ? <span className="ok">autorisé</span>
                                : <span className="ko">REFUSÉ — {e.payload.reason}</span>}
                            </>
                          : JSON.stringify(e.payload)}
                      </span>
                      <span className="muted mono" style={{ fontSize: ".72rem" }}>
                        {e.hash.slice(0, 10)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {refus.length > 0 && (
                <div className="card card-pad">
                  <h3>Appels refusés par le courtier</h3>
                  <p className="small muted">
                    Ces refus ne sont pas des erreurs : ce sont les garde-fous qui s'appliquent.
                  </p>
                  <table className="small">
                    <thead><tr><th>Outil</th><th>Motif</th></tr></thead>
                    <tbody>
                      {refus.map((r) => (
                        <tr key={r.seq}><td className="mono">{r.payload.tool}</td>
                          <td className="ko">{r.payload.reason}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="card card-pad">
                <h3>Scores du graphe causal</h3>
                <table className="small">
                  <tbody>
                    {Object.entries(diag.trace.graph_scores).map(([c, s]) => (
                      <tr key={c}>
                        <td className="mono">{c}</td>
                        <td style={{ width: 90 }}><Confiance v={s} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="sep" />
                <h3>Décisions de politique</h3>
                <table className="small">
                  <tbody>
                    {diag.trace.policy_decisions.map((p, i) => (
                      <tr key={i}>
                        <td>{p.rule}</td>
                        <td style={{ width: 90 }}>
                          <span className={p.triggered ? "pill ambre" : "pill"}>
                            {p.triggered ? "déclenchée" : "non"}
                          </span>
                        </td>
                        <td className="muted">{p.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="sep" />
                <div className="row small muted">
                  <span>ancrage : {diag.trace.groundedness_score}</span>
                  <span>latence : {diag.trace.latency_ms} ms</span>
                  <span>modèle : {diag.trace.provider}</span>
                  <span>coût : {diag.trace.cost_usd} USD</span>
                  <span>arbitrage : {diag.trace.adjudicated ? "oui" : "non"}</span>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
