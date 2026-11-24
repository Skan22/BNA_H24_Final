# La grille d'évaluation BNA, critère par critère

Pour chaque critère de la proposition : ce qui est livré, où le vérifier, et ce qui manque. Les notes ne sont pas
attribuées ici : c'est le travail du jury.

| Critère (poids) | Ce que l'on peut vérifier | Où | Ce qui manque ou reste faible |
|---|---|---|---|
| **Exactitude du diagnostic (25 %)** | Cause exacte sur 133 dossiers privés, 12 familles, avec des variantes difficiles (seuils, source muette, agence fermée mais étape dépassée, texte légitime qui ressemble à une injection) ; invariance à l'ordre des documents ; déterminisme | `make eval-private`, `tests/test_invariance.py`, `tests/test_agence.py` | Kit synthétique écrit par les auteurs : le 100 % mesure la couverture. Aucun dossier réel. |
| **Sécurité et maîtrise des risques (20 %)** | Aucun dommage sur 50 attaques inédites ; outils interdits au manifeste ; une session client = un dossier ; confirmation d'escalade par un agent connecté, acquittement jamais fourni par la requête ; CSRF, limiteur de débit, secrets par défaut refusés ; audit chaîné ; plateforme testée au navigateur | `docs/securite.md`, `make probe`, `tests/test_plateforme.py` | **Détection d'attaques inédites : 33 %.** Pas de SSO ni de MFA. Rate limit par processus. |
| **Qualité des explications (15 %)** | Explication sans jargon ni code interne ; chemin de déblocage ordonné par l'étape du parcours ; agences de remplacement nommées ; message prêt à transmettre ; arabe et anglais (modèle, ou gabarit annoncé hors ligne) | `/client`, `/agent` onglet « À transmettre » | Pas d'évaluation de lisibilité par de vrais clients. Arabe hors ligne : gabarit court. |
| **Fidélité et traçabilité (15 %)** | Citations tirées des ancres du nœud retenu (jamais d'une similarité) ; ancrage structurel 1,00 ; chaîne de preuve faits → règle → suite, refusée si le dossier change ; journal du moteur et journal de la plateforme chaînés | onglet « Preuve », `/v1/audit` | Précision des citations 0,65. Corpus réécrit, pas le corpus BNA. |
| **Architecture et qualité technique (10 %)** | Moteur sans sessions + plateforme autour ; port d'adaptation pour brancher les vraies API ; PostgreSQL, Docker avec contrôles de santé ; 101 tests Python, 6 parcours navigateur, kit reproductible bit à bit | `docs/architecture.md`, `make all`, `make docker-up`, `make verify-kit` | Pas de migrations (création de schéma au démarrage). |
| **Expérience utilisateur (10 %)** | Parcours en dix étapes avec l'étape active ; trois langues ; contrôle d'accessibilité automatique (axe, WCAG 2.1 AA) sur les écrans testés ; lien d'évitement, focus visible, texte arabe `lang`/`dir` | `make e2e` | Axe ne couvre pas tout : pas d'essai avec lecteur d'écran ni avec de vrais utilisateurs. |
| **Innovation et potentiel BNA (5 %)** | Diagnostic déterministe, modèle seulement pour traduire et arbitrer ; simulation « et si ? » ; étape « choix de l'agence » et bifurcation de finalisation ; chemin vers un pilote en cinq phases | `docs/vers-un-pilote.md` | Valeur non mesurée sur de vrais abandons de parcours. |

## Livrables demandés

| Livrable | Fichier | Vérifié par |
|---|---|---|
| Prototype fonctionnel (client et/ou agent) | `web/`, `api/`, `engine/` | `make demo-check`, `make e2e` |
| Code source avec instructions d'installation | `README.md`, `Makefile` | `make install && make all` |
| Schéma d'architecture | `docs/architecture.md` | relecture |
| Documentation des contrats d'API | `docs/api.md`, `contracts/openapi.json` | `make contracts` |
| Rapport de sécurité (menaces testées, limites) | `docs/securite.md` | `make probe`, `tests/test_plateforme.py` |
| Rapport d'évaluation avec les cas d'échec | `docs/evaluation.md`, `docs/cas-d-echec.md` | `make eval-private`, `make probe` |
| Jeux de tests reproductibles | `tests/`, `kit/` | `make test`, `make verify-kit` |
| Démonstration filmée | `artifacts/BNA_H24_demo.webm` | `make film` |
| Fiche : aller vers un pilote | `docs/vers-un-pilote.md` | relecture |

`make livrables` vérifie que chaque fichier existe et que le README ne cite pas un chiffre différent de ce que le code
produit.

## Ce que dit la proposition qu'une solution ne doit pas faire

| Interdit | Comment il est tenu |
|---|---|
| Données réelles | tout est tiré au sort d'une graine ; le référentiel d'agences est fictif |
| Validation KYC ou activation autonome | cinq outils interdits au manifeste ; une seule écriture, sous acquittement d'une session agent |
| Invention de règle | les citations viennent des ancres du nœud retenu ; une ancre inconnue est ignorée |
| Décider à la place de la BNA | aucun texte libre n'atteint le chemin de décision ; `resolved` signifie « explication disponible » |
| En cas de doute, deviner | 5 règles d'abstention ordonnées ; 10,5 % d'abstentions sur le jeu privé |
