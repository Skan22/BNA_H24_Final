"""BOUSSOLA — vérification d'ancrage.

Deux contrôles, de nature différente :

  1. STRUCTUREL (toujours, sans modèle) — on vérifie que chaque ancre citée
     existe réellement dans le corpus, et que chaque action proposée au client
     provient littéralement de la remédiation déclarée par le nœud causal.
     Comme le français est produit par gabarit à partir de ces seuls éléments,
     ce contrôle est une garantie, pas une estimation : une phrase inventée
     n'a aucun chemin pour entrer dans le texte.

  2. SÉMANTIQUE (si un modèle est disponible) — un second avis qui relit
     l'explication à la lumière des règles citées et signale toute affirmation
     non soutenue. Il sert surtout aux traductions et à tout texte que le
     modèle aurait touché.

Un échec du contrôle structurel est un défaut du moteur, pas du modèle : il
doit faire échouer la suite de tests.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from contracts.models import Citation, UnblockStep
from engine.graph import GRAPH, node_of
from engine.llm.provider import LLMUnavailable
from engine.counterfactual import PREFIXE_AGENCES
from engine.rag.corpus import CORPUS


class RapportAncrage(BaseModel):
    structurel_ok: bool
    ancres_inconnues: list[str] = []
    actions_hors_graphe: list[str] = []
    score: float | None = None
    phrases_non_soutenues: list[str] = []
    methode: str = "structurel"


class _Entailment(BaseModel):
    phrases_non_soutenues: list[str] = Field(
        default_factory=list,
        description="Phrases de l'explication qui affirment quelque chose que les règles citées ne disent pas")
    score: float = Field(ge=0.0, le=1.0, description="Part des affirmations soutenues par les règles citées")


SYSTEM_VERIF = (
    "Tu vérifies qu'une explication donnée à un client bancaire ne dit rien de "
    "plus que ce que disent les règles citées. Tu reçois l'explication et le "
    "texte intégral des règles. Tu listes les phrases qui affirment un fait, un "
    "délai, un seuil ou une démarche absents des règles, et tu donnes la part "
    "d'affirmations correctement soutenues.\n\n"
    "Les formules d'accompagnement (« votre demande est arrêtée », « un conseiller "
    "vous recontactera ») ne sont pas des affirmations réglementaires : elles ne "
    "comptent pas comme non soutenues. Tu ne réécris rien."
)


def verifier(provider, *, texte_client: str, citations: list[Citation],
             path: list[UnblockStep], cause_id: str | None) -> RapportAncrage:
    # --- 1. Contrôle structurel ------------------------------------------
    inconnues = [c.anchor for c in citations if c.anchor not in CORPUS.rules]

    actions_autorisees = set()
    if cause_id:
        for step in node_of(cause_id).get("remediation", []):
            actions_autorisees.add(step["action"].strip().lower())
    # R-OFR-016 : la ligne d'alternatives est produite par le chemin de
    # déblocage lui-même, elle est donc légitime par construction.
    hors_graphe = [
        s.action for s in path
        if s.action.strip().lower() not in actions_autorisees
        and not s.action.startswith("Offres pour lesquelles vous restez éligible")
        and not s.action.startswith(PREFIXE_AGENCES)
        and "R-OFR-016" not in s.anchors
    ]
    # Une action peut venir d'une autre cause active du chemin de déblocage :
    # on n'invalide que celles qui n'existent nulle part dans le graphe.
    if hors_graphe:
        toutes = {st["action"].strip().lower()
                  for n in GRAPH["nodes"] for st in n.get("remediation", [])}
        hors_graphe = [a for a in hors_graphe if a.strip().lower() not in toutes]

    rapport = RapportAncrage(
        structurel_ok=not inconnues and not hors_graphe,
        ancres_inconnues=inconnues,
        actions_hors_graphe=hors_graphe,
    )

    # --- 2. Contrôle sémantique (facultatif) ------------------------------
    passages = CORPUS.anchors_for_passage_check([c.anchor for c in citations])
    if not passages:
        rapport.score = 1.0 if rapport.structurel_ok else 0.0
        return rapport
    try:
        out = provider.structured(
            system=SYSTEM_VERIF,
            user=f"EXPLICATION\n{texte_client}\n\nRÈGLES CITÉES\n{passages}",
            schema=_Entailment, tier="verify")
    except LLMUnavailable:
        # Hors ligne, le texte français est assemblé exclusivement à partir
        # d'éléments tracés : le contrôle structurel fait foi.
        rapport.score = 1.0 if rapport.structurel_ok else 0.0
        return rapport

    rapport.score = round(out.score, 3)
    rapport.phrases_non_soutenues = out.phrases_non_soutenues
    rapport.methode = "structurel+entailment"
    return rapport


def phrases(texte: str) -> list[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", texte) if p.strip()]
