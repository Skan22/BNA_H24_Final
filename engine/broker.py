"""BOUSSOLA — courtier d'outils.

Tout accès à une donnée passe ici. Le courtier applique, dans l'ordre :

  1. l'outil existe-t-il au manifeste ? (sinon : refus tracé)
  2. est-il explicitement interdit ? (refus tracé avec la règle nommée)
  3. écrit-il ? alors il exige un acquittement humain
  4. l'argument reste-t-il dans le périmètre de la session ? (R-SEC-003)
  5. les budgets de la session sont-ils tenus ?

Un refus n'est pas une exception silencieuse : il est journalisé et devient un
fait exploitable par le diagnostic.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time
from dataclasses import dataclass, field

import yaml

from engine.audit import AuditLog

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = yaml.safe_load((ROOT / "contracts" / "tools.manifest.yaml").read_text())
TOOLS = {t["name"]: t for t in MANIFEST["tools"]}
FORBIDDEN = {t["name"]: t for t in MANIFEST["forbidden"]}
BUDGETS = MANIFEST["budgets"]


class ToolRefused(Exception):
    def __init__(self, tool: str, reason: str, rule: str):
        super().__init__(f"{tool} refusé : {reason}")
        self.tool, self.reason, self.rule = tool, reason, rule


@dataclass
class Session:
    """Une session = un dossier. C'est la frontière de sécurité."""

    trace_id: str
    dossier_id: str
    identite: str | None = None
    human_ack: bool = False
    audit: AuditLog = field(default=None)          # type: ignore[assignment]
    calls: list[dict] = field(default_factory=list)
    llm_calls: int = 0
    started_at: float = field(default_factory=time.monotonic)

    def __post_init__(self):
        if self.audit is None:
            self.audit = AuditLog(self.trace_id)
            self.audit.append("session.open", {"dossier_id": self.dossier_id})

    @property
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.started_at) * 1000)

    def budget_exceeded(self) -> str | None:
        if len(self.calls) >= BUDGETS["max_tool_calls"]:
            return f"budget d'appels d'outils dépassé ({BUDGETS['max_tool_calls']})"
        if self.llm_calls >= BUDGETS["max_llm_calls"]:
            return f"budget d'appels au modèle dépassé ({BUDGETS['max_llm_calls']})"
        if self.elapsed_ms >= BUDGETS["max_wall_clock_ms"]:
            return f"budget de temps dépassé ({BUDGETS['max_wall_clock_ms']} ms)"
        return None


def _digest(args: dict) -> str:
    return hashlib.sha256(json.dumps(args, sort_keys=True, default=str).encode()).hexdigest()[:12]


class Broker:
    def __init__(self, port, session: Session):
        self.port, self.s = port, session

    # -- contrôle d'accès ---------------------------------------------------
    def _authorize(self, tool: str, args: dict) -> None:
        if tool in FORBIDDEN:
            raise ToolRefused(tool, FORBIDDEN[tool]["reason"], "manifeste.forbidden")
        spec = TOOLS.get(tool)
        if spec is None:
            raise ToolRefused(tool, "outil absent du manifeste de capacités", "manifeste.allowlist")
        if spec["mode"] == "write" and spec.get("requires_human_ack") and not self.s.human_ack:
            raise ToolRefused(tool, "écriture soumise à acquittement humain", "R-ESC-003")

        scope = spec.get("scope", MANIFEST["defaults"]["scope"])
        if scope == "bound_dossier":
            demande = args.get("dossier_id")
            if demande is not None and demande != self.s.dossier_id:
                # Le cas qui compte : une session ne lit pas le dossier d'autrui.
                raise ToolRefused(tool, f"dossier {demande} hors du périmètre de la session", "R-SEC-003")
        elif scope == "bound_identity":
            demande = args.get("identite")
            if demande is not None and demande != self.s.identite:
                raise ToolRefused(tool, "identité hors du périmètre de la session", "R-SEC-003")

        if (msg := self.s.budget_exceeded()):
            raise ToolRefused(tool, msg, "manifeste.budgets")

    def call(self, tool: str, **args):
        t0 = time.monotonic()
        try:
            self._authorize(tool, args)
            result = self._dispatch(tool, args)
            allowed, reason = True, None
        except ToolRefused as exc:
            result, allowed, reason = None, False, f"{exc.reason} [{exc.rule}]"
        latency = int((time.monotonic() - t0) * 1000)
        record = {"seq": len(self.s.calls), "tool": tool, "args_digest": _digest(args),
                  "allowed": allowed, "reason": reason, "latency_ms": latency}
        self.s.calls.append(record)
        self.s.audit.append("tool.call", record)
        if not allowed:
            raise ToolRefused(tool, reason or "refusé", "voir trace")
        return result

    def try_call(self, tool: str, **args):
        """Comme `call`, mais un refus renvoie None au lieu de lever.

        Le diagnostic continue avec une vue du monde incomplète — et le sait,
        puisque le refus figure dans la trace.
        """
        try:
            return self.call(tool, **args)
        except ToolRefused:
            return None

    # -- exécution ----------------------------------------------------------
    def _dispatch(self, tool: str, args: dict):
        p = self.port
        match tool:
            case "h24.get_dossier":
                return p.get_dossier(self.s.dossier_id)
            case "h24.get_steps":
                d = p.get_dossier(self.s.dossier_id) or {}
                return {"step": d.get("step"), "status": d.get("status")}
            case "h24.get_events":
                return p.get_events(self.s.dossier_id)
            case "h24.get_document_ocr":
                return p.get_document_ocr(self.s.dossier_id, args["doc_id"])
            case "csa.get_subscriptions":
                return p.get_subscriptions(self.s.identite)
            case "csa.get_relations":
                return p.get_relations(self.s.identite)
            case "csa.search_duplicates":
                return p.search_duplicates(self.s.dossier_id)
            case "csa.get_agency_queue":
                q = p.get_agency_queue(args.get("code_agence"))
                return q          # agrégats seulement : aucune donnée nominative
            case "csa.get_etat":
                return p.get_etat_csa(self.s.dossier_id)
            case "csa.create_escalation":
                return {"escalation_id": f"ESC-{self.s.trace_id[:8]}", "statut": "preparee",
                        "transmise": False, "note": "transmission après acquittement humain (R-ESC-003)"}
            case _:
                raise ToolRefused(tool, "aucune implémentation", "broker.dispatch")
