"""BOUSSOLA — simulation « et si ? », en lecture seule.

Question posée : si le blocage X était levé et vérifié, que resterait-il ? On
reprend les faits réels du dossier, on neutralise les prérequis durs du nœud
causal X (jamais la source), puis on rejoue le scoring et la politique. Rien
n'est écrit nulle part : la copie de faits est jetée, aucun outil d'écriture
n'est appelé, et aucun modèle n'intervient.
"""
from __future__ import annotations

from engine import policy
from engine.graph import CAUSE_BY_ID, node_of, score_all
from engine.pipeline import build_worldview, open_session, run_deterministic
from engine.signals import Fact

NON_SIMULABLES_FAMILLE = {"F10"}      # lever une manipulation n'a pas de sens
NON_SIMULABLES = {"C-UNK-000"}


class NotSimulable(ValueError):
    pass


def simulable(cause_id: str) -> bool:
    meta = CAUSE_BY_ID.get(cause_id)
    return bool(meta) and cause_id not in NON_SIMULABLES and meta["family"] not in NON_SIMULABLES_FAMILLE


def simulate(port, dossier_id: str, cause_id: str, avant: list[str]) -> dict:
    if not simulable(cause_id):
        raise NotSimulable("cette cause ne peut pas être simulée")
    session, broker, dossier = open_session(port, dossier_id, "TR-simulation")
    world = build_worldview(broker, dossier)
    facts, _, _ = run_deterministic(dossier, world)
    for requis in node_of(cause_id).get("requires", []):
        ancien = facts[requis].value if requis in facts else False
        facts[requis] = Fact(requis, [] if isinstance(ancien, list) else False, "simulation")
    ranked = score_all(facts)
    outcome = policy.apply(ranked, facts)
    reste = [c.cause_id for c in ranked]
    levees = [c for c in avant if c not in reste and c != "C-UNK-000"]
    if not reste:
        disposition = "resolved"
    elif outcome.abstained or outcome.human_validation_required:
        disposition = "human_review_required"
    else:
        disposition = "action_required"
    return {
        "cause_id": cause_id,
        "cleared": [{"cause_id": c, "label_fr": CAUSE_BY_ID[c]["label_fr"]} for c in levees],
        "remaining": [{"cause_id": c, "label_fr": CAUSE_BY_ID[c]["label_fr"]} for c in reste],
        "simulated_disposition": disposition,
        # Lever ce blocage reste soumis à vérification humaine si sa cause l'exige.
        "human_validation_required": bool(node_of(cause_id).get("requires_human_validation"))
        or (bool(reste) and (outcome.abstained or outcome.human_validation_required)),
    }
