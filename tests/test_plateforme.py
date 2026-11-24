"""Plateforme : authentification, périmètre, vues par rôle, preuve, simulation, escalade, audit.

Chaque test correspond à un contrôle annoncé dans docs/securite.md."""
import copy
import json
import pathlib
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api.config import Settings
from api.db import AuditRow, database, verify_audit
from api.main import create_app
from engine.llm.provider import resolve
from engine.ports import LocalKitPort

ROOT = pathlib.Path(__file__).resolve().parents[1]
GT = json.loads((ROOT / "kit/scenarios/public/ground_truth.json").read_text())


def dossier_pour(cause):
    return next(k for k, g in GT.items() if g["cause_id"] == cause)


@pytest.fixture
def plat(tmp_path):
    cfg = Settings(database_url=f"sqlite:///{tmp_path/'t.db'}", requests_per_minute=1000, demo_mode=True)
    port = LocalKitPort("public")
    port.dossiers = copy.deepcopy(port.dossiers)       # les tests peuvent muter : jamais le kit partagé
    engine, factory = database(cfg.database_url)
    with TestClient(create_app(cfg, port, factory, resolve("none"))) as c:
        yield c, cfg, port, factory
    engine.dispose()


def login(c, cfg, role="agent", dossier=None):
    pw = cfg.agent_password if role == "agent" else cfg.client_password
    r = c.post("/v1/auth/login", json={"username": role, "password": pw, "dossier_id": dossier})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": r.json()["csrf"]}


def test_authentification_requise_et_identifiants_opaques(plat):
    c, cfg, _, _ = plat
    assert c.get("/v1/dossiers").status_code == 401
    assert c.post("/v1/auth/login", json={"username": "agent", "password": "x"}).status_code == 401
    # un client doit nommer un dossier existant ; la réponse ne dit pas lequel des deux champs est faux
    r = c.post("/v1/auth/login", json={"username": "client", "password": cfg.client_password})
    assert r.status_code == 401
    r = c.post("/v1/auth/login", json={"username": "client", "password": cfg.client_password,
                                       "dossier_id": "DOS-ZZZ-999999"})
    assert r.status_code == 401


def test_csrf_et_role_non_choisi_par_l_appelant(plat):
    c, cfg, _, _ = plat
    csrf = login(c, cfg)
    did = dossier_pour("C-IDN-001")
    assert c.post("/v1/diagnoses", json={"dossier_id": did}).status_code == 403          # sans CSRF
    assert c.post("/v1/diagnoses", json={"dossier_id": did, "role": "evaluator"}, headers=csrf).status_code == 422
    assert c.post("/v1/diagnoses", json={"dossier_id": did}, headers=csrf).status_code == 200


def test_client_limite_a_son_dossier_et_vue_restreinte(plat):
    c, cfg, _, _ = plat
    mien, autre = dossier_pour("C-IDN-001"), dossier_pour("C-DOC-001")
    csrf = login(c, cfg, "client", mien)
    # le dossier du corps est ignoré : la session décide
    r = c.post("/v1/diagnoses", json={"dossier_id": autre}, headers=csrf)
    assert r.status_code == 200 and r.json()["dossier_id"] == mien
    assert not {"causes", "trace", "explanation_agent", "error_code", "allowed_actions"} & r.json().keys()
    assert not re.search(r"\bC-[A-Z]{3}-\d{3}\b", json.dumps(r.json()))             # aucun identifiant de cause
    assert [d["dossier_id"] for d in c.get("/v1/dossiers").json()] == [mien]
    for chemin in (f"/v1/diagnoses/{r.json()['reference']}/trace", "/v1/audit", "/v1/eval/summary"):
        assert c.get(chemin).status_code == 403
    assert c.post("/v1/escalations", json={"diagnosis_id": r.json()["reference"]}, headers=csrf).status_code == 403
    # le diagnostic d'un autre client est invisible (404, pas 403)
    c2 = TestClient(c.app)
    csrf2 = login(c2, cfg, "client", autre)
    assert c2.get(f"/v1/diagnoses/{r.json()['reference']}").status_code == 404


def test_le_client_n_apprend_pas_qu_une_manipulation_a_ete_detectee(plat):
    """R-SEC-006 : ni le chemin de déblocage, ni les sources, ni le texte ne trahissent la détection."""
    c, cfg, _, _ = plat
    did = dossier_pour("C-SEC-001")
    csrf = login(c, cfg, "client", did)
    d = c.post("/v1/diagnoses", json={}, headers=csrf).json()
    assert d["human_validation_required"] and d["unblock_path"] == [] and d["sources"] == []
    texte = json.dumps(d).lower()
    assert not any(m in texte for m in ("manipulation", "sécurité", "securite", "injection", "suspect"))
    e = c.get(f"/v1/diagnoses/{d['reference']}/explanation").json()
    assert e["steps"] == []


