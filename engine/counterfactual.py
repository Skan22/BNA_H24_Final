"""BOUSSOLA — étage D : chemin de déblocage minimal.

Plutôt que d'égrener la cause de tête, on répond à la question que le client se
pose réellement : « qu'est-ce qu'il me reste à faire, exactement, et dans quel
ordre ? »

Méthode : on rassemble TOUTES les causes bloquantes actives (pas seulement la
première), on prend leurs remédiations, on supprime les doublons, et on les
ordonne selon la position de la cause dans le parcours — corriger son identité
avant de discuter de l'offre. Le résultat est le plus court chemin connu vers
un dossier recevable.
"""
from __future__ import annotations

from contracts.models import Owner, UnblockStep
from engine.graph import CAUSE_BY_ID, ScoredCause, node_of

# Position de chaque famille dans le parcours (R-GEN-001). Sert uniquement à
# ordonner les actions : on ne demande pas de choisir une offre à quelqu'un
# dont la pièce d'identité n'est pas encore recevable.
ORDRE_FAMILLE = {
    "F10": 0,   # sécurité : traitée avant tout
    "F01": 1,   # orientation
    "F11": 2,   # choix de l'agence (première étape du parcours, R-AGE-001)
    "F02": 3,   # identité
    "F03": 4,   # coordonnées
    "F05": 5,   # profil
    "F04": 6,   # documents
    "F06": 7,   # offre
    "F07": 8,   # doublons
    "F09": 9,   # technique
    "F08": 10,  # agence
    "F00": 11,
}

# Lignes produites par le chemin de déblocage lui-même (légitimes par construction pour le contrôle d'ancrage).
PREFIXE_AGENCES = "Agences ouvertes qui prennent en charge votre profil : "

# En dessous, la cause n'est pas assez soutenue pour justifier une action
# supplémentaire demandée au client.
SEUIL_ACTION = 0.50


def build(ranked: list[ScoredCause], *, retenues: list[str], alternatives: list[str] | None = None,
          abstained: bool = False, agences: list[str] | None = None) -> list[UnblockStep]:
    actives = [c for c in ranked if c.score >= SEUIL_ACTION or c.cause_id in retenues]
    if abstained and not actives:
        actives = ranked[:1]

    vues: set[str] = set()
    brutes: list[tuple[int, int, dict, str]] = []
    for cause in actives:
        rang = ORDRE_FAMILLE.get(CAUSE_BY_ID[cause.cause_id]["family"], 99)
        for i, step in enumerate(node_of(cause.cause_id).get("remediation", [])):
            cle = step["action"].strip().lower()
            if cle in vues:
                continue
            vues.add(cle)
            brutes.append((rang, i, step, cause.cause_id))

    brutes.sort(key=lambda t: (t[0], t[1]))
    out: list[UnblockStep] = []
    for ordre, (_, _, step, _cid) in enumerate(brutes, start=1):
        out.append(UnblockStep(order=ordre, action=step["action"], owner=Owner(step["owner"]),
                               eta_hours=int(step["eta_hours"]), anchors=list(step.get("anchors", []))))

    # R-OFR-016 : un refus d'offre sans alternative est une cause d'abandon
    # évitable. Si le prospect reste éligible à autre chose, on le dit.
    if alternatives and any(c.cause_id.startswith("C-OFR") for c in actives):
        out.append(UnblockStep(
            order=len(out) + 1,
            action="Offres pour lesquelles vous restez éligible : " + ", ".join(alternatives),
            owner=Owner.CLIENT, eta_hours=1, anchors=["R-OFR-016"]))
    # R-AGE-006 : « choisissez une autre agence » sans dire lesquelles serait une impasse.
    if agences and any(c.cause_id in ("C-AGE-002", "C-AGE-003") for c in actives):
        out.append(UnblockStep(
            order=len(out) + 1,
            action=PREFIXE_AGENCES + ", ".join(agences[:4]),
            owner=Owner.CLIENT, eta_hours=0, anchors=["R-AGE-006"]))
    return out


def eta_total(path: list[UnblockStep]) -> int:
    """Délai de bout en bout : les actions du client s'enchaînent, celles des
    équipes internes peuvent se dérouler en parallèle."""
    client = sum(s.eta_hours for s in path if s.owner == Owner.CLIENT)
    interne = max((s.eta_hours for s in path if s.owner != Owner.CLIENT), default=0)
    return client + interne
