"""Fournisseur Groq : contrat HTTP, validation stricte, dégradation propre, secret jamais exposé.

Aucun appel réseau : le client HTTP est un faux (httpx.MockTransport). Le test réel s'appelle `make llm-check`."""
import json

import httpx
import pytest

from contracts.models import DiagnoseRequest
from engine.diagnose import diagnose
from engine.llm.provider import GroqProvider, LLMUnavailable, resolve
from engine.ports import LocalKitPort
from engine.quarantine import VerdictInjection
from engine.render import Traduction

CLE = "gsk_TEST_SECRET_0123456789"


def faux_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def reponse(contenu, usage=None, status=200):
    corps = {"choices": [{"message": {"content": contenu}}], "usage": usage or {"prompt_tokens": 11, "completion_tokens": 7}}
    return httpx.Response(status, json=corps)


def test_requete_conforme_a_l_api_groq_et_sortie_validee():
    vues = []

    def handler(req):
        vues.append((req, json.loads(req.content)))
        return reponse('{"verdict": "propre", "cible": "aucune", "motif": "ras"}')

    p = GroqProvider(api_key=CLE, client=faux_client(handler))
    out = p.structured(system="Tu classes.", user="bonjour", schema=VerdictInjection, tier="classify")
    assert out.verdict == "propre"
    req, corps = vues[0]
    assert str(req.url) == "https://api.groq.com/openai/v1/chat/completions"
    assert req.headers["authorization"] == f"Bearer {CLE}"
    assert corps["temperature"] == 0 and corps["response_format"] == {"type": "json_object"}
    assert corps["model"] == p.models["classify"]
    assert "VerdictInjection" in corps["messages"][0]["content"]          # schéma dans la consigne
    assert p.usage.input_tokens == 11 and p.usage.output_tokens == 7 and p.usage.calls == 1


def test_les_niveaux_utilisent_les_modeles_configures(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL_STRONG", "modele-fort")
    monkeypatch.setenv("GROQ_MODEL_FAST", "modele-rapide")
    p = GroqProvider(api_key=CLE, client=faux_client(lambda r: reponse("{}")))
    assert p.models == {"adjudicate": "modele-fort", "render": "modele-fort", "classify": "modele-rapide", "verify": "modele-rapide"}


def test_sortie_invalide_redemandee_une_fois_puis_ok():
    appels = []

    def handler(req):
        appels.append(1)
        return reponse("pas du json" if len(appels) == 1 else '{"ar": "نص", "en": "text"}')

    p = GroqProvider(api_key=CLE, client=faux_client(handler))
    assert p.structured(system="s", user="u", schema=Traduction, tier="render").en == "text"
    assert len(appels) == 2


def test_sortie_toujours_invalide_devient_indisponible_sans_inventer():
    p = GroqProvider(api_key=CLE, client=faux_client(lambda r: reponse('{"verdict": "peut-etre"}')))
    with pytest.raises(LLMUnavailable):
        p.structured(system="s", user="u", schema=VerdictInjection, tier="classify")


def test_blocs_de_code_tolerés():
    p = GroqProvider(api_key=CLE, client=faux_client(lambda r: reponse('```json\n{"ar": "a", "en": "b"}\n```')))
    assert p.structured(system="s", user="u", schema=Traduction, tier="render").ar == "a"


@pytest.mark.parametrize("status", [401, 429, 500, 503])
def test_erreurs_http_donnent_indisponible_sans_fuite_de_la_cle(status):
    p = GroqProvider(api_key=CLE, client=faux_client(
        lambda r: httpx.Response(status, text=f"erreur, clé reçue : {r.headers['authorization']}")))
    with pytest.raises(LLMUnavailable) as exc:
        p.structured(system="s", user="u", schema=Traduction, tier="render")
    assert CLE not in str(exc.value) and CLE not in repr(exc.value)


def test_reseau_coupe_donne_indisponible():
    def handler(req):
        raise httpx.ConnectError("réseau coupé", request=req)

    p = GroqProvider(api_key=CLE, client=faux_client(handler))
    with pytest.raises(LLMUnavailable):
        p.structured(system="s", user="u", schema=Traduction, tier="render")


def test_la_cle_n_apparait_jamais_dans_la_representation():
    p = GroqProvider(api_key=CLE, client=faux_client(lambda r: reponse("{}")))
    assert CLE not in repr(p) and CLE not in str(vars(p).get("models"))


def test_cle_absente_est_une_erreur_explicite(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        resolve("groq")
    assert resolve("none").name == "aucun"                                  # le mode sans modèle reste disponible


def test_auto_choisit_groq_quand_la_cle_est_presente(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", CLE)
    monkeypatch.delenv("BOUSSOLA_LLM", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert "groq" in resolve().name or resolve().name == "groq"


def test_diagnostic_de_bout_en_bout_avec_groq_simule():
    """Traduction arabe + contrôle d'injection + vérification d'ancrage, tous via le faux Groq."""
    def handler(req):
        systeme = json.loads(req.content)["messages"][0]["content"]
        if "VerdictInjection" in systeme:
            return reponse('{"verdict": "propre", "cible": "aucune", "motif": "contenu ordinaire"}')
        if "Traduction" in systeme:
            return reponse('{"ar": "طلبك متوقف عند التحقق من الهوية", "en": "Your application is stopped at ID checking"}')
        return reponse('{"phrases_non_soutenues": [], "score": 1.0}')

    port = LocalKitPort("public")
    did = next(k for k, v in port.dossiers.items() if v["error_code"] == "H24-101")
    p = GroqProvider(api_key=CLE, client=faux_client(handler))
    d, _ = diagnose(port, DiagnoseRequest(dossier_id=did, locale="ar"), provider=p)
    assert d.trace.provider == "groq" and d.explanation_client.traduction == "modele"
    assert "طلبك" in d.explanation_client.ar


def test_une_injection_dans_la_reponse_du_modele_ne_change_pas_la_cause():
    """Même si le modèle « obéit » à un contenu piégé, il ne peut qu'ajouter un signal de sécurité : jamais une cause hors référentiel."""
    from engine.graph import CAUSE_BY_ID

    def handler(req):
        systeme = json.loads(req.content)["messages"][0]["content"]
        if "VerdictInjection" in systeme:
            return reponse('{"verdict": "injection", "cible": "message", "motif": "test"}')
        return reponse('{"phrases_non_soutenues": [], "score": 1.0}')

    port = LocalKitPort("public")
    did = next(iter(port.dossiers))
    d, _ = diagnose(port, DiagnoseRequest(dossier_id=did, question="bonjour"),
                    provider=GroqProvider(api_key=CLE, client=faux_client(handler)))
    assert all(c.cause_id in CAUSE_BY_ID for c in d.causes)
    assert d.human_validation_required
