"""BOUSSOLA — API de la plateforme.

Le moteur (engine/) ne connaît ni sessions ni rôles ; cette couche les ajoute :
authentification, CSRF, périmètre « une session client = un dossier », vues par
rôle, persistance, instantané du dossier (preuve et escalade refusées si le
dossier a changé), simulation « et si ? » et escalade confirmée par un agent.

Lancer : uvicorn api.main:app   (la configuration vient de l'environnement)
"""

import hashlib
import json
import pathlib
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import timedelta, timezone
from typing import Annotated, Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from api import projection
from api.config import Settings
from api.db import (AuditRow, DiagnosisRow, EscalationRow, SessionRow, append_audit, database, now,
                    purge_sessions, verify_audit, write)
from contracts.models import Diagnosis, DiagnoseRequest
from engine.audit import AuditLog
from engine.broker import Broker, Session, ToolRefused
from engine.diagnose import diagnose
from engine.graph import CAUSE_BY_ID
from engine.llm.provider import resolve as resolve_provider
from engine.ports import HttpPort, LocalKitPort
from engine.preview import NotSimulable, simulate
from engine.rag.corpus import CORPUS

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOSSIER_RE = r"^DOS-[A-Z]{3}-\d{6}$"


class StrictModel(BaseModel):
    model_config = {"extra": "forbid"}


class LoginRequest(StrictModel):
    username: Literal["agent", "client"]
    password: str = Field(min_length=1, max_length=256)
    dossier_id: str | None = Field(default=None, pattern=DOSSIER_RE)   # obligatoire pour un client


class DiagnoseBody(StrictModel):
    dossier_id: str | None = Field(default=None, pattern=DOSSIER_RE)   # ignoré pour un client : la session décide
    question: str | None = Field(default=None, max_length=2000)
    locale: Literal["fr", "ar", "en"] = "fr"


class PreviewBody(StrictModel):
    cause_id: str | None = Field(default=None, pattern=r"^C-[A-Z]{3}-\d{3}$")   # agent
    step: int | None = Field(default=None, ge=0, le=9)                            # client : rang opaque dans l'explication


class EscalationBody(StrictModel):
    diagnosis_id: str = Field(pattern=r"^TR-[0-9a-f]{12}$")
    note: str = Field(default="", max_length=2000)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Principal:
    def __init__(self, role: str, identifier: str, csrf: str = "", dossier_id: str | None = None):
        self.role, self.identifier, self.csrf, self.dossier_id = role, identifier, csrf, dossier_id

    @property
    def staff(self) -> bool:
        return self.role in ("agent", "evaluator")

    def permit(self, dossier_id: str) -> None:
        # 404 et non 403 : ne pas révéler l'existence d'un dossier d'autrui.
        if self.role == "client" and dossier_id != self.dossier_id:
            raise HTTPException(404, "Dossier introuvable")

    def need_staff(self) -> None:
        if not self.staff:
            raise HTTPException(403, "Accès agent requis")

    def need_agent(self) -> None:
        if self.role != "agent":
            raise HTTPException(403, "Action réservée à un agent connecté")


