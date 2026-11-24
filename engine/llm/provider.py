"""BOUSSOLA — accès au modèle de langage, derrière une interface unique.

Implémentations, choisies par la variable BOUSSOLA_LLM :

  groq       appel réel via l'API de Groq (compatible OpenAI) — fournisseur par défaut dès que
             GROQ_API_KEY est présente ; modèles réglables (GROQ_MODEL_STRONG / GROQ_MODEL_FAST)
  anthropic  appel réel via l'API d'Anthropic (conservé, non utilisé par défaut)
  ollama     repli local, pour une salle sans réseau
  cassette   rejoue des réponses enregistrées, indexées par empreinte de prompt
  none       aucun modèle : le moteur reste entièrement fonctionnel

La démonstration tourne en `cassette` : le jour du jury, le wifi ne doit pas
faire partie des dépendances. Les cassettes sont enregistrées en amont avec
BOUSSOLA_RECORD=1.

Toutes les sorties sont contraintes par un schéma Pydantic : le modèle ne rend
jamais du texte libre que l'on aurait ensuite à interpréter.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

ROOT = pathlib.Path(__file__).resolve().parents[2]
CASSETTES = ROOT / "engine" / "llm" / "cassettes"

T = TypeVar("T", bound=BaseModel)

# Un seul endroit où les modèles sont nommés.
MODELES = {
    "adjudicate": "claude-opus-5",     # arbitrage : la décision la plus sensible
    "classify": "claude-haiku-4-5",    # détection d'injection, appelée à chaque requête
    "verify": "claude-haiku-4-5",      # vérification d'ancrage
    "render": "claude-opus-5",         # reformulation client/agent
}
# $ / million de jetons (entrée, sortie), pour le rapport de coût.
TARIFS = {"claude-opus-5": (5.0, 25.0), "claude-haiku-4-5": (1.0, 5.0)}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0

    def add(self, model: str, inp: int, out: int, cached: int = 0) -> None:
        pin, pout = TARIFS.get(model, (0.0, 0.0))
        self.input_tokens += inp
        self.output_tokens += out
        self.cached_tokens += cached
        self.cost_usd += (inp * pin + out * pout) / 1_000_000
        self.calls += 1


@dataclass
class LLMUnavailable(Exception):
    """Levée quand aucun modèle n'est joignable.

    Ce n'est jamais fatal : l'appelant retombe sur le chemin déterministe et la
    politique de repli sûr s'applique. Un assistant sans modèle reste capable de
    diagnostiquer ; il est seulement moins disert.
    """

    detail: str = ""


def _key(system: str, user: str, model: str, schema: str) -> str:
    blob = json.dumps([system, user, model, schema], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


class CassetteProvider:
    """Rejoue à l'identique. Aucune sortie réseau, latence nulle, coût nul."""

    name = "cassette"

    def __init__(self, directory: pathlib.Path = CASSETTES):
        self.dir = directory
        self.usage = Usage()
        self.misses: list[str] = []

    def structured(self, *, system: str, user: str, schema: type[T], tier: str) -> T:
        model = MODELES[tier]
        k = _key(system, user, model, schema.__name__)
        path = self.dir / f"{k}.json"
        if not path.exists():
            self.misses.append(f"{tier}/{schema.__name__}/{k}")
            raise LLMUnavailable(f"cassette absente pour {tier} ({k})")
        payload = json.loads(path.read_text())
        self.usage.add(model, payload.get("input_tokens", 0), payload.get("output_tokens", 0))
        return schema.model_validate(payload["output"])


