---
doc_id: DOC-GEN-02
titre: "Codes d'erreur H24 et messages affichés"
version: "2026.1"
effective_date: "2026-02-01"
domaine: general
source: "Référentiel technique H24, réécrit pour le hackathon (données synthétiques)"
---

# Codes d'erreur H24 et messages affichés

## R-GEN-010 — Nature des messages affichés
Les messages affichés au prospect sont volontairement génériques pour des
raisons de sécurité. Le message « Votre demande ne peut aboutir pour le moment »
(code H24-000) ne préjuge d'aucune cause précise : il recouvre indifféremment un
document manquant, une incompatibilité d'offre, un doublon ou une indisponibilité
technique. Il ne doit jamais être repris tel quel dans une explication.

## R-GEN-011 — Familles de codes
Les codes sont préfixés par domaine : H24-1xx pour l'identité, H24-2xx pour les
coordonnées et l'OTP, H24-3xx pour les pièces justificatives, H24-4xx pour le
profil, H24-5xx pour l'éligibilité d'une offre, H24-6xx pour l'unicité,
H24-7xx pour le traitement en agence, H24-8xx pour le choix de l'agence et le
mode de finalisation, H24-9xx pour les incidents techniques.

## R-GEN-012 — Codes d'identité
H24-101 pièce d'identité expirée. H24-102 type de pièce non accepté pour
l'offre demandée. H24-103 incohérence entre les données de la pièce et le
formulaire.

## R-GEN-013 — Codes de coordonnées et OTP
H24-201 nombre maximum de tentatives OTP atteint. H24-202 numéro de téléphone
non éligible à l'envoi d'OTP. H24-203 adresse e-mail invalide ou déjà rattachée
à un dossier actif.

## R-GEN-014 — Codes de pièces justificatives
H24-301 pièce obligatoire absente. H24-302 pièce déposée illisible.
H24-303 justificatif dont la date d'émission dépasse la durée de validité.

## R-GEN-015 — Codes de profil
H24-401 champs obligatoires du profil non renseignés. H24-402 revenu déclaré
sans justificatif correspondant. H24-403 situation professionnelle contredite
par les pièces déposées.

## R-GEN-016 — Codes d'éligibilité
H24-501 offre réservée aux résidents. H24-502 revenu inférieur au seuil de
l'offre. H24-503 âge hors des bornes de l'offre. H24-504 domiciliation de
salaire exigée et non constatée.

## R-GEN-017 — Codes d'unicité
H24-601 dossier en double sur le même numéro d'identité. H24-602 coordonnées
déjà rattachées à un autre dossier en cours. H24-603 abonnement déjà actif sur
le pack demandé.

## R-GEN-018 — Codes de traitement en agence
H24-701 dossier en file d'attente de validation. H24-702 délai de traitement
dépassé. H24-703 rendez-vous en agence non honoré.

## R-GEN-019 — Codes techniques
H24-901 désynchronisation entre le parcours H24 et le CSA. H24-902 signature
électronique non propagée. H24-903 indisponibilité d'un service amont.

## R-GEN-020 — Un code n'est pas un diagnostic
Un code d'erreur indique le contrôle qui a échoué, pas la cause qui l'a fait
échouer. Le code H24-000 n'indique rien du tout. Toute explication donnée au
prospect doit reposer sur l'état constaté du dossier et sur la règle applicable,
et non sur la seule lecture du code.

## R-GEN-021 — Codes du choix de l'agence
H24-801 aucune agence choisie. H24-802 agence choisie temporairement indisponible.
H24-803 agence ne prenant pas en charge le profil. H24-804 code d'agence inconnu du
référentiel. H24-805 signature électronique non aboutie, finalisation en agence.
