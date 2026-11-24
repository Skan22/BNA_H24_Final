"""BOUSSOLA — calibration de la confiance.

Un score de graphe n'est pas une probabilité. Annoncer « confiance 100 % »
parce que toutes les arêtes ont matché serait un abus de langage, et le seuil
de repli sûr n'aurait alors aucun sens.

On mesure donc, sur le jeu PUBLIC uniquement, la justesse réelle observée pour
chaque tranche de score brut, et on écrit la table de correspondance. Le jeu
privé n'est jamais utilisé pour calibrer : il servirait alors deux fois.

    python eval/calibrate.py     ->  engine/rules/calibration.json
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.pipeline import build_worldview, open_session, run_deterministic   # noqa: E402
from engine.ports import LocalKitPort                                          # noqa: E402

TRANCHES = [(0.0, 0.5), (0.5, 0.65), (0.65, 0.75), (0.75, 0.85), (0.85, 0.95), (0.95, 1.01)]
# Sous ce nombre d'observations, la fréquence mesurée n'est pas exploitable :
# on garde alors le score brut plutôt que d'inventer une calibration.
MIN_OBSERVATIONS = 8


def collect(split: str = "public") -> list[tuple[float, bool]]:
    port = LocalKitPort(split)
    gt = json.loads((ROOT / "kit" / "scenarios" / split / "ground_truth.json").read_text())
    obs = []
    for did in port.dossiers:
        session, broker, dossier = open_session(port, did, f"cal-{did}")
        _, ranked, _ = run_deterministic(dossier, build_worldview(broker, dossier))
        if ranked:
            obs.append((ranked[0].score, ranked[0].cause_id == gt[did]["cause_id"]))
    return obs


def main() -> None:
    obs = collect("public")
    bins, rapport = [], []
    for lo, hi in TRANCHES:
        dedans = [ok for score, ok in obs if lo <= score < hi]
        if len(dedans) < MIN_OBSERVATIONS:
            valeur = round((lo + min(hi, 1.0)) / 2, 4)
            note = f"{len(dedans)} obs. — trop peu, score brut conservé"
        else:
            valeur = round(sum(dedans) / len(dedans), 4)
            note = f"{len(dedans)} obs. — justesse observée {valeur:.0%}"
        bins.append([lo, hi, valeur])
        rapport.append(f"  [{lo:.2f}, {hi:.2f}) -> {valeur:.2f}   ({note})")

    out = {
        "source": "kit/scenarios/public",
        "n_observations": len(obs),
        "methode": "fréquence de justesse du top-1 par tranche de score brut",
        "note": "Calibré sur le jeu PUBLIC uniquement. Le jeu privé reste non vu.",
        "bins": bins,
    }
    path = ROOT / "engine" / "rules" / "calibration.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"Calibration écrite ({len(obs)} observations) -> {path.relative_to(ROOT)}")
    print("\n".join(rapport))


if __name__ == "__main__":
    main()
