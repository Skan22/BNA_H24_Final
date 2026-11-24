"""Cohérence des contrats. Ces tests protègent les invariants de conception :
s'ils cassent, ce n'est pas un détail, c'est la garantie anti-hallucination
qui a cédé."""
import re
import pathlib

import yaml

from engine.graph import CAUSE_BY_ID, GRAPH, NODE_BY_ID
from engine.rag.corpus import CORPUS

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_graphe_et_contrat_couvrent_les_memes_causes():
    assert set(NODE_BY_ID) == set(CAUSE_BY_ID), "graphe et contrat de causes ont divergé"


def test_toute_ancre_citee_existe_dans_le_corpus():
    """Une citation vers une règle inexistante serait une hallucination
    structurelle : le pire défaut possible pour ce système."""
    citees = {a for n in GRAPH["nodes"] for a in n.get("anchors", [])}
    citees |= {a for n in GRAPH["nodes"] for s in n.get("remediation", []) for a in s.get("anchors", [])}
    assert citees <= set(CORPUS.rules), f"ancres introuvables : {sorted(citees - set(CORPUS.rules))}"


def test_toute_cause_a_au_moins_une_ancre():
    for cid, node in NODE_BY_ID.items():
        assert node.get("anchors"), f"{cid} ne cite aucune règle"


def test_toute_cause_a_une_remediation():
    for cid, node in NODE_BY_ID.items():
        assert node.get("remediation"), f"{cid} ne propose aucune suite"


def test_poids_des_aretes_coherents():
    """La somme des poids d'un nœud borne son score : au-delà de 1, la
    confiance annoncée n'aurait plus de sens."""
    for cid, node in NODE_BY_ID.items():
        total = sum(e["weight"] for e in node.get("evidence", []))
        assert total <= 1.0001, f"{cid} : somme des poids = {total}"


def test_les_faits_references_sont_produits_par_signals():
    """Une arête qui référencerait un fait que personne ne produit serait
    morte, et le nœud ne se déclencherait jamais."""
    source = (ROOT / "engine" / "signals.py").read_text()
    produits = set(re.findall(r'put\("([^"]+)"', source))
    references = {c["fact"] for n in GRAPH["nodes"]
                  for c in n.get("evidence", []) + n.get("inhibits", [])}
    references |= {r for n in GRAPH["nodes"] for r in n.get("requires", [])}
    assert references <= produits, f"faits jamais produits : {sorted(references - produits)}"


def test_le_manifeste_couvre_tous_les_outils_appeles():
    manifeste = yaml.safe_load((ROOT / "contracts" / "tools.manifest.yaml").read_text())
    declares = {t["name"] for t in manifeste["tools"]}
    appeles = set(re.findall(r'(?:try_call|call)\("([a-z0-9_.]+)"',
                             (ROOT / "engine" / "pipeline.py").read_text()
                             + (ROOT / "api" / "main.py").read_text()))
    assert appeles <= declares, f"outils appelés hors manifeste : {sorted(appeles - declares)}"


def test_aucune_ecriture_hors_escalade():
    manifeste = yaml.safe_load((ROOT / "contracts" / "tools.manifest.yaml").read_text())
    ecritures = [t for t in manifeste["tools"] if t["mode"] == "write"]
    assert [t["name"] for t in ecritures] == ["csa.create_escalation"]
    assert ecritures[0]["requires_human_ack"] is True
