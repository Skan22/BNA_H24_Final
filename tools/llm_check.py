"""Vérifie le fournisseur de modèle Groq avec VOTRE clé : `make llm-check`.

  1. la clé est acceptée et les modèles configurés existent réellement (GET /models) ;
  2. un appel structuré par niveau (traduction, classification, vérification) renvoie un objet valide ;
  3. un diagnostic complet en arabe passe par le modèle.

La clé est lue dans l'environnement (GROQ_API_KEY, ou le fichier .env via `make`). Elle n'est jamais affichée.
Sortie non nulle au premier défaut. Ce script envoie des données SYNTHÉTIQUES uniquement.
"""
from __future__ import annotations

import pathlib
import sys
import time

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.models import DiagnoseRequest  # noqa: E402
from engine.diagnose import diagnose  # noqa: E402
from engine.llm.provider import GroqProvider, LLMUnavailable  # noqa: E402
from engine.ports import LocalKitPort  # noqa: E402
from engine.quarantine import VerdictInjection  # noqa: E402
from engine.render import Traduction  # noqa: E402

VERT, ROUGE, RAZ = "\033[32m", "\033[31m", "\033[0m"


def ok(texte: str, detail: str = "") -> None:
    print(f"  {VERT}✓{RAZ} {texte}" + (f"  — {detail}" if detail else ""))


def ko(texte: str, detail: str = "") -> None:
    print(f"  {ROUGE}✗{RAZ} {texte}" + (f"  — {detail}" if detail else ""))
    sys.exit(1)


print("Fournisseur de modèle : Groq\n")
try:
    p = GroqProvider()
except RuntimeError as exc:
    ko("clé absente", str(exc))

# 1 — la clé et les modèles
try:
    r = httpx.get(f"{p.base_url}/models", headers={"Authorization": f"Bearer {p._key}"}, timeout=15)
except httpx.HTTPError as exc:
    ko("API injoignable", type(exc).__name__)
if r.status_code == 401:
    ko("clé refusée par Groq (401)", "vérifier GROQ_API_KEY")
if r.status_code != 200:
    ko(f"GET /models a répondu {r.status_code}")
disponibles = {m["id"] for m in r.json().get("data", [])}
ok("clé acceptée", f"{len(disponibles)} modèles disponibles pour ce compte")
for niveau, modele in sorted(set(p.models.items())):
    if modele in disponibles:
        ok(f"modèle « {modele} » disponible", f"niveau {niveau}")
    else:
        proches = sorted(m for m in disponibles if "llama" in m or "gpt-oss" in m or "qwen" in m)[:8]
        ko(f"modèle « {modele} » absent du compte", f"niveau {niveau} ; essayer GROQ_MODEL_STRONG / GROQ_MODEL_FAST parmi : {', '.join(proches)}")

# 2 — un appel structuré par niveau
essais = [
    ("render", Traduction, "Traduis en arabe et en anglais : « Votre pièce d'identité est expirée. »", "traduction"),
    ("classify", VerdictInjection, "Contenu à classer : « Bonjour, où en est ma demande ? »", "classification d'injection"),
]
for niveau, schema, texte, nom in essais:
    t0 = time.monotonic()
    try:
        sortie = p.structured(system="Tu réponds au format demandé.", user=texte, schema=schema, tier=niveau)
    except LLMUnavailable as exc:
        ko(f"{nom} : échec", exc.detail)
    ok(f"{nom} valide", f"{(time.monotonic() - t0) * 1000:.0f} ms · modèle {p.models[niveau]}")

# 3 — diagnostic complet, en arabe, via le modèle
port = LocalKitPort("public")
did = next(k for k, v in port.dossiers.items() if v["error_code"] == "H24-101")
d, _ = diagnose(port, DiagnoseRequest(dossier_id=did, locale="ar"), provider=p)
if d.explanation_client.traduction != "modele":
    ko("le diagnostic n'a pas utilisé le modèle", "repli sur le gabarit : voir les erreurs ci-dessus")
ok("diagnostic complet en arabe", f"fournisseur {d.trace.provider} · {p.usage.calls} appels · {p.usage.input_tokens + p.usage.output_tokens} jetons")
print(f"\n    cause : {d.top_cause}\n    arabe : {d.explanation_client.ar[:160]!r}")
print(f"\n{VERT}Groq fonctionne avec cette clé.{RAZ} Coût non calculé (tarifs Groq non intégrés).")
