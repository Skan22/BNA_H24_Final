"""Vérifie que le kit se régénère à l'identique.

La reproductibilité n'est pas un détail de confort : sans elle, aucun chiffre
d'évaluation n'est vérifiable par un tiers.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def empreintes() -> dict[str, str]:
    return {s: json.loads((ROOT / "kit" / "scenarios" / s / "manifest.json").read_text())["sha256_dossiers"]
            for s in ("public", "private")}


avant = empreintes()
subprocess.run([sys.executable, str(ROOT / "kit" / "generate.py")], check=True, capture_output=True)
apres = empreintes()
for split in avant:
    etat = "identique" if avant[split] == apres[split] else "A CHANGÉ"
    print(f"  {split:8s} {avant[split]} -> {apres[split]}   {etat}")
sys.exit(0 if avant == apres else 1)