class AnthropicProvider:
    """Appel réel. Sorties contraintes par `messages.parse`, donc toujours valides."""

    name = "anthropic"

    def __init__(self, *, record: bool = False):
        import anthropic

        self.client = anthropic.Anthropic()
        self.usage = Usage()
        self.record = record
        if record:
            CASSETTES.mkdir(parents=True, exist_ok=True)

    def structured(self, *, system: str, user: str, schema: type[T], tier: str) -> T:
        import anthropic

        model = MODELES[tier]
        try:
            response = self.client.messages.parse(
                model=model,
                max_tokens=4096,
                # Le préambule est identique d'une requête à l'autre : on le met en
                # cache pour ne pas le repayer à chaque dossier évalué.
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                output_format=schema,
            )
        except anthropic.APIError as exc:
            raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc

        u = response.usage
        cached = getattr(u, "cache_read_input_tokens", 0) or 0
        self.usage.add(model, u.input_tokens, u.output_tokens, cached)
        parsed = response.parsed_output
        if parsed is None:
            raise LLMUnavailable("réponse non conforme au schéma demandé")
        if self.record:
            k = _key(system, user, model, schema.__name__)
            (CASSETTES / f"{k}.json").write_text(json.dumps(
                {"tier": tier, "model": model, "schema": schema.__name__,
                 "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                 "output": parsed.model_dump(mode="json")},
                indent=2, ensure_ascii=False) + "\n")
        return parsed


class GroqProvider:
    """Appel réel via Groq (API compatible OpenAI : https://api.groq.com/openai/v1).

    Sorties contraintes en deux temps : mode JSON de Groq (`json_object`, accepté par tous les modèles de
    chat) + schéma Pydantic en consigne, puis VALIDATION stricte ici. Une sortie invalide est redemandée une
    fois, puis devient `LLMUnavailable` : le moteur retombe alors sur le chemin déterministe. Le mode
    `json_schema` strict de Groq n'est volontairement pas utilisé : il n'est offert que sur certains modèles.

    La clé n'est lue que dans l'environnement (GROQ_API_KEY), jamais journalisée, jamais incluse dans une exception.
    """

    name = "groq"
    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self, *, api_key: str | None = None, client=None, timeout: float = 20.0):
        import httpx

        self._key = api_key or os.getenv("GROQ_API_KEY", "")
        if not self._key:
            raise RuntimeError("GROQ_API_KEY manquante : la définir dans l'environnement ou dans .env (jamais dans le code).")
        self.base_url = os.getenv("GROQ_BASE_URL", self.BASE_URL).rstrip("/")
        self.models = {
            "adjudicate": os.getenv("GROQ_MODEL_STRONG", "openai/gpt-oss-120b"),
            "render": os.getenv("GROQ_MODEL_STRONG", "openai/gpt-oss-120b"),
            "classify": os.getenv("GROQ_MODEL_FAST", "openai/gpt-oss-20b"),
            "verify": os.getenv("GROQ_MODEL_FAST", "openai/gpt-oss-20b"),
        }
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=False)
        self.usage = Usage()

    def __repr__(self) -> str:                       # jamais la clé
        return f"GroqProvider(models={self.models})"

    def _appel(self, model: str, system: str, user: str) -> tuple[str, dict]:
        import httpx

        try:
            r = self.client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
                json={"model": model, "temperature": 0, "max_tokens": 1024,
                      "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"groq injoignable : {type(exc).__name__}") from None
        if r.status_code != 200:
            # Le corps d'erreur de Groq peut citer la requête : on ne garde que le code.
            raise LLMUnavailable(f"groq a répondu {r.status_code}")
        try:
            corps = r.json()
            return corps["choices"][0]["message"]["content"], corps.get("usage", {}) or {}
        except (ValueError, KeyError, IndexError, TypeError):
            raise LLMUnavailable("réponse groq illisible") from None

    def structured(self, *, system: str, user: str, schema: type[T], tier: str) -> T:
        model = self.models[tier]
        consigne = (f"{system}\n\nRéponds UNIQUEMENT par un objet JSON valide, sans texte autour ni balises de code, "
                    f"conforme à ce schéma JSON ({schema.__name__}) :\n"
                    f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}")
        dernier = ""
        for tentative in range(2):
            contenu, u = self._appel(model, consigne if not dernier else consigne + f"\n\nTa réponse précédente était invalide ({dernier}). Corrige-la.", user)
            self.usage.add(model, u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
            texte = contenu.strip()
            if texte.startswith("```"):
                texte = texte.strip("`").removeprefix("json").strip()
            try:
                return schema.model_validate_json(texte)
            except Exception as exc:                 # noqa: BLE001 — toute non-conformité se traite pareil
                dernier = type(exc).__name__
        raise LLMUnavailable(f"sortie groq non conforme au schéma {schema.__name__}")


class OllamaProvider:
    """Repli local. Moins bon, mais disponible hors réseau."""

    name = "ollama"

    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen2.5:7b-instruct"):
        self.base_url, self.model, self.usage = base_url.rstrip("/"), model, Usage()

    def structured(self, *, system: str, user: str, schema: type[T], tier: str) -> T:
        import httpx

        consigne = (f"{system}\n\nRéponds UNIQUEMENT par un objet JSON conforme à ce schéma :\n"
                    f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}")
        try:
            r = httpx.post(f"{self.base_url}/api/chat", timeout=60.0, json={
                "model": self.model, "format": "json", "stream": False,
                "messages": [{"role": "system", "content": consigne},
                             {"role": "user", "content": user}]})
            r.raise_for_status()
            contenu = r.json()["message"]["content"]
        except Exception as exc:                      # réseau local, modèle absent…
            raise LLMUnavailable(f"ollama indisponible : {exc}") from exc
        self.usage.calls += 1
        try:
            return schema.model_validate_json(contenu)
        except Exception as exc:
            raise LLMUnavailable(f"sortie ollama non conforme : {exc}") from exc


@dataclass
class ChainProvider:
    """Essaie les fournisseurs dans l'ordre, retient le premier qui répond.

    Sert au mode démonstration : cassette d'abord (instantané), Anthropic ensuite
    si une question inédite est posée depuis la salle.
    """

    providers: list = field(default_factory=list)
    name: str = "chaine"

    def structured(self, **kw):
        dernier = None
        for p in self.providers:
            try:
                out = p.structured(**kw)
                self.name = f"chaine:{p.name}"
                return out
            except LLMUnavailable as exc:
                dernier = exc
        raise dernier or LLMUnavailable("aucun fournisseur disponible")

    @property
    def usage(self) -> Usage:
        total = Usage()
        for p in self.providers:
            u = p.usage
            total.input_tokens += u.input_tokens
            total.output_tokens += u.output_tokens
            total.cached_tokens += u.cached_tokens
            total.cost_usd += u.cost_usd
            total.calls += u.calls
        return total


class NullProvider:
    """Aucun modèle. Le moteur reste entièrement fonctionnel, en déterministe pur."""

    name = "aucun"
    usage = Usage()

    def structured(self, **_kw):
        raise LLMUnavailable("aucun fournisseur configuré (BOUSSOLA_LLM=none)")


def resolve(mode: str | None = None):
    mode = (mode or os.getenv("BOUSSOLA_LLM") or "auto").lower()
    record = os.getenv("BOUSSOLA_RECORD") == "1"
    if mode == "none":
        return NullProvider()
    if mode == "cassette":
        return CassetteProvider()
    if mode == "ollama":
        return OllamaProvider()
    if mode == "groq":
        return GroqProvider()                       # lève si GROQ_API_KEY manque : pas de repli silencieux
    if mode == "anthropic":
        return AnthropicProvider(record=record)
    # auto : cassette si elle existe, puis Groq si une clé est présente, puis Anthropic.
    chaine = []
    if CASSETTES.exists() and any(CASSETTES.glob("*.json")):
        chaine.append(CassetteProvider())
    if os.getenv("GROQ_API_KEY"):
        chaine.append(GroqProvider())
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        chaine.append(AnthropicProvider(record=record))
    if not chaine:
        return NullProvider()
    return ChainProvider(chaine) if len(chaine) > 1 else chaine[0]
