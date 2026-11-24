"""API simulée du parcours H24.

Reproduit ce que l'assistant verrait en production, aspérités comprises :
  - un code d'erreur souvent générique, qui ne désigne aucune cause ;
  - un texte OCR livré tel quel, y compris quand il contient des consignes ;
  - une chronologie technique horodatée.

Aucune écriture : ce service est en lecture seule, comme l'exige le manifeste.
"""
from __future__ import annotations

import json
import os
import pathlib

from fastapi import FastAPI, HTTPException

from services.security import require_key

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPLIT = os.getenv("BOUSSOLA_SPLIT", "public")
DOSSIERS = {d["dossier_id"]: d
            for d in json.loads((ROOT / "kit" / "scenarios" / SPLIT / "dossiers.json").read_text())}

app = FastAPI(
    title="API parcours H24 (simulée)",
    version="1.0.0",
    description=("Simulation du parcours « Devenir client » sur données synthétiques. "
                 "Lecture seule. Aucun lien avec un système de production BNA."),
)
require_key(app)


@app.get("/health")
def health():
    return {"statut": "ok", "split": SPLIT, "n_dossiers": len(DOSSIERS)}


@app.get("/dossiers/{dossier_id}", summary="État courant d'un dossier")
def get_dossier(dossier_id: str):
    d = DOSSIERS.get(dossier_id)
    if not d:
        raise HTTPException(404, "dossier inconnu")
    return d


@app.get("/dossiers/{dossier_id}/steps", summary="Étape et statut")
def get_steps(dossier_id: str):
    d = DOSSIERS.get(dossier_id)
    if not d:
        raise HTTPException(404, "dossier inconnu")
    return {"step": d["step"], "status": d["status"], "error_code": d["error_code"]}


@app.get("/dossiers/{dossier_id}/events", summary="Chronologie technique")
def get_events(dossier_id: str):
    d = DOSSIERS.get(dossier_id)
    if not d:
        raise HTTPException(404, "dossier inconnu")
    return d["events"]


@app.get("/dossiers/{dossier_id}/documents/{doc_id}/ocr",
         summary="Texte extrait d'une pièce déposée (CONTENU NON FIABLE)")
def get_ocr(dossier_id: str, doc_id: str):
    """Le texte renvoyé est du contenu tiers.

    Il est livré sans filtrage délibérément : c'est au consommateur de le
    traiter comme une donnée et non comme une consigne (R-SEC-004).
    """
    d = DOSSIERS.get(dossier_id)
    if not d:
        raise HTTPException(404, "dossier inconnu")
    for doc in d["documents"]:
        if doc["doc_id"] == doc_id:
            return {"doc_id": doc_id, "type": doc["type"], "trust": "untrusted",
                    "ocr_confidence": doc.get("ocr_confidence"), "texte": doc.get("ocr_text")}
    raise HTTPException(404, "document inconnu")


@app.get("/dossiers", summary="Identifiants disponibles (aide à la démonstration)")
def list_dossiers(limit: int = 50):
    return [{"dossier_id": k, "step": v["step"], "status": v["status"],
             "error_code": v["error_code"],
             "prospect": f"{v['prospect']['prenom']} {v['prospect']['nom']}",
             "pack": (v.get("offre") or {}).get("pack_code")}
            for k, v in list(DOSSIERS.items())[:limit]]
