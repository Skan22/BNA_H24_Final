---
doc_id: DOC-SYN-01
titre: "Synchronisation entre le parcours H24 et le CSA"
version: "2026.1"
effective_date: "2026-03-12"
domaine: technique
source: "Note d'exploitation, réécrite pour le hackathon (données synthétiques)"
---

# Synchronisation entre le parcours H24 et le CSA

## R-SYN-001 — Deux référentiels, un dossier
L'état affiché au prospect provient du parcours H24. L'état utilisé par les
équipes internes provient du CSA. Les deux sont alimentés par le même flux,
mais de manière asynchrone : un écart transitoire est normal.

## R-SYN-002 — Écart admissible
Un écart de moins de quinze minutes entre les deux référentiels est considéré
comme normal et ne donne lieu à aucune action. Au-delà, l'écart est une anomalie
et doit être signalé à l'exploitation.

## R-SYN-003 — Signature non propagée
Une signature électronique enregistrée côté H24 mais absente du CSA au-delà de
quinze minutes bloque la mise en file d'attente en agence. Le dossier paraît
avancé au prospect alors qu'il ne l'est pas côté interne. C'est la
désynchronisation la plus visible et la plus mal comprise.

## R-SYN-004 — Conduite à tenir en cas d'écart
En cas d'écart entre les deux référentiels, aucune conclusion n'est tirée en
faveur de l'un ou de l'autre. Le dossier est escaladé à l'exploitation avec les
deux états constatés et leurs horodatages. L'assistant ne choisit pas quel
référentiel a raison.
