"""Intégration du modèle de langage, éprouvée sans clé d'API.

Un fournisseur factice joue le rôle du modèle. Cela permet de vérifier ce qui
compte vraiment : que le moteur **encadre** correctement le modèle — qu'il
rejette une cause hors liste, qu'il n'exécute jamais une consigne trouvée dans
un document, et qu'une panne du modèle dégrade proprement au lieu de casser.

Ces garanties ne dépendent pas de la qualité du modèle, et c'est exactement le
but : elles tiennent quel que soit le modèle branché derrière.
"""
import json
import pathlib

import pytest

from contracts.models import DiagnoseRequest
from engine.diagnose import diagnose
from engine.llm.provider import LLMUnavailable, Usage
from engine.ports import LocalKitPort
from engine.quarantine import VerdictInjection
from engine.render import Traduction

ROOT = pathlib.Path(__file__).resolve().parents[1]


class FauxProvider:
    """Répond selon le schéma demandé. `scenario` pilote ce qu'il renvoie."""

    def __init__(self, scenario="normal", cause_arbitree=None):
        self.name = "faux"
        self.usage = Usage()
        self.scenario = scenario
        self.cause_arbitree = cause_arbitree
        self.appels = []

    def structured(self, *, system, user, schema, tier):
        self.appels.append((tier, schema.__name__, user))
        if self.scenario == "panne":
            raise LLMUnavailable("panne simulée")
        if schema is VerdictInjection:
            return VerdictInjection(verdict="propre", cible="aucune", motif="contenu ordinaire")
        if schema is Traduction:
            return Traduction(ar="نص مترجم", en="translated text")
        if schema.__name__ == "Arbitrage":
            if self.cause_arbitree is None:
                return schema(indetermine=True, cause_id=None,
                              justification="les faits ne départagent pas", niveau="faible")
            return schema(indetermine=False, cause_id=self.cause_arbitree,
                          justification="soutenu par les faits", niveau="fort")
        if schema.__name__ == "_Entailment":
            return schema(phrases_non_soutenues=[], score=1.0)
        raise AssertionError(f"schéma inattendu : {schema.__name__}")


@pytest.fixture(scope="module")
def port():
    return LocalKitPort("public")


@pytest.fixture(scope="module")
def gt():
    return json.loads((ROOT / "kit" / "scenarios" / "public" / "ground_truth.json").read_text())


def dossier_pour(gt, cause_id):
    return next(k for k, g in gt.items() if g["cause_id"] == cause_id)


def test_le_modele_est_appele_pour_traduire(port, gt):
    p = FauxProvider()
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-IDN-001"), locale="ar"), provider=p)
    assert diag.explanation_client.ar == "نص مترجم"
    assert diag.explanation_client.fr, "le français reste produit par gabarit"
    assert any(t == "render" for t, _, _ in p.appels)


def test_une_cause_hors_liste_est_rejetee(port, gt):
    """Le garde-fou décisif : si le modèle propose un identifiant absent des
    candidats, il est traité comme une non-réponse, jamais comme une cause."""
    p = FauxProvider(cause_arbitree="C-INVENTEE-999")
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-UNK-000")), provider=p)
    assert all(c.cause_id != "C-INVENTEE-999" for c in diag.causes)
    assert diag.abstained, "une non-réponse doit conduire au repli sûr"


def dossier_ambigu_sans_contradiction(port):
    """Ambiguïté PURE : familles concurrentes, mais référentiels d'accord.

    Le distinguo importe : quand H24 et le CSA se contredisent, on s'arrête pour
    cette raison-là (R-SYN-004), et l'arbitrage ne doit pas pouvoir passer outre.
    L'arbitrage n'a de terrain que lorsque l'ambiguïté est la seule difficulté.
    """
    from engine.pipeline import build_worldview, open_session, run_deterministic
    for did in port.dossiers:
        s, b, d = open_session(port, did, "t")
        facts, ranked, (ambigu, _) = run_deterministic(d, build_worldview(b, d))
        if ambigu and not facts["syn.ecart_referentiels"].value:
            return did, ranked
    pytest.skip("aucun dossier ambigu sans contradiction dans ce kit")


