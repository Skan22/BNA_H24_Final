// Toutes les requêtes passent par /api, relayé vers FastAPI (voir next.config.mjs) : une seule origine,
// donc le cookie de session (HttpOnly, SameSite=Strict) accompagne chaque appel sans CORS.
const base = "/api";
let csrf = "";

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function call(url, { method = "GET", body } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && csrf) headers["X-CSRF-Token"] = csrf;
  const r = await fetch(base + url, { method, headers, credentials: "same-origin",
                                      body: body === undefined ? undefined : JSON.stringify(body) });
  if (!r.ok) {
    let detail = r.statusText;
    try { const j = await r.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* corps non JSON */ }
    throw new ApiError(r.status, detail);
  }
  return r.json();
}

export const api = {
  health: () => call("/health"),
  demo: () => call("/v1/auth/demo"),
  me: async () => { const s = await call("/v1/auth/me"); csrf = s.csrf; return s; },
  login: async (body) => { const s = await call("/v1/auth/login", { method: "POST", body }); csrf = s.csrf; return s; },
  logout: async () => { await call("/v1/auth/logout", { method: "POST", body: {} }); csrf = ""; },
  dossiers: () => call("/v1/dossiers"),
  diagnose: (body) => call("/v1/diagnoses", { method: "POST", body }),
  trace: (id) => call(`/v1/diagnoses/${id}/trace`),
  explanation: (id) => call(`/v1/diagnoses/${id}/explanation`),
  preview: (id, body) => call(`/v1/diagnoses/${id}/preview`, { method: "POST", body }),
  regle: (anchor) => call(`/v1/corpus/${anchor}`),
  draft: (diagnosis_id, note) => call("/v1/escalations", { method: "POST", body: { diagnosis_id, note } }),
  confirm: (id) => call(`/v1/escalations/${id}/confirm`, { method: "POST", body: {} }),
  audit: (dossier_id) => call(`/v1/audit?dossier_id=${dossier_id}`),
  evaluation: (split) => call(`/v1/eval/summary?split=${split}`),
};

export const ETAPES = ["ORIENTATION", "CHOIX_AGENCE", "IDENTITE", "COORDONNEES", "PROFIL",
  "CHOIX_OFFRE", "DOCUMENTS", "SIGNATURE", "VALIDATION_AGENCE", "ACTIVATION"];

export const ETAPE_COURTE = {
  ORIENTATION: "Début", CHOIX_AGENCE: "Agence", IDENTITE: "Identité", COORDONNEES: "Contact", PROFIL: "Profil",
  CHOIX_OFFRE: "Offre", DOCUMENTS: "Pièces", SIGNATURE: "Signature",
  VALIDATION_AGENCE: "Validation", ACTIVATION: "Activation",
};

export function classeConfiance(c) {
  return c >= 0.8 ? "" : c >= 0.6 ? " mid" : " low";
}

export const DISPOSITIONS = {
  resolved: "Plus aucun blocage", action_required: "Il resterait des actions à mener",
  human_review_required: "Une vérification humaine resterait nécessaire",
};
