"""BOUSSOLA — assemblage de la vue du monde et exécution des étages A et B.

Séparé de `diagnose.py` pour que l'évaluateur puisse mesurer le chemin
déterministe seul, sans modèle de langage : c'est la référence à laquelle tout
apport du modèle doit être comparé.
"""
from __future__ import annotations

import json
import os
import pathlib
from datetime import datetime

from contracts.models import Dossier
from engine.broker import Broker, Session
from engine.graph import ScoredCause, is_ambiguous, score_all
from engine.signals import Fact, WorldView, extract

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "kit" / "catalog.json").read_text())

# Date de référence du kit. Figée pour que les calculs d'âge, d'expiration et
# de délai restent reproductibles d'un jour sur l'autre.
# BOUSSOLA_AS_OF=now (ou une date ISO) pour une instance branchée sur des données vivantes.
_AS_OF = os.getenv("BOUSSOLA_AS_OF", "2026-09-26T10:30:00")
AS_OF = datetime.now().replace(microsecond=0) if _AS_OF == "now" else datetime.fromisoformat(_AS_OF)


def build_worldview(broker: Broker, dossier: Dossier, *, question: str | None = None) -> WorldView:
    """Interroge les outils AUTORISÉS et n'en garde que ce qui est revenu.

    Aucun accès direct au port : tout passe par le courtier, donc tout est tracé
    et tout refus se voit.
    """
    w = WorldView(question=question)
    w.relations = broker.try_call("csa.get_relations") or []
    w.subscriptions = broker.try_call("csa.get_subscriptions") or []
    w.doublons = broker.try_call("csa.search_duplicates") or []
    w.etat_csa = broker.try_call("csa.get_etat")
    if dossier.agence.code_agence:
        w.agency_queue = broker.try_call("csa.get_agency_queue", code_agence=dossier.agence.code_agence)
    return w


def run_deterministic(dossier: Dossier, world: WorldView) -> tuple[dict[str, Fact], list[ScoredCause], tuple[bool, str]]:
    facts = extract(dossier, world, catalog=CATALOG, as_of=AS_OF)
    ranked = score_all(facts)
    return facts, ranked, is_ambiguous(ranked)


def load_dossier(port, dossier_id: str) -> Dossier | None:
    raw = port.get_dossier(dossier_id)
    return Dossier.model_validate(raw) if raw else None


def open_session(port, dossier_id: str, trace_id: str) -> tuple[Session, Broker, Dossier]:
    raw = port.get_dossier(dossier_id)
    if raw is None:
        raise KeyError(dossier_id)
    dossier = Dossier.model_validate(raw)
    identite = dossier.prospect.cin or dossier.prospect.passeport
    session = Session(trace_id=trace_id, dossier_id=dossier_id, identite=identite)
    return session, Broker(port, session), dossier
