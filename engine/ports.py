"""BOUSSOLA — couture d'adaptation vers les sources de données.

Le moteur ne connaît que cette interface. Le kit officiel de la BNA, s'il
arrive, se branche en écrivant un nouveau port : aucun autre fichier du moteur
ne change.
"""
from __future__ import annotations

import json
import os
import pathlib
from typing import Protocol, runtime_checkable

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]


@runtime_checkable
class DataPort(Protocol):
    def get_dossier(self, dossier_id: str) -> dict | None: ...
    def list_dossiers(self, limit: int) -> list[dict]: ...
    def get_events(self, dossier_id: str) -> list[dict]: ...
    def get_document_ocr(self, dossier_id: str, doc_id: str) -> dict | None: ...
    def get_subscriptions(self, identite: str | None) -> list[dict]: ...
    def get_relations(self, identite: str | None) -> list[dict]: ...
    def search_duplicates(self, dossier_id: str) -> list[dict]: ...
    def get_etat_csa(self, dossier_id: str) -> dict | None: ...
    def get_agency_queue(self, code_agence: str | None) -> dict | None: ...


class LocalKitPort:
    """Lit directement les fichiers du kit. Utilisé par l'évaluateur et les tests.

    Rapide et hors réseau : l'évaluation de 128 dossiers ne doit pas dépendre
    de deux serveurs HTTP.
    """

    def __init__(self, split: str = "public"):
        base = ROOT / "kit" / "scenarios" / split
        self.split = split
        self.dossiers = {d["dossier_id"]: d for d in json.loads((base / "dossiers.json").read_text())}
        self.csa = json.loads((base / "csa_state.json").read_text())

    def get_dossier(self, dossier_id):
        return self.dossiers.get(dossier_id)

    def list_dossiers(self, limit: int = 200):
        return [{"dossier_id": k, "step": v["step"], "status": v["status"],
                 "error_code": v["error_code"],
                 "prospect": f"{v['prospect']['prenom']} {v['prospect']['nom']}",
                 "pack": (v.get("offre") or {}).get("pack_code")}
                for k, v in list(self.dossiers.items())[:limit]]

    def get_events(self, dossier_id):
        d = self.dossiers.get(dossier_id)
        return d["events"] if d else []

    def get_document_ocr(self, dossier_id, doc_id):
        d = self.dossiers.get(dossier_id) or {}
        for doc in d.get("documents", []):
            if doc["doc_id"] == doc_id:
                return {"doc_id": doc_id, "type": doc["type"],
                        "ocr_confidence": doc.get("ocr_confidence"), "texte": doc.get("ocr_text")}
        return None

    def get_subscriptions(self, identite):
        return [s for s in self.csa.get("subscriptions", []) if identite and s.get("identite") == identite]

    def get_relations(self, identite):
        return [r for r in self.csa.get("relations", []) if identite and r.get("cin") == identite]

    def search_duplicates(self, dossier_id):
        """Dossiers partageant identité, courriel ou téléphone avec celui de la session.

        Le rapprochement est fait ICI, côté source, pour que le moteur ne voie
        jamais l'index complet des dossiers (R-SEC-003).
        """
        moi = self.dossiers.get(dossier_id)
        if not moi:
            return []
        p = moi["prospect"]
        out = []
        for x in self.csa.get("dossiers_index", []):
            if x["dossier_id"] == dossier_id:
                continue
            if ((p.get("cin") and x.get("cin") == p["cin"])
                    or (x.get("email") and x["email"] == p["email"])
                    or (x.get("telephone") and x["telephone"] == p["telephone"])):
                out.append(x)
        return out

    def get_etat_csa(self, dossier_id):
        return self.csa.get("etats", {}).get(dossier_id)

    def get_agency_queue(self, code_agence):
        return self.csa.get("agency_queue", {}).get(code_agence)


class HttpPort:
    """Passe par les deux API simulées (services/mock_h24, services/mock_csa).

    C'est le chemin utilisé par la démonstration : il montre que le moteur
    n'a aucun accès privilégié aux données.
    """

    def __init__(self, h24: str | None = None, csa: str | None = None, timeout: float = 4.0):
        # Configurables : sur un poste où d'autres services occupent déjà 8001/8002,
        # pointer ailleurs ne doit pas demander de modifier le code.
        h24 = h24 or os.getenv("BOUSSOLA_H24", "http://127.0.0.1:8001")
        csa = csa or os.getenv("BOUSSOLA_CSA", "http://127.0.0.1:8002")
        self.h24, self.csa_url = h24.rstrip("/"), csa.rstrip("/")
        self.client = httpx.Client(timeout=timeout, follow_redirects=False,
                                   headers={"X-Mock-Key": os.getenv("BOUSSOLA_MOCK_KEY", "local-mock-change-me")})

    def _get(self, url: str):
        r = self.client.get(url)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def get_dossier(self, dossier_id):
        return self._get(f"{self.h24}/dossiers/{dossier_id}")

    def list_dossiers(self, limit: int = 200):
        return self._get(f"{self.h24}/dossiers?limit={limit}") or []

    def get_events(self, dossier_id):
        return self._get(f"{self.h24}/dossiers/{dossier_id}/events") or []

    def get_document_ocr(self, dossier_id, doc_id):
        return self._get(f"{self.h24}/dossiers/{dossier_id}/documents/{doc_id}/ocr")

    def get_subscriptions(self, identite):
        return self._get(f"{self.csa_url}/subscriptions?identite={identite or ''}") or []

    def get_relations(self, identite):
        return self._get(f"{self.csa_url}/relations?identite={identite or ''}") or []

    def search_duplicates(self, dossier_id):
        return self._get(f"{self.csa_url}/duplicates?dossier_id={dossier_id}") or []

    def get_etat_csa(self, dossier_id):
        return self._get(f"{self.csa_url}/etats/{dossier_id}")

    def get_agency_queue(self, code_agence):
        return self._get(f"{self.csa_url}/agency-queue/{code_agence}")
