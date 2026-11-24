"""Contrat d'un port de données : à lancer sur TOUT nouvel adaptateur avant de le brancher.

    from engine.port_contract import verifier_port
    verifier_port(MonPortBna(), dossier_id="...")      # lève AssertionError avec le défaut précis

Ne vérifie que la FORME (méthodes présentes, dossier conforme au modèle `Dossier`, types de retour). La justesse des
données reste à valider avec les métiers.
"""
from __future__ import annotations

from contracts.models import Dossier
from engine.ports import DataPort


def verifier_port(port, dossier_id: str) -> None:
    assert isinstance(port, DataPort), "le port n'implémente pas toutes les méthodes de DataPort"
    raw = port.get_dossier(dossier_id)
    assert raw is not None, f"get_dossier({dossier_id!r}) a renvoyé None"
    dossier = Dossier.model_validate(raw)                     # lève si un champ attendu manque ou a un mauvais type
    identite = dossier.prospect.cin or dossier.prospect.passeport
    assert port.get_dossier("DOS-ZZZ-000000") is None, "un dossier inconnu doit renvoyer None, pas lever"
    for nom, valeur in {
        "list_dossiers": port.list_dossiers(5), "get_events": port.get_events(dossier_id),
        "get_subscriptions": port.get_subscriptions(identite), "get_relations": port.get_relations(identite),
        "search_duplicates": port.search_duplicates(dossier_id),
    }.items():
        assert isinstance(valeur, list), f"{nom} doit renvoyer une liste"
    for nom, valeur in {"get_etat_csa": port.get_etat_csa(dossier_id),
                        "get_agency_queue": port.get_agency_queue(dossier.agence.code_agence)}.items():
        assert valeur is None or isinstance(valeur, dict), f"{nom} doit renvoyer un dict ou None (source muette)"
    # Un doublon ne doit jamais exposer l'index complet : seuls les dossiers liés à CELUI-CI reviennent.
    assert all(d.get("dossier_id") != dossier_id for d in port.search_duplicates(dossier_id)), \
        "search_duplicates ne doit pas renvoyer le dossier lui-même"
