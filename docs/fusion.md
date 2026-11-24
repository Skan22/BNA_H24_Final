# Fusion de deux prototypes

Cette solution réunit deux réalisations du même cahier des charges (`BNA_H24_Proposition.docx`) :

- **Boussola** — un moteur de diagnostic (faits calculés, graphe causal de 37 causes, politique de repli, chemin de
  déblocage, FR/AR/EN, corpus ancré de 99 règles, suite d'attaques) mais sans authentification ni persistance.
- **BNA H24 Diagnostic Lab** — une plateforme (sessions, CSRF, rôles, PostgreSQL, preuve liée au dossier, simulation
  « et si ? », escalade confirmée, Docker, accessibilité) mais dont le « diagnostic » se limitait à lire 23 booléens
  déjà calculés et refusait des questions légitimes sur l'OTP.

## Ce qui vient d'où

| Pièce | Origine | Ce qui a changé |
|---|---|---|
| Moteur : faits, graphe, politique, chemin de déblocage, rendu, vérification, corpus, courtier d'outils, kit, évaluateur, red team | Boussola | Inchangé |
| Authentification, sessions en base, CSRF, plafond de corps, en-têtes, limiteur de débit | Lab | Réécrit autour des rôles et du moteur ; session client = un dossier |
| Vues par rôle | Lab | Réécrit : le client ne reçoit aucun code de cause ; rien ne trahit une détection de manipulation |
| Audit en base | Lab (table) + Boussola (chaîne d'empreintes) | Chaîne d'empreintes appliquée aux événements de la plateforme |
| Preuve et escalade liées à l'état du dossier | Lab | Empreinte des deux sources (dossier + CSA) au lieu de numéros de version |
| Simulation « et si ? » | Lab | Réécrite pour le graphe : on neutralise les prérequis d'une cause (`engine/preview.py`) au lieu d'une table d'effets sur 23 booléens |
| Escalade en deux temps (brouillon → confirmation) | Lab | `human_ack` n'est plus fourni par l'appelant : la confirmation exige une session agent |
| Clé de service sur les API simulées | Lab | Ajoutée aux deux API et au `HttpPort` |
| PostgreSQL, Docker, Compose | Lab | Vérifiés ici (voir ci-dessous) |
| Interface | Boussola (Next.js) | Ajout : connexion, rôles, preuve, simulation, escalade en deux temps, lien d'évitement, focus visible |

## Corrigé en chemin

- Le Lab refusait « Je n'ai pas reçu mon code OTP » et « J'ai oublié mon mot de passe » (regex trop large) ; Boussola
  ne le faisait pas. Un test de non-régression le garde.
- Boussola laissait un client voir, dans son « chemin de déblocage », « Signalement à l'équipe sécurité » sur un
  dossier piégé : cela contredisait R-SEC-006. La projection client le supprime désormais.
- Boussola acceptait un `human_ack` fourni par l'appelant, CORS ouvert à tous, traces en mémoire seulement.

## Volontairement laissé de côté

Conversations multi-messages persistées (la question libre accompagne le diagnostic), archive « participants » et
exécuteur privé du Lab, migrations Alembic.

## Ce qui est vérifié

71 tests Python, 4 parcours navigateur (Playwright, avec contrôle axe WCAG 2.1 AA), évaluations publique et privée,
suite d'attaques (40/40 tenues, 0 faux positif), et `make demo-check` sur la pile locale **et** sur la pile
Docker/PostgreSQL. Les mesures du moteur restent celles d'un kit écrit par ses
auteurs : elles mesurent la couverture, pas la précision sur de vrais dossiers BNA.
