# Vers un pilote

Ce qui sépare ce démonstrateur d'un pilote en agence. Nous distinguons ce que nous avons
bâti de ce qui reste entièrement à faire.

## Ce qui est prêt à être repris

| Élément | État |
|---|---|
| Taxonomie des causes | 37 causes, 11 familles — celles du cahier des charges. À valider avec les métiers BNA, la structure ne bouge pas. |
| Contrat d'entrée/sortie | Gelé, généré depuis le code, documenté. |
| Courtier d'outils et manifeste | Réutilisable tel quel ; seule la liste des outils change. |
| Journal d'audit chaîné | Réutilisable tel quel. |
| Évaluateur et suite d'attaques | Réutilisables ; seuls les jeux de données changent. |
| Couture d'adaptation (`engine/ports.py`) | Prévue pour cela : un nouveau port, aucun autre fichier touché. |

## Ce qu'un pilote exige et que nous n'avons pas

### 1. Le vrai corpus, et sa gouvernance
Notre corpus est une réécriture : 17 documents, 99 règles ancrées. Le vrai corpus est plus
gros, plus contradictoire, et **il change**. Il faut : un format d'ancre stable dans les
documents source, un processus de versionnement, et un responsable métier par domaine. Une
règle qui change sans que son ancre bouge fait mentir toutes les citations passées.

**Charge estimée :** 3 à 4 semaines, majoritairement métier, pas technique.

### 2. Le vrai graphe causal
Nos 37 causes viennent du cahier des charges. Le vrai parcours en a davantage, et surtout des
pondérations que seules les données de production peuvent établir. Le chemin réaliste :
extraire 6 à 12 mois de dossiers bloqués réels, les faire qualifier par des agents, puis
ajuster poids et seuils sur ces données — et recalibrer la confiance dessus.

### 3. Les données personnelles
Le démonstrateur ne traite que du synthétique. Un pilote touche à des CIN, des revenus, des
pièces d'identité. Il faut : minimisation à l'entrée (le moteur ne reçoit que les champs dont
il a besoin — l'audit de `signals.py` dira lesquels), pseudonymisation dans les journaux,
durée de conservation des traces, et la base légale du traitement.

### 4. L'authentification et l'habilitation
**Fait dans le démonstrateur :** sessions serveur (cookie HttpOnly, CSRF), rôles agent/client, session client liée à un
seul dossier, escalade confirmée par une session agent, audit chaîné en base.
**Reste à faire :** SSO agence et MFA côté conseiller, session bancaire authentifiée côté client (aujourd'hui : un mot de
passe de démonstration + un numéro de dossier), habilitation par agence/portefeuille, séparation préparateur/approbateur
si la BNA l'exige, limiteur de débit partagé entre processus.

### 5. L'humain dans la boucle, avec des engagements
Le système prépare des escalades ; personne n'est encore tenu d'y répondre. Un pilote a
besoin d'une file de traitement, d'un délai de prise en charge, et d'une boucle de retour :
l'agent qui corrige une cause doit pouvoir le dire, et cette correction doit nourrir
l'évaluation.

### 6. L'observation en production
Il faut suivre, en continu : la distribution des causes (une dérive signale un changement de
parcours), le taux d'abstention (s'il monte, le corpus a vieilli), le taux d'escalades
infirmées par les agents, et les motifs de sécurité déclenchés. Le journal d'audit contient
déjà tout ce qu'il faut ; il manque la collecte et les tableaux de bord.

### 7. Ce qui reste à éprouver
Charge et concurrence — jamais testées. Dialogue multi-tours — le moteur répond à une question
à la fois. Arabe dialectal — couvert partiellement, et c'est probablement la langue dans
laquelle un prospect tunisien écrira spontanément.

## Un chemin possible

| Phase | Durée | Contenu | Critère de passage |
|---|---|---|---|
| 0 — Cadrage | 2 sem. | valider la taxonomie avec les métiers ; geler le format d'ancre | 37 causes confirmées ou amendées |
| 1 — Corpus | 4 sem. | ancrer le vrai corpus ; rebrancher le port | citations exactes sur 100 dossiers réels qualifiés |
| 2 — Étalonnage | 4 sem. | ajuster le graphe sur dossiers réels ; recalibrer | top-1 ≥ 85 % sur un jeu réel tenu à l'écart |
| 3 — Pilote agent | 6 sem. | une agence, **poste agent seulement**, aucune vue client | les agents jugent l'aide utile sur ≥ 70 % des dossiers |
| 4 — Pilote client | 6 sem. | vue client, une famille de blocage à la fois | abandons en baisse mesurée sur cette famille |

Commencer par le poste agent n'est pas de la prudence excessive : l'agent est un lecteur
averti qui détectera une erreur que le client croirait. C'est le meilleur filet pendant qu'on
étalonne.

## Ce que nous déconseillons

- **Élargir la taxonomie avant de l'étalonner.** Plus de causes sans données réelles, c'est
  plus d'ambiguïtés et plus d'abstentions.
- **Remplacer le graphe par un modèle de langage seul** parce que ce serait plus rapide à
  faire évoluer. Le graphe est exactement ce qui rend les citations vérifiables et les
  refus défendables.
- **Baisser le seuil d'abstention pour améliorer la couverture.** La valeur du système tient
  à ce qu'il s'arrête quand il ne sait pas.
