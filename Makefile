# BOUSSOLA — BNA H24 × IndabaX Tunisia
# Tout se relance depuis zéro. Aucune étape n'exige de réseau, sauf `install`.

# Variables d'environnement locales (clé Groq, mots de passe) : fichier .env, ignoré par git. Voir .env.example.
-include .env
export

PY      := .venv/bin/python
PYTEST  := .venv/bin/pytest
SPLIT   ?= public
# Ports surchargeables : PORT_API=8010 make demo, si 8000-8002 sont déjà pris.
PORT_API   ?= 8000
PORT_H24   ?= 8001
PORT_CSA   ?= 8002
PORT_WEB   ?= 3000

.DEFAULT_GOAL := help
.PHONY: help install kit contracts calibrate eval eval-private redteam test \
	    mocks api web demo demo-offline clean verify-kit all docker-up e2e film probe livrables llm-check shots

help: ## Afficher cette aide
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "};{printf "  \033[36m%-16s\033[0m %s\n",$$1,$$2}'

install: ## Créer l'environnement et installer les dépendances (seule étape en ligne)
	uv sync --extra dev
	cd web && npm install --no-audit --no-fund

contracts: ## Régénérer schémas JSON et OpenAPI
	$(PY) contracts/generate_schemas.py

kit: ## Régénérer le kit synthétique (déterministe, deux graines)
	$(PY) kit/generate.py

verify-kit: ## Vérifier que le kit régénéré est bit-à-bit identique
	$(PY) tools/verify_kit.py

calibrate: ## Calibrer la confiance sur le jeu PUBLIC uniquement
	$(PY) eval/calibrate.py

redteam: ## Lancer la seule suite d'attaques
	BOUSSOLA_LLM=none $(PY) eval/redteam.py $(SPLIT)

eval: ## Évaluation complète sur le jeu public (garde-fou de régression)
	BOUSSOLA_LLM=none $(PY) eval/run.py --split public --seuil-top1 0.90

eval-private: ## Évaluation sur le jeu privé — le chiffre qui compte (sans modèle : reproductible)
	BOUSSOLA_LLM=none $(PY) eval/run.py --split private --seuil-top1 0.90

test: ## Suite de tests (sans modèle, sans réseau)
	BOUSSOLA_LLM=none $(PYTEST) -q tests

llm-check: ## Vérifie le fournisseur Groq avec votre clé (réseau) : clé, modèles, un appel par niveau, diagnostic arabe
	$(PY) tools/llm_check.py

mocks: ## Démarrer les deux API simulées (:8001 parcours H24, :8002 back-office CSA)
	@$(PY) -m uvicorn services.mock_h24.app:app --port $(PORT_H24) & \
	 $(PY) -m uvicorn services.mock_csa.app:app --port $(PORT_CSA) & \
	 wait

api: ## Démarrer l'API (:8000) sur le kit local
	DEMO_MODE=true $(PY) -m uvicorn api.main:app --port $(PORT_API)

web: ## Démarrer l'interface (:3000)
	cd web && BOUSSOLA_API=http://127.0.0.1:$(PORT_API) npx next dev -p $(PORT_WEB)

demo: ## Tout démarrer : API simulées (clé de service), API plateforme, interface
	@echo "  H24 :$(PORT_H24) · CSA :$(PORT_CSA) · API :$(PORT_API) · interface :$(PORT_WEB)"
	@$(PY) -m uvicorn services.mock_h24.app:app --port $(PORT_H24) & \
	 $(PY) -m uvicorn services.mock_csa.app:app --port $(PORT_CSA) & \
	 sleep 2; BOUSSOLA_PORT=http DEMO_MODE=true \
	   BOUSSOLA_H24=http://127.0.0.1:$(PORT_H24) \
	   BOUSSOLA_CSA=http://127.0.0.1:$(PORT_CSA) \
	   $(PY) -m uvicorn api.main:app --port $(PORT_API) & \
	 sleep 2; cd web && BOUSSOLA_API=http://127.0.0.1:$(PORT_API) npx next dev -p $(PORT_WEB)

demo-check: ## Vérifier les 6 étapes de la démonstration sur la pile en marche
	$(PY) tools/demo_check.py http://127.0.0.1:$(PORT_API)

demo-offline: ## Vérifier que la démonstration tourne sans réseau ni clé d'API
	@echo "Coupure du modèle : BOUSSOLA_LLM=none"
	@BOUSSOLA_LLM=none $(PY) eval/run.py --split private --seuil-top1 0.90

all: kit calibrate test eval eval-private ## Chaîne complète, de zéro aux mesures

docker-up: ## Pile complète en conteneurs (PostgreSQL, mocks, API, web)
	docker compose up --build

e2e: ## Parcours navigateur + accessibilité (pile en marche) ; CHROMIUM_PATH=/usr/bin/chromium si besoin
	cd web && npx playwright test

film: ## Enregistre la démonstration filmée (pile en marche) -> artifacts/BNA_H24_demo.webm
	cd web && npx playwright test -c playwright.demo.config.ts
	$(PY) tools/collect_film.py

shots: ## Captures d'écran du README (pile en marche) -> docs/img/*.png
	cd web && npx playwright test -c playwright.shots.config.ts

probe: ## Sonde adversariale hors suite : jeu de réglage puis jeu réservé
	$(PY) eval/probe.py
	$(PY) eval/probe.py --holdout --detail

livrables: ## Vérifie que chaque livrable demandé par la proposition existe
	$(PY) tools/check_livrables.py

clean: ## Supprimer les artefacts régénérables
	rm -rf eval/report-*.html eval/report-*.json web/.next
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
