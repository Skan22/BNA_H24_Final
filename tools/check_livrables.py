"""Vérifie que chaque livrable demandé par la proposition existe, et que le README ne ment pas sur les chiffres.

    python tools/check_livrables.py        (ou : make livrables)

Sortie non nulle si un livrable manque ou si un chiffre du README diverge de ce que le code produit.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
VERT, ROUGE, RAZ = "\033[32m", "\033[31m", "\033[0m"

LIVRABLES = [
    ("Prototype fonctionnel (client et agent)", ["web/app/client/page.jsx", "web/app/agent/page.jsx", "api/main.py"]),
    ("Code source et instructions d'installation", ["README.md", "pyproject.toml", "uv.lock", "Makefile"]),
    ("Schéma d'architecture", ["docs/architecture.md"]),
    ("Documentation des contrats d'API", ["docs/api.md", "contracts/openapi.json", "contracts/diagnosis.schema.json"]),
    ("Rapport de sécurité (menaces testées, limites)", ["docs/securite.md", "eval/redteam/attacks.yaml", "eval/probe.py"]),
    ("Rapport d'évaluation avec les cas d'échec", ["docs/evaluation.md", "docs/cas-d-echec.md", "eval/report-private.json"]),
    ("Jeux de tests reproductibles", ["tests/test_moteur.py", "tests/test_agence.py", "kit/scenarios/private/dossiers.json",
                                      "kit/scenarios/public/dossiers.json", "tools/verify_kit.py"]),
    ("Démonstration filmée", ["artifacts/BNA_H24_demo.webm", "docs/demonstration.md"]),
    ("Fiche : ce qu'il faut pour aller vers un pilote", ["docs/vers-un-pilote.md"]),
    ("Grille d'évaluation BNA, preuve par critère", ["docs/grille-bna.md"]),
    ("Guide de passation pour l'équipe (présentation et intégration)", ["docs/GUIDE-EQUIPE.md"]),
    ("Déploiement en conteneurs", ["Dockerfile", "compose.yaml", "web/Dockerfile"]),
]

echecs: list[str] = []


def ligne(ok: bool, texte: str, detail: str = "") -> None:
    print(f"  {VERT + '✓' if ok else ROUGE + '✗'}{RAZ} {texte}" + (f"  — {detail}" if detail and not ok else ""))
    if not ok:
        echecs.append(texte)


print("Livrables demandés par la proposition\n")
for nom, fichiers in LIVRABLES:
    manquants = [f for f in fichiers if not (ROOT / f).exists()]
    ligne(not manquants, nom, "manquant : " + ", ".join(manquants) if manquants else "")

film = ROOT / "artifacts" / "BNA_H24_demo.webm"
ligne(film.exists() and film.stat().st_size > 200_000, "La vidéo n'est pas vide", "lancer `make film`" if not film.exists() else "")

print("\nCohérence du README avec le code\n")
readme = (ROOT / "README.md").read_text()
from engine.graph import CAUSE_BY_ID, GRAPH  # noqa: E402

n_causes = len(CAUSE_BY_ID)
ligne(f"référentiel fermé de {n_causes} causes" in readme, f"le README annonce {n_causes} causes", "")
ligne(len(GRAPH["nodes"]) == n_causes, "le graphe couvre exactement les causes du contrat")
rapport = ROOT / "eval" / "report-private.json"
if rapport.exists():
    m = json.loads(rapport.read_text())["metrics"]
    ligne(f"{m['n']} dossiers" in readme, f"le README cite {m['n']} dossiers privés", "relancer `make eval-private` puis mettre le README à jour")
    ligne(abs(m["exactitude"]["top1"] - 1.0) < 1e-9 or f"{m['exactitude']['top1']:.0%}".replace("%", " %") in readme,
          "le top-1 du README correspond au rapport", f"rapport : {m['exactitude']['top1']:.1%}")
corpus_docs = len(list((ROOT / "kit" / "corpus").glob("*.md")))
m_doc = re.search(r"(\d+) documents", readme)
ligne(bool(m_doc) and int(m_doc.group(1)) == corpus_docs, f"le README annonce {m_doc.group(1) if m_doc else '?'} documents de corpus",
      f"le dépôt en contient {corpus_docs}")

print()
if echecs:
    print(f"{ROUGE}{len(echecs)} point(s) à corriger : {echecs}{RAZ}")
    sys.exit(1)
print(f"{VERT}Tous les livrables sont présents et le README est cohérent.{RAZ}")