def test_l_arbitrage_tranche_une_vraie_ambiguite(port):
    """Quand le modèle départage, la cause retenue vient des candidats du graphe."""
    did, ranked = dossier_ambigu_sans_contradiction(port)
    choix = ranked[1].cause_id                       # un candidat qui n'est pas en tête
    p = FauxProvider(cause_arbitree=choix)
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=did), provider=p)
    assert diag.causes[0].cause_id == choix
    assert diag.trace.adjudicated
    assert not diag.abstained, "une ambiguïté tranchée ne doit plus déclencher le repli"


def test_l_arbitrage_ne_passe_pas_outre_une_contradiction(port, gt):
    """Garde-fou d'ordre : même si le modèle tranche, deux référentiels en
    désaccord imposent l'arrêt (R-SYN-004). Le modèle n'arbitre pas cela."""
    from engine.pipeline import build_worldview, open_session, run_deterministic
    cible = None
    for did in port.dossiers:
        s, b, d = open_session(port, did, "t")
        facts, ranked, (ambigu, _) = run_deterministic(d, build_worldview(b, d))
        if ambigu and facts["syn.ecart_referentiels"].value:
            cible = (did, ranked[1].cause_id)
            break
    if cible is None:
        pytest.skip("aucun dossier ambigu avec contradiction dans ce kit")
    did, choix = cible
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=did), provider=FauxProvider(cause_arbitree=choix))
    assert diag.abstained, "la contradiction entre référentiels prime sur l'arbitrage"


def test_le_modele_n_est_pas_appele_sans_ambiguite(port, gt):
    """Économie et sûreté : pas d'appel d'arbitrage quand le graphe est net."""
    p = FauxProvider()
    diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-IDN-001")), provider=p)
    assert not any(t == "adjudicate" for t, _, _ in p.appels)


def test_panne_du_modele_degrade_proprement(port, gt):
    """Le modèle tombe : le diagnostic déterministe doit rester complet."""
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-IDN-001"), locale="ar"),
                       provider=FauxProvider(scenario="panne"))
    assert diag.causes[0].cause_id == "C-IDN-001"
    assert diag.explanation_client.fr
    assert diag.explanation_client.traduction == "gabarit", "hors ligne : gabarit annoncé, pas une traduction inventée"
    assert diag.explanation_client.ar and diag.explanation_client.ar != diag.explanation_client.fr
    assert diag.sources


def test_le_contenu_non_fiable_est_encapsule(port, gt):
    """Ce qui part au modèle doit toujours être étiqueté comme donnée inerte."""
    p = FauxProvider()
    diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-SEC-001")), provider=p)
    envois = [u for t, _, u in p.appels if t == "classify"]
    assert envois, "le contenu suspect doit être soumis au classifieur"
    for u in envois:
        assert "DÉBUT DONNÉE" in u and "fiabilité=untrusted" in u


def test_le_classifieur_ne_peut_pas_disculper_une_injection(port, gt):
    """Le classifieur dit « propre » sur un document manifestement piégé.
    Les motifs déterministes doivent tenir seuls : aucune couche ne peut
    annuler l'autre."""
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-SEC-001")),
                       provider=FauxProvider())      # répond toujours « propre »
    assert diag.causes[0].cause_id == "C-SEC-001"
    assert diag.human_validation_required


def test_le_cout_est_comptabilise(port, gt):
    p = FauxProvider()
    diag, _ = diagnose(port, DiagnoseRequest(dossier_id=dossier_pour(gt, "C-IDN-001")), provider=p)
    assert diag.trace.provider == "faux"
    assert diag.trace.cost_usd is not None
