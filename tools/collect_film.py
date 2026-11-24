"""Copie la vidéo la plus récente de la démonstration filmée vers artifacts/BNA_H24_demo.webm."""
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
videos = sorted((ROOT / "artifacts" / "film").glob("**/video.webm"), key=lambda p: p.stat().st_mtime)
if not videos:
    sys.exit("Aucune vidéo trouvée : lancer `make film` avec la pile en marche.")
cible = ROOT / "artifacts" / "BNA_H24_demo.webm"
shutil.copyfile(videos[-1], cible)
print(f"{cible}  ({cible.stat().st_size // 1024} Ko)")
