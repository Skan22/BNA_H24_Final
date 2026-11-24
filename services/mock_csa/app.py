"""API simulée du back-office CSA.

Porte l'état de référence interne. Deux particularités volontaires :

  - le rapprochement des doublons est fait CÔTÉ SERVICE : l'appelant ne reçoit
    que les dossiers liés à SON dossier, jamais l'index complet (R-SEC-003) ;
  - l'état CSA peut diverger de celui de H24, ou être absent. C'est le cas réel
    décrit par R-SYN-001, et l'assistant doit s'en accommoder sans conclure.

Une seule écriture : la préparation d'une escalade, qui n'est jamais transmise
sans acquittement humain (R-ESC-003).
"""
from __future__ import annotations

import json
import os
import pathlib
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.security import require_key

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPLIT = os.getenv("BOUSSOLA_SPLIT", "public")
BASE = ROOT / "kit" / "scenarios" / SPLIT
CSA = json.loads((BASE / "csa_state.json").read_text())
DOSSIERS = {d["dossier_id"]: d for d in json.loads((BASE / "dossiers.json").read_text())}

app = FastAPI(
    title="API back-office CSA (simulée)",
    version="1.0.0",
    description=("Portail interne de gestion des abonnements H24, sur données synthétiques. "
                 "Lecture seule, hormis la préparation d'escalade."),
)
require_key(app)

ESCALADES: dict[str, dict] = {}


@app.get("/health")
def health():
    return {"statut": "ok", "split": SPLIT, "n_etats": len(CSA.get("etats", {}))}


@app.get("/relations", summary="Relations bancaires existantes pour une identité")
def relations(identite: str = ""):
    return [r for r in CSA.get("relations", []) if identite and r.get("cin") == identite]


@app.get("/subscriptions", summary="Abonnements actifs pour une identité")
def subscriptions(identite: str = ""):
    return [s for s in CSA.get("subscriptions", []) if identite and s.get("identite") == identite]


@app.get("/duplicates", summary="Dossiers liés à celui de la session")
def duplicates(dossier_id: str = ""):
    """Le rapprochement se fait ici. L'index complet ne sort jamais du service."""
    moi = DOSSIERS.get(dossier_id)
    if not moi:
        return []
    p = moi["prospect"]
    out = []
    for x in CSA.get("dossiers_index", []):
        if x["dossier_id"] == dossier_id:
            continue
        if ((p.get("cin") and x.get("cin") == p["cin"])
                or (x.get("email") and x["email"] == p["email"])
                or (x.get("telephone") and x["telephone"] == p["telephone"])):
            out.append(x)
    return out


@app.get("/etats/{dossier_id}", summary="État du dossier vu par le back-office")
def etat(dossier_id: str):
    e = CSA.get("etats", {}).get(dossier_id)
    if e is None:
        # Absence assumée : le CSA n'a rien à dire sur ce dossier. Ce n'est pas
        # une erreur, et ce n'est surtout pas une désynchronisation.
        raise HTTPException(404, "aucun état CSA pour ce dossier")
    return e


@app.get("/agency-queue/{code_agence}", summary="Charge d'une agence (agrégats, sans nominatif)")
def agency_queue(code_agence: str):
    q = CSA.get("agency_queue", {}).get(code_agence)
    if q is None:
        raise HTTPException(404, "agence inconnue")
    return q


class DemandeEscalade(BaseModel):
    dossier_id: str
    destinataire: str
    motif: str
    note: str
    trace_id: str
    human_ack: bool = False


@app.post("/escalations", summary="Prépare une escalade (jamais transmise sans acquittement)")
def create_escalation(demande: DemandeEscalade):
    if not demande.human_ack:
        # Le refus est explicite et porte le nom de la règle : une escalade
        # transmise sans acquittement serait une décision prise par la machine.
        raise HTTPException(403, "acquittement humain requis avant transmission (R-ESC-003)")
    eid = f"ESC-{uuid.uuid4().hex[:8].upper()}"
    ESCALADES[eid] = {"escalation_id": eid, "transmise": True, **demande.model_dump()}
    return ESCALADES[eid]


@app.get("/escalations/{escalation_id}")
def get_escalation(escalation_id: str):
    e = ESCALADES.get(escalation_id)
    if not e:
        raise HTTPException(404, "escalade inconnue")
    return e