@pytest.mark.parametrize("question", ["Je n'ai pas reçu mon code OTP", "J'ai oublié mon mot de passe, que faire ?"])
def test_questions_legitimes_sur_otp_et_mot_de_passe_ne_sont_pas_refusees(plat, question):
    """Régression trouvée en comparant les deux prototypes : un refus ici bloquerait toute une famille de blocages."""
    c, cfg, _, _ = plat
    csrf = login(c, cfg)
    d = c.post("/v1/diagnoses", json={"dossier_id": dossier_pour("C-OTP-001"), "question": question},
               headers=csrf).json()
    assert all(x["family"] != "F10" for x in d["causes"]), d["causes"]


def multi_cause(c, csrf):
    for did in LocalKitPort("public").dossiers:
        d = c.post("/v1/diagnoses", json={"dossier_id": did}, headers=csrf).json()
        simples = [x for x in d["causes"] if x["family"] not in ("F10", "F00")]
        if len(simples) >= 2 and not d["abstained"]:
            return d
    pytest.skip("aucun dossier multi-causes dans le kit")


def test_simulation_en_lecture_seule_et_bornee_au_diagnostic(plat):
    c, cfg, port, _ = plat
    csrf = login(c, cfg)
    d = multi_cause(c, csrf)
    avant = copy.deepcopy(port.dossiers)
    cause = d["causes"][0]["cause_id"]
    r = c.post(f"/v1/diagnoses/{d['trace_id']}/preview", json={"cause_id": cause}, headers=csrf)
    assert r.status_code == 200, r.text
    p = r.json()
    assert cause in [x["cause_id"] for x in p["cleared"]] and p["synthetic"] is True
    assert p["remaining"] and p["simulated_disposition"] != "resolved"
    assert port.dossiers == avant                                                      # rien n'a été écrit
    hors = c.post(f"/v1/diagnoses/{d['trace_id']}/preview", json={"cause_id": "C-ORI-002"}, headers=csrf)
    assert hors.status_code == 409 or "C-ORI-002" in [x["cause_id"] for x in d["causes"]]
    # vue client : titres seulement
    c2 = TestClient(c.app)
    csrf2 = login(c2, cfg, "client", d["dossier_id"])
    dc = c2.post("/v1/diagnoses", json={}, headers=csrf2).json()
    steps = c2.get(f"/v1/diagnoses/{dc['reference']}/explanation").json()["steps"]
    assert not re.search(r"\bC-[A-Z]{3}-\d{3}\b", json.dumps(steps))
    pc = c2.post(f"/v1/diagnoses/{dc['reference']}/preview", json={"step": steps[0]["step"]}, headers=csrf2)
    assert pc.status_code == 200 and not re.search(r"\bC-[A-Z]{3}-\d{3}\b", json.dumps(pc.json()))
    assert c2.post(f"/v1/diagnoses/{dc['reference']}/preview", json={"cause_id": cause}, headers=csrf2).status_code == 409


def test_simulation_refusee_pour_manipulation_et_repli(plat):
    c, cfg, _, _ = plat
    csrf = login(c, cfg)
    d = c.post("/v1/diagnoses", json={"dossier_id": dossier_pour("C-SEC-001")}, headers=csrf).json()
    r = c.post(f"/v1/diagnoses/{d['trace_id']}/preview", json={"cause_id": d["causes"][0]["cause_id"]}, headers=csrf)
    assert r.status_code == 409


def test_preuve_et_simulation_refusees_si_le_dossier_a_change(plat):
    c, cfg, port, _ = plat
    csrf = login(c, cfg)
    did = dossier_pour("C-IDN-001")
    d = c.post("/v1/diagnoses", json={"dossier_id": did}, headers=csrf).json()
    ok = c.get(f"/v1/diagnoses/{d['trace_id']}/explanation")
    assert ok.status_code == 200 and ok.json()["steps"][0]["facts"] and ok.json()["steps"][0]["rules"]
    port.dossiers[did]["updated_at"] = "2026-09-26T09:59:00"
    assert c.get(f"/v1/diagnoses/{d['trace_id']}/explanation").status_code == 409
    cause = d["causes"][0]["cause_id"]
    assert c.post(f"/v1/diagnoses/{d['trace_id']}/preview", json={"cause_id": cause}, headers=csrf).status_code == 409


def test_escalade_confirmee_par_un_agent_seulement_idempotente_et_perimee_si_dossier_change(plat):
    c, cfg, port, _ = plat
    csrf = login(c, cfg)
    did = dossier_pour("C-UNK-000")
    d = c.post("/v1/diagnoses", json={"dossier_id": did}, headers=csrf).json()
    assert d["human_validation_required"]
    # un acquittement fourni par l'appelant n'existe pas : le champ est refusé
    assert c.post("/v1/escalations", json={"diagnosis_id": d["trace_id"], "human_ack": True},
                  headers=csrf).status_code == 422
    draft = c.post("/v1/escalations", json={"diagnosis_id": d["trace_id"], "note": "fictive"}, headers=csrf).json()
    assert draft["status"] == "draft"
    assert c.post("/v1/escalations", json={"diagnosis_id": d["trace_id"]}, headers=csrf).json()["id"] == draft["id"]
    ev = {"Authorization": f"Bearer {cfg.evaluator_token}"}
    assert c.post("/v1/escalations", json={"diagnosis_id": d["trace_id"]}, headers=ev).status_code == 403
    assert c.post(f"/v1/escalations/{draft['id']}/confirm", headers=ev).status_code == 403
    port.dossiers[did]["updated_at"] = "2026-09-26T09:59:00"
    assert c.post(f"/v1/escalations/{draft['id']}/confirm", headers=csrf).status_code == 409
    port.dossiers[did]["updated_at"] = LocalKitPort("public").dossiers[did]["updated_at"]
    for _ in range(2):
        r = c.post(f"/v1/escalations/{draft['id']}/confirm", headers=csrf)
        assert r.status_code == 200 and r.json()["status"] == "confirmed" and r.json()["simulated"] is True
    events = c.get("/v1/audit", params={"dossier_id": did}).json()
    assert [e["event"] for e in events["events"]].count("escalation_confirmed") == 1


