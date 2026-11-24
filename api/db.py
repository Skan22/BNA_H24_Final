"""Persistance : sessions, diagnostics, escalades et journal d'audit chaîné.

SQLite par défaut ; PostgreSQL en changeant DATABASE_URL (psycopg à installer).
shortcut: `create_all` au démarrage, pas de migrations — à remplacer par Alembic dès qu'un schéma doit évoluer en production.
"""
from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, String, create_engine, delete, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

GENESIS = "0" * 64
_WRITE = threading.RLock()


def now() -> datetime:
    return datetime.now(timezone.utc)


def uid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    csrf: Mapped[str] = mapped_column(String(80))
    dossier_id: Mapped[str | None] = mapped_column(String(40), nullable=True)   # client : session = un dossier
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DiagnosisRow(Base):
    __tablename__ = "diagnoses"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)               # = trace_id
    dossier_id: Mapped[str] = mapped_column(String(40), index=True)
    actor: Mapped[str] = mapped_column(String(20))
    snapshot: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    bundle: Mapped[dict] = mapped_column(JSON)                                    # journal d'audit scellé du moteur
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EscalationRow(Base):
    __tablename__ = "escalations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    diagnosis_id: Mapped[str] = mapped_column(String(40), unique=True)
    dossier_id: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    snapshot: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditRow(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dossier_id: Mapped[str] = mapped_column(String(40), index=True)
    actor: Mapped[str] = mapped_column(String(20))
    event: Mapped[str] = mapped_column(String(60))
    trace_id: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON)
    at: Mapped[str] = mapped_column(String(40))
    prev: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


def _digest(prev: str, row: dict) -> str:
    return hashlib.sha256((prev + json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)).encode()).hexdigest()


def _fields(r) -> dict:
    return {"dossier_id": r.dossier_id, "actor": r.actor, "event": r.event,
            "trace_id": r.trace_id, "detail": r.detail, "at": r.at}


def append_audit(db, *, dossier_id: str, actor: str, event: str, trace_id: str, detail: dict) -> None:
    """Ajoute un événement chaîné à l'empreinte du précédent (global, tous dossiers)."""
    last = db.scalar(select(AuditRow).order_by(AuditRow.id.desc()).limit(1))
    row = AuditRow(dossier_id=dossier_id, actor=actor, event=event, trace_id=trace_id,
                   detail=json.loads(json.dumps(detail, default=str)), at=now().isoformat(),
                   prev=last.hash if last else GENESIS, hash="")
    row.hash = _digest(row.prev, _fields(row))
    db.add(row)


def verify_audit(db) -> tuple[bool, str]:
    prev = GENESIS
    for r in db.scalars(select(AuditRow).order_by(AuditRow.id)):
        if r.prev != prev or r.hash != _digest(r.prev, _fields(r)):
            return False, f"chaînage rompu à l'événement {r.id}"
        prev = r.hash
    return True, "chaîne intègre"


def database(url: str):
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, **kwargs)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


@contextmanager
def write(factory):
    """Transaction d'écriture sérialisée.

    Le journal d'audit est une chaîne : deux écritures concurrentes liraient la même « dernière »
    empreinte et fourcheraient la chaîne. Verrou de processus + verrou consultatif PostgreSQL.
    """
    with _WRITE, factory.begin() as db:
        if db.bind.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(724001)"))
        yield db


def purge_sessions(db) -> None:
    db.execute(delete(SessionRow).where(SessionRow.expires_at <= now()))
