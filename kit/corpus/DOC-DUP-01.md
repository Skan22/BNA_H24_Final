---
doc_id: DOC-DUP-01
titre: "Unicité des dossiers et traitement des doublons"
version: "2026.1"
effective_date: "2026-02-01"
domaine: unicite
source: "Procédure interne BNA H24, réécrite pour le hackathon (données synthétiques)"
---

# Unicité des dossiers et traitement des doublons

## R-DUP-001 — Unicité sur l'identité
Un numéro d'identité ne peut porter qu'un seul dossier en cours à la fois. Un
second dossier ouvert sur la même identité est mis en attente et rapproché du
premier par le back-office. Aucun des deux n'est supprimé automatiquement.

## R-DUP-002 — Unicité des coordonnées
Un numéro de téléphone ou une adresse électronique déjà rattachés à un dossier
en cours ne peuvent pas être réutilisés sur un nouveau dossier (voir R-OTP-005).

## R-DUP-003 — Abonnement déjà actif
Si un abonnement au pack demandé est déjà actif sur l'identité du prospect, la
nouvelle souscription est sans objet. Le prospect est orienté vers son espace
client. Ce cas est fréquemment confondu avec un blocage technique.

## R-DUP-004 — Arbitrage
Le choix du dossier à conserver appartient au back-office, qui tient compte de
l'antériorité et de la complétude. Ni le prospect ni l'assistant ne peuvent
désigner le dossier à conserver.
