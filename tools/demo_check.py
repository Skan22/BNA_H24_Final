"""Vérifie que les étapes de la démonstration fonctionnent, dans l'ordre, sur la pile en marche.

À lancer juste avant de passer devant le jury (`make demo-check`). Chaque étape correspond à une
section de docs/demonstration.md : si l'une tombe, on sait laquelle retirer du script.

    AGENT_PASSWORD=... CLIENT_PASSWORD=... python tools/demo_check.py [url_du_moteur]
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
VERT, ROUGE, GRIS, RAZ = "\033[32m", "\033[31m", "\033[90m", "\033[0m"
MDP = {"agent": os.getenv("AGENT_PASSWORD", "agent-demo-change-me"),
       "client": os.getenv("CLIENT_PASSWORD", "client-demo-change-me")}


class Client:
    """Un navigateur minimal : cookie de session + jeton CSRF."""

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.http = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = ""

    def call(self, path, payload=None, method=None):
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        if self.csrf and (data is not None or method == "POST"):
            headers["X-CSRF-Token"] = self.csrf
        req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
        try:
            with self.http.open(req, timeout=15) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, {"detail": e.read().decode()[:200]}

    def login(self, role, dossier=None):
        code, body = self.call("/v1/auth/login", {"username": role, "password": MDP[role], "dossier_id": dossier})
        self.csrf = body.get("csrf", "")
        return code


def dossier_de(cause: str, split: str = "public") -> str | None:
    gt = json.loads((ROOT / "kit" / "scenarios" / split / "ground_truth.json").read_text())
    return next((k for k, g in gt.items() if g["cause_id"] == cause), None)


resultats: list[tuple[str, bool, str]] = []


def verifier(etape: str, condition: bool, detail: str) -> None:
    resultats.append((etape, condition, detail))
    print(f"  {VERT + '✓' if condition else ROUGE + '✗'}{RAZ} {etape}\n      {GRIS}{detail}{RAZ}")


print(f"BOUSSOLA — vérification de la démonstration ({BASE})\n")
anon = Client()
code, _ = anon.call("/health")
staff = Client()
staff.login("agent")
_, sante = staff.call("/v1/status")
verifier("0 · les services répondent, accès anonyme refusé", code == 200 and anon.call("/v1/dossiers")[0] == 401,
         f"{sante.get('statut')} · port {sante.get('port')} · modèle {sante.get('fournisseur')} · "
         f"{sante.get('regles_corpus')} règles")
if code != 200:
    print(f"\n{ROUGE}Moteur injoignable. Lancer `make demo`.{RAZ}")
    sys.exit(1)

# 1 · client : explication sans jargon, périmètre = son dossier
did = dossier_de("C-IDN-001")
cl = Client()
cl.login("client", did)
_, d = cl.call("/v1/diagnoses", {})
texte = d["explanation_client"]["fr"]
verifier("1 · explication client lisible, sans jargon ni cause interne",
         d["dossier_id"] == did and "causes" not in d and not any(j in texte for j in ("H24-", "C-IDN", "R-IDN"))
         and any(s["owner"] == "client" for s in d["unblock_path"]),
         f"{did} → {len(d['unblock_path'])} action(s) · vue restreinte")

# 2 · agent : causes, preuve, règle citée
ag = Client()
ag.login("agent")
_, a = ag.call("/v1/diagnoses", {"dossier_id": did})
_, preuve = ag.call(f"/v1/diagnoses/{a['trace_id']}/explanation")
_, regle = ag.call(f"/v1/corpus/{a['sources'][0]['anchor']}")
verifier("2 · chaîne de preuve : faits → règle citée → suite",
         bool(preuve.get("steps")) and preuve["steps"][0]["facts"] and len(regle.get("texte", "")) > 80,
         f"{a['causes'][0]['cause_id']} · {len(preuve['steps'][0]['facts'])} fait(s) · règle {regle.get('anchor')}")

# 3 · simulation « et si ? » en lecture seule
_, p = ag.call(f"/v1/diagnoses/{a['trace_id']}/preview", {"cause_id": a["causes"][0]["cause_id"]})
verifier("3 · simulation « et si ? » en lecture seule", p.get("synthetic") is True and p.get("cleared"),
         f"levé : {[c['cause_id'] for c in p.get('cleared', [])]} · reste : {[c['cause_id'] for c in p.get('remaining', [])]}"
         f" · {p.get('simulated_disposition')}")

# 4 · document piégé : signalé, jamais exécuté, et le client n'en sait rien
did_sec = dossier_de("C-SEC-001")
cs = Client()
cs.login("client", did_sec)
_, d = cs.call("/v1/diagnoses", {})
verifier("4 · document piégé neutralisé, détection non révélée au client",
         d["human_validation_required"] and d["unblock_path"] == []
         and "manipulation" not in json.dumps(d).lower(),
         f"{did_sec} → escalade, aucune trace de détection côté client")

# 5 · repli sûr, puis escalade : brouillon → confirmation par l'agent connecté
did_unk = dossier_de("C-UNK-000")
_, a2 = ag.call("/v1/diagnoses", {"dossier_id": did_unk})
c_ev, _ = anon.call("/v1/escalations", {"diagnosis_id": a2["trace_id"]})
_, brouillon = ag.call("/v1/escalations", {"diagnosis_id": a2["trace_id"], "note": "démonstration"})
c_ok, conf = ag.call(f"/v1/escalations/{brouillon['id']}/confirm", method="POST")
verifier("5 · repli sûr puis escalade confirmée par un agent",
         a2["abstained"] and c_ev == 401 and c_ok == 200 and conf.get("simulated") is True,
         f"{did_unk} → abstention · sans session {c_ev} · confirmation {c_ok}")

# 6 · journal chaîné et mesures
_, tr = ag.call(f"/v1/diagnoses/{a2['trace_id']}/trace")
_, au = ag.call("/v1/audit")
code_eval, ev = ag.call("/v1/eval/summary?split=private")
verifier("6 · trace scellée, journal chaîné, mesures publiées",
         tr.get("integrite", {}).get("ok") is True and au.get("integrite", {}).get("ok") is True and code_eval == 200,
         f"{len(tr.get('entries', []))} entrées · {len(au.get('events', []))} événements · "
         + (f"top-1 privé {ev['metrics']['exactitude']['top1']:.0%}" if code_eval == 200 else "lancer `make eval-private`"))

echecs = [e for e, ok, _ in resultats if not ok]
print()
if echecs:
    print(f"{ROUGE}{len(echecs)} étape(s) en échec : {echecs}{RAZ}")
    sys.exit(1)
print(f"{VERT}Les {len(resultats)} étapes de la démonstration fonctionnent.{RAZ}")
