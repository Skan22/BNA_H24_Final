"""BOUSSOLA — politique de repli sûr.

« En cas de doute, l'assistant s'arrête et escalade plutôt que de deviner. »
Ce fichier est l'endroit où cette phrase devient du code exécutable et testable.

Ordre d'application, du plus grave au plus bénin :
  1. sécurité      un contenu injecté ou une demande hors périmètre l'emporte
                   sur toute autre lecture du dossier
  2. budget        si la session a été tronquée, la vue du monde est partielle
  3. contradiction deux référentiels en désaccord sur un dossier par ailleurs
                   explicable : on ne choisit pas lequel a raison (R-SYN-004)
  4. ambiguïté     plusieurs familles à égalité, non tranchées par l'arbitrage
  5. confiance     score sous le seuil calibré
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field

from contracts.models import PolicyDecision
from engine.graph import THRESHOLDS, ScoredCause
from engine.signals import Fact

ROOT = pathlib.Path(__file__).resolve().parents[1]
CALIBRATION_PATH = ROOT / "engine" / "rules" / "calibration.json"

CAUSES_SECURITE = {
    "sec.injection_document": "C-SEC-001",
    "sec.injection_message": "C-SEC-002",
    "sec.hors_perimetre": "C-SEC-003",
}


def _calibration() -> list[list[float]]:
    """Table brut -> calibré, produite par eval/calibrate.py sur le jeu PUBLIC.

    Absente, on reste sur l'identité : mieux vaut une confiance non calibrée et
    annoncée comme telle qu'un chiffre inventé.
    """
    if CALIBRATION_PATH.exists():
        return json.loads(CALIBRATION_PATH.read_text())["bins"]
    return []


def calibrate(raw: float) -> float:
    bins = _calibration()
    for lo, hi, value in bins:
        if lo <= raw < hi:
            return round(value, 4)
    return round(raw, 4)


@dataclass
class Outcome:
    causes: list[ScoredCause]
    confidence: float
    abstained: bool
    human_validation_required: bool
    decisions: list[PolicyDecision] = field(default_factory=list)
    escalation_reason: str | None = None
    cause_indeterminee: bool = False
    """Vrai seulement si l'on s'arrête FAUTE de savoir.

    Une tentative de manipulation déclenche aussi une escalade, mais la cause,
    elle, est parfaitement identifiée : la confondre avec une indétermination
    ferait perdre l'information au moment du triage."""


def apply(ranked: list[ScoredCause], facts: dict[str, Fact], *,
          budget_message: str | None = None,
          adjudication: dict | None = None,
          score_of=lambda c: c.score) -> Outcome:
    d: list[PolicyDecision] = []

    def note(rule: str, triggered: bool, detail: str) -> bool:
        d.append(PolicyDecision(rule=rule, triggered=triggered, detail=detail))
        return triggered

    def stop(causes, reason, *, confidence, indeterminee: bool = True) -> Outcome:
        return Outcome(causes=causes, confidence=confidence, abstained=True,
                       human_validation_required=True, decisions=d, escalation_reason=reason,
                       cause_indeterminee=indeterminee)

    # --- 1. Sécurité -------------------------------------------------------
    securite = [cid for fact, cid in CAUSES_SECURITE.items()
                if fact in facts and facts[fact].value]
    if note("R-SEC-004 / R-SEC-003 — contenu ou demande suspects", bool(securite),
            f"motifs : {facts['sec.motifs_suspects'].value}" if securite else "aucun motif détecté"):
        retenues = [c for c in ranked if c.cause_id in securite] or []
        return stop(retenues, "tentative de manipulation ou demande hors périmètre",
                    confidence=max((c.score for c in retenues), default=0.9),
                    indeterminee=False)     # la cause est connue : c'est l'action qui revient à un humain

    # --- 2. Budget ---------------------------------------------------------
    if note("manifeste.budgets — session tronquée", bool(budget_message), budget_message or "budgets tenus"):
        return stop(ranked[:1], f"vue du monde incomplète : {budget_message}", confidence=0.0)

    # Convention : `triggered` signifie « cette règle a provoqué un arrêt ».
    # Une décision affichée comme déclenchée doit toujours être une anomalie,
    # jamais un fonctionnement normal — sinon la trace devient illisible.
    if note("graphe — aucune cause plausible", not ranked,
            f"{len(ranked)} cause(s) au-dessus de zéro"):
        return stop([], "aucune cause du référentiel ne correspond à l'état constaté", confidence=0.0)

    tete = ranked[0]
    brut = score_of(tete)

    # --- 3. Contradiction entre référentiels ------------------------------
    ecart = facts.get("syn.ecart_referentiels")
    contradiction = bool(ecart and ecart.value) and not tete.cause_id.startswith("C-SYN")
    if note("R-SYN-004 — référentiels en désaccord", contradiction,
            f"écart H24/CSA de {facts['syn.ecart_minutes'].value} min alors que la cause de tête "
            f"est {tete.cause_id}" if contradiction else "référentiels concordants"):
        return stop(ranked[:THRESHOLDS["max_causes_returned"]],
                    "les deux référentiels ne décrivent pas le même dossier ; aucun n'est présumé correct",
                    confidence=calibrate(brut))

    # --- 4. Ambiguïté non tranchée ----------------------------------------
    marge = THRESHOLDS["ambiguity_margin"]
    concurrents = [c for c in ranked[1:] if brut - score_of(c) <= marge and c.family != tete.family]
    tranchee = bool(adjudication and adjudication.get("cause_id"))
    if note("R-SEC-005 — familles concurrentes", bool(concurrents) and not tranchee,
            f"{[c.cause_id for c in [tete, *concurrents]]}" if concurrents
            else "une seule famille en tête"):
        return stop(ranked[:THRESHOLDS["max_causes_returned"]],
                    "plusieurs causes de familles différentes restent également plausibles",
                    confidence=calibrate(brut))

    # --- 5. Confiance insuffisante ----------------------------------------
    confiance = calibrate(brut)
    if note("R-SEC-005 — confiance sous le seuil", confiance < THRESHOLDS["min_confidence"],
            f"{confiance:.2f} < {THRESHOLDS['min_confidence']}"):
        return stop(ranked[:THRESHOLDS["max_causes_returned"]],
                    "niveau de confiance insuffisant pour affirmer une cause",
                    confidence=confiance)

    # --- Diagnostic retenu -------------------------------------------------
    besoin_humain = bool(tete.node.get("requires_human_validation"))
    note("graphe — validation humaine exigée par la cause", besoin_humain,
         "la cause retenue relève d'un arbitrage humain" if besoin_humain
         else "la cause retenue est actionnable sans arbitrage")
    return Outcome(causes=ranked[:THRESHOLDS["max_causes_returned"]], confidence=confiance,
                   abstained=False, human_validation_required=besoin_humain, decisions=d,
                   escalation_reason=None)
