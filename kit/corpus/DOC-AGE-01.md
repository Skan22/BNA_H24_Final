---
doc_id: DOC-AGE-01
titre: "Choix de l'agence et mode de finalisation"
version: "2026.1"
effective_date: "2026-04-01"
domaine: agence
source: "Parcours « Packs H24 » (choix de l'agence, formulaire, package, signature électronique ou finalisation en agence), réécrit pour le hackathon (données synthétiques)"
---

# Choix de l'agence et mode de finalisation

## R-AGE-001 — Choisir son agence
La première étape de la souscription en ligne est le choix de l'agence BNA, de
préférence la plus proche du prospect. Cette agence devient l'agence de
rattachement du dossier. Sans agence choisie, le dossier ne peut pas avancer vers
l'étape suivante.

## R-AGE-002 — Agence temporairement indisponible
Une agence peut être fermée temporairement (travaux, fermeture exceptionnelle).
Aucun dossier ne peut lui être rattaché pendant la fermeture : le prospect choisit
une autre agence ouverte. La fermeture n'est pas une anomalie de son dossier.

## R-AGE-003 — Agences et profils pris en charge
Toutes les agences ne prennent pas en charge tous les profils. Certaines
n'accueillent pas les clients résidant à l'étranger (pack TWENSA). Le prospect
choisit alors une agence qui les accueille ; il n'a rien à corriger dans son
profil.

## R-AGE-004 — Code d'agence inconnu
Un code d'agence absent du référentiel est une incohérence de données, pas une
erreur du prospect. Le dossier est transmis au back-office pour correction du
rattachement. Le prospect n'a aucune démarche à effectuer et ne doit pas
recommencer sa demande.

## R-AGE-005 — Signature électronique ou finalisation en agence
La souscription se termine soit par une signature électronique, soit en agence.
Si la signature électronique échoue, ou si l'agence de rattachement ne la propose
pas, le prospect finalise sa souscription en se rendant dans son agence avec sa
pièce d'identité. Aucun document n'est signé à sa place, et l'échec de la
signature électronique n'annule pas le dossier.

## R-AGE-006 — Changer d'agence
Le prospect peut choisir une autre agence tant que la signature n'est pas
intervenue. Après la signature, le changement passe par une demande en agence
(voir R-AGC-005).
