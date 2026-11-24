---
doc_id: DOC-PRF-01
titre: "Profil du prospect et déclaration de revenus"
version: "2026.1"
effective_date: "2026-02-20"
domaine: profil
source: "Procédure interne BNA H24, réécrite pour le hackathon (données synthétiques)"
---

# Profil du prospect et déclaration de revenus

## R-PRF-001 — Champs obligatoires
Sont obligatoires : la situation professionnelle, l'employeur ou
l'établissement d'enseignement le cas échéant, le revenu mensuel net déclaré,
l'adresse de résidence et la finalité déclarée de la relation. Un champ
obligatoire vide bloque le passage à l'étape CHOIX_OFFRE.

## R-PRF-002 — Justification du revenu
Un revenu mensuel déclaré supérieur à 500 dinars doit être appuyé par une pièce
de la liste R-DOC-002. En l'absence de pièce, le revenu est réputé non justifié
et n'est pas retenu pour l'éligibilité aux offres.

## R-PRF-003 — Cohérence de la situation professionnelle
La situation déclarée doit être cohérente avec les pièces déposées : un
prospect déclarant « salarié » sans bulletin de paie ni attestation de travail,
ou déclarant « étudiant » avec des bulletins de paie, est mis en attente d'un
contrôle en agence. L'assistant ne tranche pas cette contradiction.

## R-PRF-004 — Absence de revenu
Un revenu déclaré nul est recevable. Il restreint l'éligibilité aux offres sans
condition de revenu, mais ne motive jamais à lui seul un rejet du dossier.