def test_journal_d_audit_chaine_detecte_la_falsification(plat):
    c, cfg, _, factory = plat
    csrf = login(c, cfg)
    c.post("/v1/diagnoses", json={"dossier_id": dossier_pour("C-IDN-001")}, headers=csrf)
    c.post("/v1/diagnoses", json={"dossier_id": dossier_pour("C-DOC-001")}, headers=csrf)
    assert c.get("/v1/audit").json()["integrite"]["ok"] is True
    with factory.begin() as db:
        db.scalars(select(AuditRow).order_by(AuditRow.id)).first().detail = {"cause": "falsifiee"}
    assert c.get("/v1/audit").json()["integrite"]["ok"] is False
    with factory() as db:
        assert verify_audit(db)[0] is False


def test_trace_rejouable_apres_redemarrage_et_limitation_de_debit(plat):
    c, cfg, _, _ = plat
    csrf = login(c, cfg)
    d = c.post("/v1/diagnoses", json={"dossier_id": dossier_pour("C-IDN-001")}, headers=csrf).json()
    t = c.get(f"/v1/diagnoses/{d['trace_id']}/trace").json()
    assert t["integrite"]["ok"] and t["entries"]
    cfg2 = Settings(database_url=cfg.database_url, requests_per_minute=3, demo_mode=True)
    with TestClient(create_app(cfg2, LocalKitPort("public"), None, resolve("none"))) as c2:
        csrf2 = login(c2, cfg2)
        codes = [c2.post("/v1/diagnoses", json={"dossier_id": dossier_pour("C-IDN-001")}, headers=csrf2).status_code
                 for _ in range(5)]
    assert codes[-1] == 429 and codes[0] == 200


def test_secrets_par_defaut_refuses_hors_demonstration(tmp_path):
    with pytest.raises(RuntimeError, match="Secrets par défaut"):
        create_app(Settings(database_url=f"sqlite:///{tmp_path/'x.db'}"), LocalKitPort("public"), None, resolve("none"))
    ok = Settings(database_url=f"sqlite:///{tmp_path/'y.db'}", agent_password="a-long-unique-passphrase",
                  client_password="another-long-unique-passphrase", evaluator_token="t" * 32)
    create_app(ok, LocalKitPort("public"), None, resolve("none"))


def test_un_essai_de_connexion_rate_ne_bloque_pas_les_autres_utilisateurs(plat):
    c, cfg, _, _ = plat
    for _ in range(12):
        c.post("/v1/auth/login", json={"username": "agent", "password": "mauvais"})
    assert c.post("/v1/auth/login", json={"username": "agent", "password": "mauvais"}).status_code == 429
    mien = dossier_pour("C-IDN-001")
    r = c.post("/v1/auth/login", json={"username": "client", "password": cfg.client_password, "dossier_id": mien})
    assert r.status_code == 200


def test_audit_concurrent_ne_fourche_pas_la_chaine(plat):
    from concurrent.futures import ThreadPoolExecutor
    c, cfg, _, factory = plat
    csrf = login(c, cfg)
    did = dossier_pour("C-IDN-001")
    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(lambda _: c.post("/v1/diagnoses", json={"dossier_id": did}, headers=csrf).status_code, range(16)))
    assert set(codes) == {200}
    with factory() as db:
        assert verify_audit(db)[0] is True
        assert len(list(db.scalars(select(AuditRow)))) == 16


def test_scenarios_de_demonstration_couvrent_toutes_les_causes_et_restent_en_mode_demo(plat, tmp_path):
    from engine.graph import CAUSE_BY_ID
    c, cfg, _, _ = plat
    s = c.get("/v1/auth/demo").json()["scenarios"]
    assert {x["cause_id"] for x in s} == set(CAUSE_BY_ID) and any(x["family"] == "F11" for x in s)
    sain = Settings(database_url=f"sqlite:///{tmp_path/'p.db'}", agent_password="a-long-unique-passphrase",
                    client_password="another-long-unique-passphrase", evaluator_token="t" * 32)
    with TestClient(create_app(sain, LocalKitPort("public"), None, resolve("none"))) as prod:
        assert prod.get("/v1/auth/demo").status_code == 404
