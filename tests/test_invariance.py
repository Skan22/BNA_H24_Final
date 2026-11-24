"""Propriétés que tout diagnostic doit garder, sur les 149 dossiers du kit public.

Un moteur qui n'est correct que dans l'ordre où le kit écrit les champs, ou qui change d'avis selon une
question anodine, ne mérite pas de confiance même avec 100 % sur la vérité terrain."""
import copy
import random

import pytest

from contracts.models import DiagnoseRequest
from engine.diagnose import diagnose
from engine.llm.provider import resolve
from engine.ports import LocalKitPort

PROVIDER = resolve("none")


@pytest.fixture(scope="module")
def port():
    return LocalKitPort("public")


def run(port, did, question=None):
    d, _ = diagnose(port, DiagnoseRequest(dossier_id=did, question=question), provider=PROVIDER)
    return d


def signature(d):
    return ([(c.cause_id, c.confidence) for c in d.causes], [s.action for s in d.unblock_path],
            d.human_validation_required, d.abstained, [s.anchor for s in d.sources])


def test_determinisme(port):
    for did in port.dossiers:
        assert signature(run(port, did)) == signature(run(port, did)), did


def test_l_ordre_des_documents_et_des_evenements_ne_change_rien(port):
    rnd = random.Random(7)
    melange = LocalKitPort("public")
    melange.dossiers = copy.deepcopy(port.dossiers)
    for did, raw in melange.dossiers.items():
        rnd.shuffle(raw["documents"])
        rnd.shuffle(raw["events"])
    for did in port.dossiers:
        assert signature(run(port, did)) == signature(run(melange, did)), did


def test_une_question_anodine_ne_change_pas_le_diagnostic(port):
    for did in port.dossiers:
        base = run(port, did)
        if any(c.family == "F10" for c in base.causes):
            continue
        avec = run(port, did, "Où en est mon dossier ?")
        assert avec.top_cause == base.top_cause and avec.abstained == base.abstained, did


def test_aucune_cause_hors_referentiel_et_actions_connues(port):
    from engine.graph import CAUSE_BY_ID, NODE_BY_ID
    permises = {a for n in NODE_BY_ID.values() for a in n.get("allowed_actions", [])} | {"preparer_escalade"}
    for did in port.dossiers:
        d = run(port, did)
        assert all(c.cause_id in CAUSE_BY_ID for c in d.causes), did
        assert set(d.allowed_actions) <= permises, did


@pytest.mark.parametrize("locale", ["ar", "en"])
def test_hors_ligne_le_gabarit_localise_ne_revele_rien_et_nomme_la_cause(port, locale):
    from engine.graph import label
    for did in list(port.dossiers)[:60]:
        d, _ = diagnose(port, DiagnoseRequest(dossier_id=did, locale=locale), provider=PROVIDER)
        txt = getattr(d.explanation_client, locale)
        assert txt and d.explanation_client.traduction == "gabarit"
        if any(c.family == "F10" for c in d.causes):
            assert not any(c.label_fr in txt or label(c.cause_id, locale) in txt for c in d.causes), did
        elif d.causes and not d.abstained:
            assert label(d.causes[0].cause_id, locale) in txt, did
