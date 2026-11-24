"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

/** Sélecteur de dossier partagé par les deux vues.
 *  En production ce choix n'existerait pas : le client est authentifié, et
 *  l'agent ouvre le dossier depuis sa file. Ici il rend la démonstration
 *  navigable — et il matérialise la frontière de session : un seul dossier. */
export default function DossierPicker({ value, onChange, filtre = "" }) {
  const [liste, setListe] = useState([]);
  const [q, setQ] = useState(filtre);
  const [scenarios, setScenarios] = useState([]);   // mode démonstration seulement

  useEffect(() => { api.dossiers().then(setListe).catch(() => setListe([])); }, []);
  useEffect(() => { api.demo().then((d) => setScenarios(d.scenarios || [])).catch(() => setScenarios([])); }, []);

  const filtres = liste.filter((d) =>
    !q || d.dossier_id.toLowerCase().includes(q.toLowerCase())
       || (d.prospect || "").toLowerCase().includes(q.toLowerCase())
       || d.step.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="row" style={{ gap: ".5rem" }}>
      {scenarios.length > 0 && (
        <select aria-label="Scénario de démonstration" value="" onChange={(e) => e.target.value && onChange(e.target.value)}
                style={{ maxWidth: 300 }}>
          <option value="">— scénario de démonstration —</option>
          {scenarios.map((x) => <option key={x.cause_id} value={x.dossier_id}>{x.cause_id} · {x.label_fr}</option>)}
        </select>
      )}
      <input aria-label="Filtrer les dossiers" placeholder="Filtrer (nom, étape, identifiant)…" value={q}
             onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 260 }} />
      <select aria-label="Dossier à analyser" value={value || ""} onChange={(e) => onChange(e.target.value)} style={{ maxWidth: 380 }}>
        <option value="">— choisir un dossier ({filtres.length}) —</option>
        {filtres.slice(0, 200).map((d) => (
          <option key={d.dossier_id} value={d.dossier_id}>
            {d.dossier_id} · {d.prospect} · {d.step} · {d.error_code}
          </option>
        ))}
      </select>
    </div>
  );
}