def snapshot_of(port, dossier_id: str) -> str:
    """Empreinte de l'état des deux sources. Si elle change, toute preuve ou escalade antérieure est périmée."""
    raw = port.get_dossier(dossier_id)
    if raw is None:
        raise HTTPException(404, "Dossier introuvable")
    blob = json.dumps({"h24": raw, "csa": port.get_etat_csa(dossier_id)}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def create_app(config: Settings | None = None, port=None, factory=None, provider=None) -> FastAPI:
    config = config or Settings()
    if not config.demo_mode and (faibles := config.insecure_defaults()):
        raise RuntimeError("Secrets par défaut refusés hors mode démonstration (DEMO_MODE=true) : " + ", ".join(faibles))
    port = port or (HttpPort() if config.port_mode == "http" else LocalKitPort(config.split))
    provider = provider or resolve_provider()
    engine_db, default_factory = database(config.database_url)
    factory = factory or default_factory
    attempts: dict[str, deque] = defaultdict(deque)
    # Préfixe __Host- (HTTPS, Path=/, sans Domain) : le navigateur refuse alors tout cookie écrasé par un sous-domaine.
    cookie_name = "__Host-boussola_session" if config.cookie_secure else "boussola_session"

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine_db.dispose()

    app = FastAPI(title="BOUSSOLA — assistant de diagnostic H24", version="2.0.0", lifespan=lifespan,
                  description="Diagnostic des blocages « Devenir client ». L'assistant explique et recommande ; "
                              "il ne décide jamais à la place de la BNA. Données 100 % synthétiques.")

    @app.middleware("http")
    async def headers(request: Request, call_next):
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "Longueur invalide"}, status_code=400)
        if length > 16384:
            return JSONResponse({"detail": "Requête trop volumineuse"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Dossier introuvable"}, status_code=404)

    @app.exception_handler(httpx.HTTPError)
    async def unavailable(request, exc):
        return JSONResponse({"detail": "Source indisponible. Réessayez plus tard."}, status_code=503)

    def limit(key: str, maximum: int) -> None:
        clock, queue = time.monotonic(), attempts[key]
        while queue and clock - queue[0] > 60:
            queue.popleft()
        if len(queue) >= maximum:
            raise HTTPException(429, "Trop de demandes. Réessayez dans une minute.", headers={"Retry-After": "60"})
        queue.append(clock)
        if len(attempts) > 5000:       # borne la mémoire : on oublie les clés inactives
            for k in [k for k, q in attempts.items() if not q or clock - q[-1] > 60]:
                del attempts[k]

    def principal(request: Request) -> Principal:
        authorization = request.headers.get("authorization", "")
        if authorization.startswith("Bearer "):
            if secrets.compare_digest(authorization[7:], config.evaluator_token):
                return Principal("evaluator", "evaluator")
            raise HTTPException(401, "Identifiants invalides")
        cookie = request.cookies.get(cookie_name, "")
        with factory() as db:
            row = db.get(SessionRow, token_hash(cookie))
            if row is None or row.expires_at.replace(tzinfo=timezone.utc) <= now():
                raise HTTPException(401, "Session expirée. Reconnectez-vous.")
            if request.method not in ("GET", "HEAD", "OPTIONS") and not secrets.compare_digest(
                    request.headers.get("x-csrf-token", ""), row.csrf):
                raise HTTPException(403, "Protection de session invalide")
            return Principal(row.role, row.token_hash, row.csrf, row.dossier_id)

    Auth = Annotated[Principal, Depends(principal)]

    def rate(user: Principal) -> None:
        limit("api:" + user.identifier, 10_000 if user.role == "evaluator" else config.requests_per_minute)

    # ------------------------------------------------------------------ santé / auth
    @app.get("/health")
    def health():
        return {"statut": "ok"}          # public : rien sur la configuration

    @app.get("/v1/status")
    def status(user: Auth):
        user.need_staff()
        return {"statut": "ok", "split": config.split, "fournisseur": provider.name,
                "port": type(port).__name__, "regles_corpus": len(CORPUS.rules)}

    scenarios_cache: list[dict] = []

    def scenarios() -> list[dict]:
        """Un dossier par cause, pour guider une démonstration. Calculé par le moteur lui-même (jamais lu dans la
        vérité terrain) sur le kit local, une seule fois."""
        if not scenarios_cache:
            local, nul, vus = LocalKitPort(config.split), resolve_provider("none"), {}
            for did in local.dossiers:
                d, _ = diagnose(local, DiagnoseRequest(dossier_id=did), provider=nul)
                vus.setdefault(d.top_cause, (did, d))
            for cause, (did, d) in sorted(vus.items()):
                scenarios_cache.append({"dossier_id": did, "cause_id": cause, "family": CAUSE_BY_ID[cause]["family"],
                                        "label_fr": CAUSE_BY_ID[cause]["label_fr"], "step": d.step.value})
        return scenarios_cache

    @app.get("/v1/auth/demo")
    def demo():
        if not config.demo_mode:
            raise HTTPException(404, "Introuvable")
        return {"scenarios": scenarios(), "note": "Mode démonstration : mots de passe fournis par l'organisateur."}

    @app.post("/v1/auth/login")
    def login(body: LoginRequest, request: Request, response: Response):
        # Derrière le relais web, l'adresse vue est celle du relais : on borne par (adresse, compte, dossier)
        # pour qu'un essai raté ne bloque pas tous les autres utilisateurs, et on garde un plafond global.
        ip = request.client.host if request.client else "?"
        limit(f"login:{ip}:{body.username}:{body.dossier_id}", 10)
        limit(f"login-ip:{ip}", 120)
        expected = config.agent_password if body.username == "agent" else config.client_password
        ok = secrets.compare_digest(body.password, expected)
        if ok and body.username == "client":
            ok = bool(body.dossier_id) and port.get_dossier(body.dossier_id) is not None
        if not ok:
            raise HTTPException(401, "Identifiants invalides")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        dossier = body.dossier_id if body.username == "client" else None
        with write(factory) as db:
            purge_sessions(db)
            db.add(SessionRow(token_hash=token_hash(token), role=body.username, csrf=csrf, dossier_id=dossier,
                              expires_at=now() + timedelta(seconds=config.session_seconds)))
        response.set_cookie(cookie_name, token, httponly=True, secure=config.cookie_secure,
                            samesite="strict", max_age=config.session_seconds)
        return {"role": body.username, "csrf": csrf, "dossier_id": dossier, "provider": provider.name}

    @app.get("/v1/auth/me")
    def me(user: Auth):
        return {"role": user.role, "csrf": user.csrf, "dossier_id": user.dossier_id, "provider": provider.name}

    @app.post("/v1/auth/logout")
    def logout(response: Response, user: Auth):
        with write(factory) as db:
            row = db.get(SessionRow, user.identifier)
            if row:
                db.delete(row)
        response.delete_cookie(cookie_name)
        return {"status": "signed_out"}

    # ------------------------------------------------------------------ dossiers & corpus
    @app.get("/v1/dossiers")
    def dossiers(user: Auth):
        if user.role == "client":
            return [d for d in port.list_dossiers(500) if d["dossier_id"] == user.dossier_id]
        return port.list_dossiers(250)

    @app.get("/v1/corpus/{anchor}")
    def rule(anchor: str, user: Auth):
        r = CORPUS.rules.get(anchor)
        if r is None or (user.role == "client" and not projection.visible_client(anchor)):
            raise HTTPException(404, "Règle introuvable")
        return {"anchor": r.anchor, "titre": f"{r.doc_titre} — {r.titre_regle}", "texte": r.texte,
                "doc_id": r.doc_id, "version": r.version, "effective_date": r.effective_date, "domaine": r.domaine}

    # ------------------------------------------------------------------ diagnostics
    def load(identifier: str, user: Principal) -> tuple[Diagnosis, DiagnosisRow]:
        with factory() as db:
            row = db.get(DiagnosisRow, identifier)
        if row is None:
            raise HTTPException(404, "Diagnostic introuvable")
        user.permit(row.dossier_id)
        return Diagnosis.model_validate(row.payload), row

    def fresh(row) -> None:
        if snapshot_of(port, row.dossier_id) != row.snapshot:
            raise HTTPException(409, "Le dossier a changé. Relancez le diagnostic.")

    def audit(dossier_id, user, event, trace_id, detail):
        with write(factory) as db:
            append_audit(db, dossier_id=dossier_id, actor=user.role, event=event, trace_id=trace_id, detail=detail)

    @app.post("/v1/diagnoses")
    def create_diagnosis(body: DiagnoseBody, user: Auth):
        rate(user)
        dossier_id = user.dossier_id if user.role == "client" else body.dossier_id
        if not dossier_id:
            raise HTTPException(422, "dossier_id requis")
        user.permit(dossier_id)
        snapshot = snapshot_of(port, dossier_id)
        diag, session = diagnose(port, DiagnoseRequest(dossier_id=dossier_id, question=body.question,
                                                       audience="client" if user.role == "client" else "agent",
                                                       locale=body.locale), provider=provider)
        with write(factory) as db:
            db.add(DiagnosisRow(id=diag.trace_id, dossier_id=dossier_id, actor=user.role, snapshot=snapshot,
                                payload=diag.model_dump(mode="json"), bundle=session.audit.bundle()))
            append_audit(db, dossier_id=dossier_id, actor=user.role, event="diagnosis_completed",
                         trace_id=diag.trace_id,
                         detail={"cause": diag.top_cause, "confidence": diag.confidence, "abstained": diag.abstained,
                                 "human_validation_required": diag.human_validation_required,
                                 "provider": diag.trace.provider, "latency_ms": diag.trace.latency_ms})
        return projection.client_diagnosis(diag) if user.role == "client" else diag.model_dump(mode="json")

    @app.get("/v1/diagnoses/{identifier}")
    def read_diagnosis(identifier: str, user: Auth):
        diag, _ = load(identifier, user)
        return projection.client_diagnosis(diag) if user.role == "client" else diag.model_dump(mode="json")

    @app.get("/v1/diagnoses/{identifier}/trace")
    def trace(identifier: str, user: Auth):
        user.need_staff()
        _, row = load(identifier, user)
        log = AuditLog(row.id, row.bundle["entries"])
        return log.bundle()

    @app.get("/v1/diagnoses/{identifier}/explanation")
    def explanation(identifier: str, user: Auth):
        diag, row = load(identifier, user)
        fresh(row)
        return projection.client_explanation(diag) if user.role == "client" else projection.agent_explanation(diag)

    @app.post("/v1/diagnoses/{identifier}/preview")
    def preview(identifier: str, body: PreviewBody, user: Auth):
        rate(user)
        diag, row = load(identifier, user)
        if user.role == "client":       # le client désigne un point de son explication, jamais un code de cause
            visibles = projection.explained_causes(diag)
            if body.step is None or body.step >= len(visibles):
                raise HTTPException(409, "Point d'explication inconnu")
            cause_id = visibles[body.step].cause_id
        else:
            cause_id = body.cause_id
        if cause_id not in {c.cause_id for c in diag.causes}:
            raise HTTPException(409, "Cette cause ne fait pas partie du diagnostic")
        fresh(row)
        try:
            result = simulate(port, row.dossier_id, cause_id, [c.cause_id for c in diag.causes])
        except NotSimulable as exc:
            raise HTTPException(409, str(exc)) from None
        audit(row.dossier_id, user, "resolution_previewed", row.id,
              {"cause": cause_id, "cleared": [c["cause_id"] for c in result["cleared"]],
               "remaining": [c["cause_id"] for c in result["remaining"]], "synthetic": True})
        result.update(synthetic=True, disclaimer=projection.DISCLAIMER_PREVIEW,
                      assumption=f"Hypothèse : « {CAUSE_BY_ID[cause_id]['label_fr']} » est levé et vérifié.")
        return projection.client_preview(result, projection.DISCLAIMER_PREVIEW) if user.role == "client" else result

    # ------------------------------------------------------------------ escalade
    @app.post("/v1/escalations")
    def draft(body: EscalationBody, user: Auth):
        user.need_agent()          # l'évaluateur ne crée ni ne confirme d'escalade
        diag, row = load(body.diagnosis_id, user)
        if not diag.human_validation_required:
            raise HTTPException(409, "Ce diagnostic ne nécessite pas d'escalade")
        with write(factory) as db:
            existing = db.scalar(select(EscalationRow).where(EscalationRow.diagnosis_id == row.id))
            if existing:
                return {"id": existing.id, "status": existing.status, **existing.payload}
            payload = {"synthetic": True, "dossier_id": row.dossier_id, "trace_id": row.id, "note": body.note,
                       "summary": diag.explanation_agent.escalation_draft or diag.explanation_agent.summary,
                       "causes": [c.cause_id for c in diag.causes], "sources": [s.anchor for s in diag.sources]}
            esc = EscalationRow(diagnosis_id=row.id, dossier_id=row.dossier_id, snapshot=row.snapshot, payload=payload)
            db.add(esc)
            db.flush()
            append_audit(db, dossier_id=row.dossier_id, actor=user.role, event="escalation_drafted",
                         trace_id=row.id, detail={"escalation_id": esc.id})
            return {"id": esc.id, "status": esc.status, **payload}

    @app.post("/v1/escalations/{identifier}/confirm")
    def confirm(identifier: str, user: Auth):
        user.need_agent()
        with factory() as db:
            esc = db.get(EscalationRow, identifier)
        if esc is None:
            raise HTTPException(404, "Escalade introuvable")
        if esc.status == "confirmed":
            return {"id": esc.id, "status": esc.status, "simulated": True}
        if snapshot_of(port, esc.dossier_id) != esc.snapshot:
            raise HTTPException(409, "Le dossier a changé. Relancez le diagnostic avant de confirmer.")
        # L'acquittement humain est établi ICI, par la session agent authentifiée — jamais par le corps de la requête.
        session = Session(trace_id=esc.payload["trace_id"], dossier_id=esc.dossier_id, human_ack=True)
        try:
            result = Broker(port, session).call("csa.create_escalation", dossier_id=esc.dossier_id)
        except ToolRefused as exc:
            raise HTTPException(403, str(exc)) from None
        with write(factory) as db:
            row = db.get(EscalationRow, identifier)
            if row.status != "confirmed":
                row.status = "confirmed"
                row.payload = {**row.payload, "confirmed_by": user.role, "confirmed_at": now().isoformat(),
                               "reference": result["escalation_id"]}
                append_audit(db, dossier_id=row.dossier_id, actor=user.role, event="escalation_confirmed",
                             trace_id=row.payload["trace_id"], detail={"escalation_id": row.id, "synthetic": True})
        return {"id": identifier, "status": "confirmed", "simulated": True, "reference": result["escalation_id"]}

    # ------------------------------------------------------------------ audit & mesures
    @app.get("/v1/audit")
    def audit_log(user: Auth, dossier_id: str | None = None):
        user.need_staff()
        with factory() as db:
            q = select(AuditRow).order_by(AuditRow.id)
            if dossier_id:
                q = q.where(AuditRow.dossier_id == dossier_id)
            ok, detail = verify_audit(db)
            rows = db.scalars(q).all()
        return {"integrite": {"ok": ok, "detail": detail},
                "events": [{"event": r.event, "actor": r.actor, "at": r.at, "dossier_id": r.dossier_id,
                            "trace_id": r.trace_id, "detail": r.detail} for r in rows]}

    @app.get("/v1/eval/summary")
    def eval_summary(user: Auth, split: Literal["public", "private"] = "private"):
        user.need_staff()
        path = ROOT / "eval" / f"report-{split}.json"
        if not path.exists():
            raise HTTPException(404, "Aucun rapport : lancer `make eval`")
        return json.loads(path.read_text())

    return app


# Entrée `uvicorn api.main:app` : paresseuse pour que l'import (tests, contrats) n'ouvre aucune base.
def __getattr__(name):
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
