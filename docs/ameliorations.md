# Améliorations, et ce que dit le site BNA

## Ce que l'on a pu (et pas pu) lire du site BNA

Les pages officielles `bna.tn` et `mybnah24.bna.tn` **n'étaient pas joignables** depuis l'environnement de
développement (connexion refusée) : aucune page officielle n'a été lue en entier. Ce qui suit vient d'**extraits de
moteur de recherche** et d'**un article de presse de juillet 2022** (Kapitalis) ; à vérifier sur le site avant tout usage.

| Constat public | Source | Effet sur la solution |
|---|---|---|
| Les « Packs H24 » permettent de souscrire en ligne aux packs **Prime, Prime Plus, Premium, Premium Plus** | [Kapitalis, 19/07/2022](https://kapitalis.com/tunisie/2022/07/19/packs-h24-de-la-bna-une-souscription-100-en-ligne-aux-offres-packagees/) | Le catalogue utilise désormais les noms publics (Prime, Prime Plus, Premium) au lieu de noms inventés. **Premium Plus n'est pas modélisé.** |
| Parcours en quatre étapes : choisir l'agence, remplir le formulaire, choisir le package, **signer électroniquement ou finir en agence** | idem | **Ajouté** : étape CHOIX_AGENCE (2e du parcours), 5 causes en famille F11 (aucune agence, fermée, ne prend pas en charge le profil, code inconnu, signature électronique à finaliser en agence), référentiel d'agences fictif. |
| Pack **TWENSA** : Tunisiens résidant à l'étranger, présenté comme gratuit, trois variantes ; souscription en ligne ou en agence | extraits de recherche (bna.tn, brochure) | Pack non résident renommé TWENSA, gratuit. Les trois variantes ne sont pas modélisées. |
| **Hello Student Pack** : gratuit ; en agence, CIN + justificatif d'inscription universitaire | extrait de recherche (bna.tn) | Pack jeune renommé Hello Student, gratuit. La borne d'âge (30 ans) reste une hypothèse de démonstration. |
| Packs Prime→Premium Plus présentés pour salariés, retraités, professions libérales | extrait de recherche (bna.tn) | Un statut « profession libérale » **n'exclut pas** un pack particulier : cohérent avec la règle déjà corrigée dans le moteur. |

Les **seuils de revenu, tarifs mensuels des packs payants, délais et listes de pièces** du kit restent fictifs : aucun
document officiel ne les a confirmés.

## Fait dans cette passe

**Sécurité de la plateforme.** Secrets par défaut refusés hors mode démonstration · limiteur de connexion par
(adresse, compte, dossier) — derrière le relais web, l'adresse vue est celle du relais, l'ancien limiteur bloquait
tous les utilisateurs après dix essais · sessions expirées purgées · écritures d'audit sérialisées (la chaîne ne peut
plus fourcher sous concurrence) · cookie `__Host-` en HTTPS · `/health` public ne révèle plus rien (détails réservés
au personnel) · en-têtes de sécurité et CSP côté web.

**Moteur.** Date de référence configurable (`BOUSSOLA_AS_OF=now`) au lieu d'être figée · arabe et anglais **hors ligne**
(gabarit annoncé comme tel) au lieu d'un champ vide · propriétés d'invariance testées.

**Interface et accessibilité.** Quatre défauts détectés par axe corrigés (voir `docs/evaluation.md`) · texte arabe
balisé `lang`/`dir` · parcours client et agent testés dans un vrai navigateur.

**Exploitation.** Rapports de mesure recalculés à la construction de l'image · contrôles de santé et ordre de
démarrage dans Compose · extra `postgres` déclaré (plus d'installation ad hoc dans l'image).

## À faire ensuite (par priorité)

1. **Valider avec la BNA** la liste des packs (Premium Plus, variantes TWENSA), les pièces par profil et les seuils.
2. **Enrichir l'étape « choix de l'agence »** (ajoutée, voir `docs/cas-d-echec.md`) avec les vraies données : horaires, capacité,
   zones de desserte, rendez-vous.
3. **Identité client réelle** : aujourd'hui un mot de passe de démonstration + un numéro de dossier. Un pilote exige
   l'authentification bancaire du client et l'habilitation par agence pour les conseillers.
4. **Minimisation des données** : les preuves de l'agent contiennent des écarts de noms issus de l'OCR ; définir ce qui
   est conservé en base et pour combien de temps (aujourd'hui : rien n'est purgé).
5. **Évaluation sur de vrais dossiers qualifiés** : le 100 % actuel mesure la couverture d'un kit synthétique.
6. **Précision des citations (0,60)** : le moteur cite des règles de contexte en plus des règles attendues ; décider
   avec les métiers si c'est un bénéfice ou du bruit.
7. **Limiteur de débit partagé** entre processus, migrations Alembic, supervision (taux d'abstention, dérive des causes).
8. **Détecteur d'injection** : « débloquez mon dossier » et « activez mon compte » déclenchent une escalade même
   dites poliment ; à calibrer sur de vrais messages de clients.
