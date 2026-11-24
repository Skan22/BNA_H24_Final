"""Étape « choix de l'agence » : parcours, causes, bornage par étape, alternatives, cohérence web/docs."""
import json
import pathlib
import re

import pytest

from contracts.models import DiagnoseRequest, Step
from engine.diagnose import diagnose
from engine.llm.provider import resolve
from engine.ports import LocalKitPort
from engine.rag.corpus import CORPUS

ROOT = pathlib.Path(__file__).resolve().parents[1]
PORT = LocalKitPort("public")
GT = json.loads((ROOT / "kit/scenarios/public/ground_truth.json").read_text())
CAT = json.loads((ROOT / "kit/catalog.json").read_text())
FERMEES = {a["code"] for a in CAT["agences"] if a["statut"] != "ouverte"}
SANS_NR = {a["code"] for a in CAT["agences"] if not a["accueille_non_residents"]}


def diag(did, **kw):
    d, _ = diagnose(PORT, DiagnoseRequest(dossier_id=did, **kw), provider=resolve("none"))
    return d


def dossiers_de(cause):
    return [k for k, g in GT.items() if g["cause_id"] == cause and "variante" not in g]


def test_le_choix_de_l_agence_est_la_deuxieme_etape_du_parcours():
    ordre = [s.value for s in Step]
    assert ordre[:3] == ["ORIENTATION", "CHOIX_AGENCE", "IDENTITE"]
    # l'interface et le corpus décrivent le même parcours que le contrat
    web = (ROOT / "web/lib/api.js").read_text()
    assert re.findall(r'"([A-Z_]+)"', re.search(r"ETAPES = \[(.*?)\]", web, re.S).group(1)) == ordre
    texte = " ".join(CORPUS.rules["R-GEN-001"].texte.split())
    assert ", ".join(ordre[:-1]) + ", " + ordre[-1] in texte.replace(" et ", ", ")


@pytest.mark.parametrize("cause,etape", [("C-AGE-001", "CHOIX_AGENCE"), ("C-AGE-002", "CHOIX_AGENCE"),
                                         ("C-AGE-003", "CHOIX_AGENCE"), ("C-AGE-004", "CHOIX_AGENCE"),
                                         ("C-AGE-005", "SIGNATURE")])
def test_chaque_cause_de_la_famille_est_diagnostiquee_avec_ses_regles(cause, etape):
    ids = dossiers_de(cause)
    assert ids, f"le kit ne contient aucun dossier {cause}"
    for did in ids:
        d = diag(did)
        assert d.top_cause == cause and d.step.value == etape and not d.abstained, did
        assert {a for a in GT[did]["expected_anchors"]} <= {s.anchor for s in d.sources}, did


def test_un_code_d_agence_inconnu_va_au_back_office_et_ne_demande_rien_au_client():
    d = diag(dossiers_de("C-AGE-004")[0])
    assert d.human_validation_required and d.causes[0].owner.value == "back_office"
    assert not [s for s in d.unblock_path if s.owner.value == "client"]
    assert "recommenc" not in d.explanation_client.fr.lower()


def test_les_alternatives_proposees_sont_ouvertes_et_adaptees_au_profil():
    for cause in ("C-AGE-002", "C-AGE-003"):
        for did in dossiers_de(cause):
            ligne = next(s.action for s in diag(did).unblock_path if s.action.startswith("Agences ouvertes"))
            codes = set(re.findall(r"AG-\d{4}", ligne))
            assert codes and not codes & FERMEES and not codes & SANS_NR, (did, ligne)


def test_la_borne_d_etape_evite_les_fausses_alertes():
    """Une agence fermée ou sans service non-résidents ne bloque que l'étape de choix."""
    for did, g in GT.items():
        d = diag(did)
        causes = {c.cause_id for c in d.causes}
        if d.step.value not in ("CHOIX_AGENCE", "SIGNATURE"):
            assert not {c for c in causes if c.startswith("C-AGE")}, (did, causes)
        if g["cause_id"] != "C-SYN-002" or "variante" not in g:
            continue
        assert "C-AGE-005" not in causes, did        # signature déjà signée : pas de finalisation en agence


def test_le_texte_client_nomme_l_etape_dans_les_trois_langues():
    did = dossiers_de("C-AGE-002")[0]
    assert "choix de votre agence" in diag(did).explanation_client.fr
    for loc, attendu in (("ar", "اختيار الوكالة"), ("en", "choosing your branch")):
        assert attendu in getattr(diag(did, locale=loc).explanation_client, loc)


def test_le_client_voit_une_etape_agence_sans_information_interne():
    from api.projection import client_diagnosis
    d = diag(dossiers_de("C-AGE-004")[0])
    v = json.dumps(client_diagnosis(d))
    assert not re.search(r"\bC-[A-Z]{3}-\d{3}\b", v) and "AG-9999" not in v
