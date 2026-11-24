"""BOUSSOLA — orchestrateur du diagnostic.

Enchaîne les étages dans un ordre fixe et trace chacun d'eux :

    ouverture de session  →  vue du monde (via le courtier)
    →  A  faits typés          (déterministe)
    →     quarantaine          (classifieur, facultatif)
    →  B  scoring du graphe    (déterministe)
    →  C  arbitrage            (modèle, seulement si ambiguïté)
    →     politique de repli    (déterministe)
    →  D  chemin de déblocage  (déterministe)
    →  E  rendu client/agent   (gabarit ; modèle pour ar/en)
    →     vérification d'ancrage
    →     scellement de la trace

Renvoie le diagnostic ET la session, pour que l'appelant dispose du journal
d'audit complet sans avoir à le reconstituer.

Retirer le modèle de cette chaîne ne la casse pas : elle produit alors un
diagnostic déterministe, avec une ambiguïté non tranchée qui part en validation
humaine. C'est une dégradation voulue, pas une panne.
"""
from __future__ import annotations

import time
import uuid

from contracts.models import (CauseCandidate, Diagnosis, DiagnoseRequest, Owner, Status, Step,
                              ToolCallRecord, Trace, Trust)
from engine import counterfactual, policy, quarantine, render, verify
from engine.adjudicate import run as adjudicate
from engine.graph import CAUSE_BY_ID, THRESHOLDS, node_of, to_candidate
from engine.llm.provider import resolve as resolve_provider
from engine.pipeline import build_worldview, open_session, run_deterministic
from engine.quarantine import Envelope
from engine.rag.corpus import CORPUS


def _enveloppes(dossier, question: str | None) -> list[Envelope]:
    """Tout ce qui vient d'un tiers, étiqueté comme tel."""
    out: list[Envelope] = []
    for d in dossier.documents:
        if d.ocr_text:
            out.append(Envelope(source=f"ocr:{d.type.value}:{d.doc_id}",
                                trust=Trust.UNTRUSTED, content=d.ocr_text))
    if dossier.message_client:
        out.append(Envelope(source="message_client", trust=Trust.UNTRUSTED,
                            content=dossier.message_client))
    if question:
        out.append(Envelope(source="question", trust=Trust.UNTRUSTED, content=question))
    return out


