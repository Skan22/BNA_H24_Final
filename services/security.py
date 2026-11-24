"""Clé de service partagée : sans elle, les API simulées répondent 401 (sauf /health).

Le moteur n'a ainsi aucun accès « de fait » : il présente la même clé que n'importe quel client."""
from __future__ import annotations

import os
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def require_key(app: FastAPI) -> None:
    @app.middleware("http")
    async def key(request: Request, call_next):
        if request.url.path not in ("/health", "/docs", "/openapi.json"):
            expected = os.getenv("BOUSSOLA_MOCK_KEY", "local-mock-change-me")
            if not secrets.compare_digest(request.headers.get("x-mock-key", ""), expected):
                return JSONResponse({"detail": "Clé de service requise"}, status_code=401)
        return await call_next(request)
