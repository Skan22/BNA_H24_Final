"""Génère contracts/*.schema.json (moteur) et contracts/openapi.json (plateforme) — `make contracts`."""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from contracts.models import Diagnosis, DiagnoseRequest, Dossier  # noqa: E402

OUT = pathlib.Path(__file__).parent
for model, name in [(Diagnosis, "diagnosis"), (Dossier, "dossier"), (DiagnoseRequest, "diagnose_request")]:
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://bna-h24.local/contracts/{name}.schema.json"
    (OUT / f"{name}.schema.json").write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
    print(f"  wrote contracts/{name}.schema.json")

from api.config import Settings  # noqa: E402
from api.main import create_app  # noqa: E402

(OUT / "openapi.json").write_text(json.dumps(
    create_app(Settings(database_url="sqlite:///:memory:", demo_mode=True)).openapi(), indent=2, ensure_ascii=False) + "\n")
print("  wrote contracts/openapi.json")
