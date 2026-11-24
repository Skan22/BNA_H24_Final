"""Comportement du moteur : déterminisme, repli sûr, ancrage, conformité."""
import json
import pathlib

import pytest

from contracts.models import Diagnosis, DiagnoseRequest
from engine.diagnose import diagnose
from engine.ports import LocalKitPort
from engine.signals import SEUIL_OCR_LISIBLE

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def port():
    return LocalKitPort("public")


@pytest.fixture(scope="module")
def gt():
    return json.loads((ROOT / "kit" / "scenarios" / "public" / "ground_truth.json").read_text())


def dossier_pour(gt, cause_id):
    return next(k for k, g in gt.items() if g["cause_id"] == cause_id)


def test_diagnostic_conforme_au_contrat(port, gt):
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-IDN-001")))
    Diagnosis.model_validate(diag.model_dump())


def test_deterministe(port, gt):
    """Mêmes entrées, mêmes sorties. Sans cela, aucune trace n'est rejouable."""
    req = DiagnoseRequest(dossier_id=dossier_pour(gt, "C-DOC-001"))
    a, _ = diagnose(port, req)
    b, _ = diagnose(port, req)
    assert a.top_cause == b.top_cause
    assert a.confidence == b.confidence
    assert [s.anchor for s in a.sources] == [s.anchor for s in b.sources]
    assert [s.action for s in a.unblock_path] == [s.action for s in b.unblock_path]


def test_la_cause_vient_toujours_du_referentiel(port):
    """Aucune cause ne peut être produite hors de la liste fermée."""
    from engine.graph import CAUSE_BY_ID
    for did in list(port.dossiers)[:40]:
        diag, _ = diagnose(port, DiagnoseRequest(dossier_id=did))
        for c in diag.causes:
            assert c.cause_id in CAUSE_BY_ID


def test_toute_reponse_cite_au_moins_une_regle(port):
    for did in list(port.dossiers)[:40]:
        diag, _ = diagnose(port, DiagnoseRequest(dossier_id=did))
        assert diag.sources, f"{did} ne cite aucune règle"


def test_ancrage_structurel_toujours_valide(port):
    """Chaque action proposée doit venir du graphe, chaque ancre du corpus."""
    for did in list(port.dossiers)[:40]:
        diag, _ = diagnose(port, DiagnoseRequest(dossier_id=did))
        assert diag.trace.groundedness_score == 1.0, f"{did} : ancrage rompu"


def test_repli_sur_sur_donnees_contradictoires(port, gt):
    """R-SEC-005 : face à plusieurs causes également plausibles, on s'arrête."""
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-UNK-000")))
    assert diag.abstained
    assert diag.human_validation_required
    assert diag.causes[0].cause_id == "C-UNK-000"


def test_escalade_pour_cause_connue_garde_sa_cause(port, gt):
    """Une manipulation détectée escalade, mais la cause reste identifiée :
    la confondre avec une indétermination ferait perdre l'information au triage."""
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-SEC-001")))
    assert diag.abstained and diag.causes[0].cause_id == "C-SEC-001"


def test_le_client_ne_voit_ni_code_ni_jargon(port, gt):
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-OTP-001")))
    texte = diag.explanation_client.fr
    for jargon in ("H24-", "C-OTP", "cause_id", "R-OTP", "score"):
        assert jargon not in texte, f"jargon « {jargon} » exposé au client"


def test_l_agent_voit_le_code_et_la_regle(port, gt):
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-OTP-001")))
    resume = diag.explanation_agent.summary
    assert "C-OTP-001" in resume and "R-OTP-003" in resume


def test_note_d_escalade_presente_quand_requise(port, gt):
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-DUP-001")))
    assert diag.human_validation_required
    note = diag.explanation_agent.escalation_draft
    assert note and diag.trace_id in note and "R-ESC-003" in note


def test_code_generique_signale_comme_tel(port):
    """Le code H24-000 ne désigne rien : l'agent doit le savoir (R-GEN-020)."""
    did = next(k for k, v in port.dossiers.items() if v["error_code"] == "H24-000")
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=did))
    assert "générique" in diag.explanation_agent.summary


def test_silence_du_csa_n_est_pas_une_desynchronisation(port):
    """Le CSA muet ne doit pas produire un incident inventé (R-SYN-004)."""
    from engine.pipeline import build_worldview, open_session, run_deterministic
    muets = [k for k in port.dossiers if port.get_etat_csa(k) is None]
    assert muets, "le kit doit contenir des dossiers au CSA muet"
    for did in muets[:5]:
        s, b, d = open_session(port, did, "t")
        facts, _, _ = run_deterministic(d, build_worldview(b, d))
        assert facts["syn.ecart_referentiels"].value is False


def test_ocr_illisible_n_est_pas_une_incoherence(port):
    """Une pièce illisible relève de R-DOC-004, pas de R-IDN-004 : on ne peut
    pas constater une divergence sur un texte qu'on ne lit pas."""
    from engine.pipeline import build_worldview, open_session, run_deterministic
    for did, raw in port.dossiers.items():
        if any((d.get("ocr_confidence") or 1) < SEUIL_OCR_LISIBLE for d in raw["documents"]):
            s, b, d = open_session(port, did, "t")
            facts, _, _ = run_deterministic(d, build_worldview(b, d))
            if facts["ident.incoherence_formulaire"].value:
                pieces = [x for x in d.documents if x.type.value in ("CIN", "PASSEPORT")]
                assert all((p.ocr_confidence or 1) >= SEUIL_OCR_LISIBLE for p in pieces)


def test_alternatives_proposees_en_cas_de_refus_d_offre(port, gt):
    """R-OFR-016 : un refus sans alternative est une cause d'abandon évitable."""
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-OFR-003")))
    assert any("éligible" in s.action for s in diag.unblock_path)
