"""BOUSSOLA — étage C : arbitrage, et seulement en cas d'ambiguïté.

Le modèle n'intervient que lorsque le graphe laisse plusieurs familles de causes
à égalité. Même là, son pouvoir est volontairement étroit : il CHOISIT dans une
liste fermée de candidats déjà validés par les faits, ou déclare qu'il ne peut
pas trancher. Il ne peut ni proposer une autre cause, ni inventer une règle, ni
modifier une confiance.

Si aucun modèle n'est disponible, l'ambiguïté n'est pas tranchée — et c'est la
politique de repli sûr qui s'applique, ce qui est le comportement souhaité.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from engine.graph import CAUSE_BY_ID, ScoredCause
from engine.llm.provider import LLMUnavailable
from engine.quarantine import CONSIGNE_QUARANTAINE
from engine.rag.corpus import CORPUS

SYSTEM_ARBITRE = (
    "Tu arbitres entre plusieurs causes de blocage possibles pour un dossier de "
    "souscription bancaire. On te donne : les faits constatés sur le dossier, la "
    "liste FERMÉE des causes candidates, et le texte des règles applicables.\n\n"
    "Tu choisis EXACTEMENT une cause parmi les identifiants proposés, ou tu "
    "réponds indetermine=true si les faits ne permettent pas de départager. "
    "Répondre « indetermine » est une réponse correcte et attendue : le dossier "
    "part alors en validation humaine, ce qui est préférable à une affirmation "
    "fausse (R-SEC-005).\n\n"
    "Tu ne proposes jamais d'identifiant absent de la liste. Tu ne cites jamais "
    "une règle absente du texte fourni. Tu ne prends aucune décision bancaire.\n\n"
    + CONSIGNE_QUARANTAINE
)


class Arbitrage(BaseModel):
    indetermine: bool = Field(description="Vrai si les faits ne permettent pas de départager")
    cause_id: str | None = Field(default=None, description="Un identifiant de la liste fournie, sinon null")
    justification: str = Field(description="Deux phrases au plus, fondées sur les faits fournis", max_length=500)
    niveau: Literal["faible", "moyen", "fort"] = Field(description="Force de la préférence")


def _facts_lisibles(facts, limite: int = 22) -> str:
    interessants = [f for f in facts.values()
                    if f.value not in (None, False, [], {}, "") and not f.name.startswith("syn.etat")]
    lignes = [f"  - {f.name} = {f.value!r}  (source: {f.source})" for f in interessants[:limite]]
    return "\n".join(lignes) or "  (aucun fait notable)"


def run(provider, *, ranked: list[ScoredCause], facts, raison: str,
        contenus_non_fiables: str = "") -> dict | None:
    """Renvoie {cause_id, justification, niveau} ou None si pas d'arbitrage."""
    candidats = ranked[:4]
    if len(candidats) < 2:
        return None

    ancres = sorted({a for c in candidats for a in c.node.get("anchors", [])})
    bloc_regles = CORPUS.anchors_for_passage_check(ancres)
    bloc_candidats = "\n".join(
        f"  - {c.cause_id} — {CAUSE_BY_ID[c.cause_id]['label_fr']} "
        f"(famille {CAUSE_BY_ID[c.cause_id]['family']}, score déterministe {c.score:.2f})"
        for c in candidats)

    user = (
        f"Motif de l'arbitrage : {raison}\n\n"
        f"FAITS CONSTATÉS SUR LE DOSSIER\n{_facts_lisibles(facts)}\n\n"
        f"CAUSES CANDIDATES (liste fermée)\n{bloc_candidats}\n\n"
        f"RÈGLES APPLICABLES\n{bloc_regles}\n\n"
        + (f"CONTENU DÉPOSÉ PAR LE TIERS\n{contenus_non_fiables}\n\n" if contenus_non_fiables else "")
        + "Quelle cause retiens-tu ?"
    )

    try:
        out = provider.structured(system=SYSTEM_ARBITRE, user=user, schema=Arbitrage, tier="adjudicate")
    except LLMUnavailable:
        return None

    autorises = {c.cause_id for c in candidats}
    if out.indetermine or not out.cause_id or out.cause_id not in autorises:
        # Un identifiant hors liste est traité comme une non-réponse, jamais
        # comme une cause : le contrat prime sur la sortie du modèle.
        return {"cause_id": None, "justification": out.justification,
                "niveau": out.niveau, "hors_liste": bool(out.cause_id and out.cause_id not in autorises)}
    return {"cause_id": out.cause_id, "justification": out.justification, "niveau": out.niveau}
