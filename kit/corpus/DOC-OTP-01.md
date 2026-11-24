---
doc_id: DOC-OTP-01
titre: "Coordonnées du prospect et vérification par OTP"
version: "2026.1"
effective_date: "2026-02-10"
domaine: coordonnees
source: "Procédure interne BNA H24, réécrite pour le hackathon (données synthétiques)"
---

# Coordonnées du prospect et vérification par OTP

## R-OTP-001 — Numéros éligibles à l'OTP
Le code à usage unique n'est envoyé que vers un numéro mobile tunisien, au
format +216 suivi de huit chiffres commençant par 2, 4, 5 ou 9. Les numéros
fixes (préfixes 7x) et les numéros étrangers ne reçoivent pas d'OTP.

## R-OTP-002 — Non-résidents et OTP
Le prospect non-résident sans numéro mobile tunisien reçoit son code par
courriel, sur l'adresse déclarée. Ce basculement est automatique et ne
constitue pas un blocage.

## R-OTP-003 — Nombre de tentatives
Trois saisies erronées consécutives verrouillent la vérification pendant
trente minutes. Le compteur est remis à zéro après ce délai, sans intervention
d'un collaborateur. Il est inutile d'orienter le prospect vers l'agence pour ce
seul motif.

## R-OTP-004 — Durée de validité du code
Un code est valable cinq minutes. Au-delà, il est refusé même s'il est saisi
correctement ; le prospect doit en demander un nouveau.

## R-OTP-005 — Unicité de l'adresse électronique
Une adresse électronique ne peut être rattachée qu'à un seul dossier en cours.
Si elle est déjà utilisée, le prospect doit soit reprendre le dossier existant,
soit déclarer une autre adresse. Cette règle est distincte du contrôle
d'unicité sur l'identité (R-DUP-001).
