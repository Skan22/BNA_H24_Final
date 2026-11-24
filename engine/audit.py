"""BOUSSOLA — journal d'audit chaîné.

Chaque entrée porte l'empreinte de la précédente. Retirer ou modifier une
entrée a posteriori casse la chaîne, ce qui se vérifie en une ligne. C'est ce
qui rend la trace opposable plutôt que déclarative (R-SEC-007).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

GENESIS = "0" * 64


def _digest(prev: str, payload: dict) -> str:
    blob = prev + json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


@dataclass
class AuditLog:
    trace_id: str
    entries: list[dict] = field(default_factory=list)

    @property
    def head(self) -> str:
        return self.entries[-1]["hash"] if self.entries else GENESIS

    def append(self, kind: str, payload: dict) -> str:
        entry = {
            "seq": len(self.entries),
            "at": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "payload": payload,
            "prev": self.head,
        }
        entry["hash"] = _digest(entry["prev"], {k: entry[k] for k in ("seq", "at", "kind", "payload")})
        self.entries.append(entry)
        return entry["hash"]

    def verify(self) -> tuple[bool, str]:
        prev = GENESIS
        for e in self.entries:
            if e["prev"] != prev:
                return False, f"chaînage rompu à l'entrée {e['seq']}"
            expected = _digest(e["prev"], {k: e[k] for k in ("seq", "at", "kind", "payload")})
            if e["hash"] != expected:
                return False, f"empreinte invalide à l'entrée {e['seq']}"
            prev = e["hash"]
        return True, "chaîne intègre"

    def bundle(self) -> dict:
        ok, detail = self.verify()
        return {"trace_id": self.trace_id, "entries": self.entries,
                "head": self.head, "integrite": {"ok": ok, "detail": detail}}