def diagnose(port, request: DiagnoseRequest, *, provider=None,
             trace_id: str | None = None) -> tuple[Diagnosis, object]:
    t0 = time.monotonic()
    trace_id = trace_id or f"TR-{uuid.uuid4().hex[:12]}"
    provider = provider or resolve_provider()

    session, broker, dossier = open_session(port, request.dossier_id, trace_id)
    world = build_worldview(broker, dossier, question=request.question)

    # Quarantaine : deuxième avis sur les contenus non fiables, avant toute
    # extraction de faits, pour que le verdict pèse dès le scoring.
    enveloppes = _enveloppes(dossier, request.question)
    world.injection_llm = quarantine.classify(provider, enveloppes)
    if world.injection_llm:
        session.llm_calls += 1
        session.audit.append("quarantine.classify", world.injection_llm)

    facts, ranked, (ambigu, raison) = run_deterministic(dossier, world)
    session.audit.append("signals.extract", {"n_faits": len(facts),
                                             "motifs_suspects": facts["sec.motifs_suspects"].value})
    session.audit.append("graph.score", {c.cause_id: c.score for c in ranked[:5]})

    # Arbitrage : uniquement si le graphe laisse plusieurs familles à égalité.
    arbitrage = None
    if ambigu:
        arbitrage = adjudicate(provider, ranked=ranked, facts=facts, raison=raison,
                               contenus_non_fiables=quarantine.render_data_block(
                                   [e for e in enveloppes if e.trust == Trust.UNTRUSTED]))
        if arbitrage:
            session.llm_calls += 1
            session.audit.append("adjudicate", arbitrage)
            if arbitrage.get("cause_id"):
                # Le choix du modèle réordonne, il n'ajoute rien.
                ranked = sorted(ranked, key=lambda c: c.cause_id != arbitrage["cause_id"])

    outcome = policy.apply(ranked, facts, budget_message=session.budget_exceeded(),
                           adjudication=arbitrage)
    for d in outcome.decisions:
        session.audit.append("policy", d.model_dump())

    retenues = [c.cause_id for c in outcome.causes]
    cause_tete = retenues[0] if retenues else None

    chemin = counterfactual.build(
        ranked, retenues=retenues,
        alternatives=facts["offre.alternatives"].value if "offre.alternatives" in facts else [],
        abstained=outcome.abstained,
        agences=facts["age.alternatives"].value if "age.alternatives" in facts else [])

    # Citations : les ancres du nœud causal RETENU, jamais d'une recherche
    # approchée. Les règles des hypothèses écartées restent lisibles dans
    # `causes[i].anchors` : les verser dans `sources` brouillerait la lecture.
    # S'ajoute la règle de repli quand on s'arrête faute de savoir.
    ancres: list[str] = []
    if outcome.causes:
        ancres.extend(node_of(outcome.causes[0].cause_id).get("anchors", []))
    if outcome.cause_indeterminee:
        ancres.extend(node_of("C-UNK-000")["anchors"])
    citations = CORPUS.resolve(ancres)

    # R-SEC-006 : on n'annonce pas au client ce que l'on a détecté sur lui.
    # Le détail reste dans la vue agent et dans la trace.
    motif_client = None if facts["sec.motifs_suspects"].value else outcome.escalation_reason
    explication_client = render.build_client(
        provider, step=dossier.step.value, cause_id=cause_tete, path=chemin,
        abstained=outcome.abstained, escalation_reason=motif_client,
        locale=request.locale)
    if request.locale != "fr":
        session.llm_calls += 1

    explication_agent = render.agent_fr(
        dossier_id=dossier.dossier_id, step=dossier.step.value, status=dossier.status.value,
        error_code=dossier.error_code, causes=outcome.causes, confidence=outcome.confidence,
        abstained=outcome.abstained, escalation_reason=outcome.escalation_reason,
        path=chemin, citations=citations, trace_id=trace_id,
        etat_csa=world.etat_csa if facts["syn.ecart_referentiels"].value else None)

    ancrage = verify.verifier(provider, texte_client=explication_client.fr,
                              citations=citations, path=chemin, cause_id=cause_tete)
    session.audit.append("verify", ancrage.model_dump())

    actions: list[str] = []
    for c in outcome.causes:
        for a in node_of(c.cause_id).get("allowed_actions", []):
            if a not in actions:
                actions.append(a)
    if outcome.human_validation_required and "preparer_escalade" not in actions:
        actions.append("preparer_escalade")

    candidats = [to_candidate(c, confidence=policy.calibrate(c.score)) for c in outcome.causes]
    if outcome.cause_indeterminee:
        # Le repli sûr est une conclusion à part entière : il figure en tête,
        # avec les hypothèses non tranchées conservées en dessous. Une escalade
        # pour cause CONNUE (manipulation, doublon…) garde sa cause en tête.
        meta = CAUSE_BY_ID["C-UNK-000"]
        candidats.insert(0, CauseCandidate(
            cause_id="C-UNK-000", family=meta["family"], label_fr=meta["label_fr"],
            confidence=round(outcome.confidence, 4), owner=Owner(meta["owner"]),
            evidence=[], anchors=node_of("C-UNK-000")["anchors"]))

    trace = Trace(
        facts=[e for c in outcome.causes for e in c.evidence],
        graph_scores={c.cause_id: c.score for c in ranked[:8]},
        retrieved_anchors=[c.anchor for c in citations],
        tool_calls=[ToolCallRecord(**r) for r in session.calls],
        policy_decisions=outcome.decisions,
        adjudicated=bool(arbitrage and arbitrage.get("cause_id")),
        adjudication_reason=(arbitrage or {}).get("justification") if arbitrage else (raison or None),
        groundedness_score=ancrage.score,
        audit_chain_head=session.audit.head,
        latency_ms=int((time.monotonic() - t0) * 1000),
        provider=provider.name,
        cost_usd=round(provider.usage.cost_usd, 6),
    )

    diag = Diagnosis(
        trace_id=trace_id, dossier_id=dossier.dossier_id, step=Step(dossier.step.value),
        status=Status(dossier.status.value), error_code=dossier.error_code,
        causes=candidats[:THRESHOLDS["max_causes_returned"]],
        unblock_path=chemin,
        explanation_client=explication_client, explanation_agent=explication_agent,
        sources=citations, allowed_actions=actions,
        human_validation_required=outcome.human_validation_required,
        confidence=outcome.confidence, abstained=outcome.abstained, trace=trace,
    )
    session.audit.append("diagnosis", {"cause": diag.top_cause, "confiance": diag.confidence,
                                       "abstention": diag.abstained})
    return diag, session
