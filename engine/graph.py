"""BOUSSOLA — étage B : scoring du graphe causal.

Le graphe est la barrière anti-hallucination. Une cause dont les prérequis
factuels sont absents obtient un score nul et ne peut pas être remontée, quel
que soit ce qu'un modèle de langage en penserait ensuite.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any

import yaml

from contracts.models import CauseCandidate, Evidence, Owner
from engine.signals import Fact

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text())


GRAPH = _load(ROOT / "engine" / "rules" / "graph.yaml")
CAUSES = _load(ROOT / "contracts" / "causes.yaml")
CAUSE_BY_ID = {c["id"]: c for c in CAUSES["causes"]}
NODE_BY_ID = {n["cause_id"]: n for n in GRAPH["nodes"]}
THRESHOLDS = GRAPH["thresholds"]


def _truthy(v: Any) -> bool:
    return bool(v) and v != [] and v != {}


def evaluate(cond: dict, facts: dict[str, Fact]) -> bool:
    """Évalue une condition d'arête. Un fait absent est FAUX, jamais une erreur."""
    fact = facts.get(cond["fact"])
    if fact is None:
        return False
    val, op, ref = fact.value, cond.get("op", "truthy"), cond.get("value")
    if op == "truthy":
        return _truthy(val)
    if op == "non_empty":
        return _truthy(val)
    if op == "==":
        return val == ref
    if op == "!=":
        return val != ref
    if op == "in":
        return val in ref
    if val is None:
        return False
    if op == ">":
        return val > ref
    if op == ">=":
        return val >= ref
    if op == "<":
        return val < ref
    if op == "<=":
        return val <= ref
    raise ValueError(f"opérateur inconnu dans graph.yaml : {op}")


@dataclass
class ScoredCause:
    cause_id: str
    score: float
    evidence: list[Evidence]
    node: dict

    @property
    def family(self) -> str:
        return CAUSE_BY_ID[self.cause_id]["family"]


def score_all(facts: dict[str, Fact]) -> list[ScoredCause]:
    """Score chaque nœud du graphe. Retour trié par score décroissant."""
    out: list[ScoredCause] = []
    for node in GRAPH["nodes"]:
        cid = node["cause_id"]
        if cid == "C-UNK-000":
            continue                       # produite par la politique, jamais scorée
        # Prérequis durs : sans eux, la cause est impossible.
        if not all(_truthy(facts[r].value) if r in facts else False for r in node.get("requires", [])):
            continue
        total, ev = 0.0, []
        for cond in node.get("evidence", []):
            if evaluate(cond, facts):
                total += cond["weight"]
                fa = facts[cond["fact"]]
                ev.append(Evidence(fact=fa.name, value=fa.value, weight=cond["weight"], source=fa.source))
        for cond in node.get("inhibits", []):
            if evaluate(cond, facts):
                total -= cond["weight"]
                fa = facts[cond["fact"]]
                ev.append(Evidence(fact=f"¬{fa.name}", value=fa.value, weight=-cond["weight"], source=fa.source))
        if total > 0:
            out.append(ScoredCause(cid, round(min(total, 1.0), 4), ev, node))
    return sorted(out, key=lambda s: (-s.score, s.cause_id))


def is_ambiguous(ranked: list[ScoredCause]) -> tuple[bool, str]:
    """Vrai si plusieurs FAMILLES se disputent la tête à moins d'une marge.

    Deux causes d'une même famille à égalité ne changent ni l'explication ni
    l'action : ce n'est pas une ambiguïté utile. Deux familles, si.
    """
    if len(ranked) < 2:
        return False, ""
    marge = THRESHOLDS["ambiguity_margin"]
    tete = ranked[0]
    concurrents = [s for s in ranked[1:] if tete.score - s.score <= marge and s.family != tete.family]
    if not concurrents:
        return False, ""
    noms = ", ".join(f"{s.cause_id} ({s.score:.2f})" for s in [tete, *concurrents])
    return True, f"familles concurrentes à moins de {marge} : {noms}"


def to_candidate(s: ScoredCause, *, confidence: float | None = None) -> CauseCandidate:
    meta = CAUSE_BY_ID[s.cause_id]
    return CauseCandidate(
        cause_id=s.cause_id,
        family=meta["family"],
        label_fr=meta["label_fr"],
        confidence=round(confidence if confidence is not None else s.score, 4),
        owner=Owner(meta["owner"]),
        evidence=s.evidence,
        anchors=list(s.node.get("anchors", [])),
    )


def node_of(cause_id: str) -> dict:
    return NODE_BY_ID[cause_id]


def label(cause_id: str, locale: str = "fr") -> str:
    return CAUSE_BY_ID[cause_id].get(f"label_{locale}") or CAUSE_BY_ID[cause_id]["label_fr"]
