"""Configuration par variables d'environnement. Les valeurs par défaut sont réservées à la démonstration locale."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", "sqlite:///./boussola.db"))
    split: str = field(default_factory=lambda: _env("BOUSSOLA_SPLIT", "public"))
    port_mode: str = field(default_factory=lambda: _env("BOUSSOLA_PORT", "local"))   # local | http
    agent_password: str = field(default_factory=lambda: _env("AGENT_PASSWORD", "agent-demo-change-me"))
    client_password: str = field(default_factory=lambda: _env("CLIENT_PASSWORD", "client-demo-change-me"))
    evaluator_token: str = field(default_factory=lambda: _env("EVALUATOR_TOKEN", "local-evaluator-change-me"))
    cookie_secure: bool = field(default_factory=lambda: _env("COOKIE_SECURE", "false").lower() == "true")
    session_seconds: int = field(default_factory=lambda: int(_env("SESSION_SECONDS", "3600")))
    requests_per_minute: int = field(default_factory=lambda: int(_env("REQUESTS_PER_MINUTE", "30")))
    demo_mode: bool = field(default_factory=lambda: _env("DEMO_MODE", "false").lower() == "true")

    def insecure_defaults(self) -> list[str]:
        """Secrets restés à leur valeur publique. Interdit hors mode démonstration."""
        import os
        courants = {"AGENT_PASSWORD": self.agent_password, "CLIENT_PASSWORD": self.client_password,
                    "EVALUATOR_TOKEN": self.evaluator_token}
        publics = {"agent-demo-change-me", "client-demo-change-me", "local-evaluator-change-me"}
        faibles = [k for k, v in courants.items() if v in publics]
        if self.port_mode == "http" and os.environ.get("BOUSSOLA_MOCK_KEY", "local-mock-change-me") == "local-mock-change-me":
            faibles.append("BOUSSOLA_MOCK_KEY")
        return faibles
