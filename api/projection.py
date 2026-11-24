"""Vues par rôle. Le client ne reçoit jamais de code de cause, de fait, de score, de trace ni
de règle interne ; il ne reçoit rien qui révèle une détection de manipulation (R-SEC-006)."""
from __future__ import annotations

from contracts.models import Diagnosis, Owner
from engine.graph import CAUSE_BY_ID, node_of
from engine.rag.corpus import CORPUS
from engine.render import RESPONSABLE_EN_CLAIR

# Documents de procédure interne : lisibles par l'agent, jamais par le client.
DOCS_INTERNES = {"DOC-SEC-01", "DOC-ESC-01", "DOC-AGC-01", "DOC-SYN-01"}
FAMILLES_SANS_EXPLICATION_CLIENT = {"F10", "F00"}   # manipulation, repli sûr


def visible_client(anchor: str) -> bool:
    r = CORPUS.rules.get(anchor)
    return bool(r) and r.doc_id not in DOCS_INTERNES


def _manipulation(d: Diagnosis) -> bool:
    return any(c.family == "F10" for c in d.causes)


def client_diagnosis(d: Diagnosis) -> dict:
    cache = _manipulation(d)
    return {
        "reference": d.trace_id,
        "dossier_id": d.dossier_id,
        "step": d.step.value,
        "status": d.status.value,
        "explanation_client": d.explanation_client.model_dump(),
        "unblock_path": [] if cache else [
            {"order": s.order, "action": s.action, "owner": s.owner.value, "eta_hours": s.eta_hours}
            for s in d.unblock_path],
        "sources": [] if cache else [s.model_dump() for s in d.sources if visible_client(s.anchor)],
        "human_validation_required": d.human_validation_required,
        "abstained": d.abstained,
    }


def agent_explanation(d: Diagnosis) -> dict:
    steps = []
    for c in d.causes:
        node = node_of(c.cause_id)
        steps.append({
            "cause_id": c.cause_id, "label_fr": c.label_fr, "family": c.family,
            "confidence": c.confidence, "owner": c.owner.value,
            "facts": [e.model_dump() for e in c.evidence],
            "rules": [x.model_dump() for x in CORPUS.resolve(c.anchors)],
            "next_steps": node.get("remediation", []),
            "human_validation_required": bool(node.get("requires_human_validation")),
        })
    return {"trace_id": d.trace_id, "summary": f"{len(steps)} chaîne(s) de preuve : faits observés → règle citée → suite.",
            "steps": steps, "limitations": LIMITES}


def explained_causes(d: Diagnosis) -> list:
    return [c for c in d.causes if c.family not in FAMILLES_SANS_EXPLICATION_CLIENT]


def client_explanation(d: Diagnosis) -> dict:
    steps = []
    for i, c in enumerate(explained_causes(d)):
        node = node_of(c.cause_id)
        steps.append({
            "step": i, "title": c.label_fr,
            "next_steps": [{"action": s["action"], "owner": RESPONSABLE_EN_CLAIR[Owner(s["owner"])],
                            "eta_hours": s["eta_hours"]} for s in node.get("remediation", [])],
            "sources": [x.model_dump() for x in CORPUS.resolve(c.anchors) if visible_client(x.anchor)],
            "human_validation_required": bool(node.get("requires_human_validation")),
        })
    summary = (f"{len(steps)} point(s) expliqué(s) à partir des règles de la démonstration." if steps
               else "Un conseiller va examiner votre dossier ; aucune cause n'est affirmée à ce stade.")
    return {"reference": d.trace_id, "summary": summary, "steps": steps, "limitations": LIMITES[:2]}


def client_preview(p: dict, disclaimer: str) -> dict:
    return {"cleared": [c["label_fr"] for c in p["cleared"]], "remaining": [c["label_fr"] for c in p["remaining"]],
            "simulated_disposition": p["simulated_disposition"],
            "human_validation_required": p["human_validation_required"], "disclaimer": disclaimer}


LIMITES = [
    "Cette vue explique des règles synthétiques, pas une politique bancaire réelle.",
    "Une correspondance de règle n'est ni une approbation, ni une validation d'identité, ni une correction du dossier.",
    "Les textes libres (messages, texte des documents) ne deviennent jamais des faits de preuve.",
]
DISCLAIMER_PREVIEW = ("Simulation uniquement : aucune donnée n'a été modifiée et aucun accord bancaire "
                      "n'est donné. Le résultat suppose l'action réalisée ET vérifiée par la banque.")

