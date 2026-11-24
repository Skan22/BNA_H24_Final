import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Les tests sont hermétiques : jamais de modèle réel, même si GROQ_API_KEY est définie dans l'environnement ou .env.
# (Les tests du fournisseur utilisent un faux client HTTP ; le test réel est `make llm-check`.)
os.environ["BOUSSOLA_LLM"] = "none"
