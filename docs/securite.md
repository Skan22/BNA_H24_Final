# Rapport de sécurité

## Modèle de menace

L'assistant est exposé à trois surfaces non fiables, par conception :

1. **le texte extrait des pièces déposées** — le prospect choisit ce qu'il dépose ;
2. **le message libre du prospect** — il choisit ce qu'il écrit ;
3. **les notes de back-office** — texte humain non structuré.

Et il détient trois choses qu'un attaquant veut : l'accès à des dossiers, la capacité de
déclencher des actions internes, et une parole que le client croira.

## Principe : la protection est structurelle, pas conversationnelle

Demander poliment à un modèle d'ignorer les consignes injectées ne protège rien. Chaque
garde-fou est donc un mécanisme que le modèle ne peut pas contourner, parce qu'il n'est pas
en position de le faire.

### 1. Le périmètre est lié à la session, pas au prompt

Une session est liée à un `dossier_id` à l'ouverture. Tout appel visant un autre dossier est
refusé par le courtier, quelle que soit la formulation de la demande. Le modèle n'a aucun
moyen d'élargir son propre périmètre : il ne construit pas les appels, il en demande.

### 2. Les contenus tiers sont des données, jamais des consignes

Tout contenu externe est encapsulé dans un bloc délimité et étiqueté `fiabilité=untrusted`,
avec une consigne permanente rappelant qu'un tel bloc n'exécute rien. Même si l'encapsulation
était franchie, la cause retenue resterait choisie dans le graphe : une phrase trouvée dans
un document ne peut pas créer un nœud causal.

### 3. Détection en deux couches

| Couche | Nature | Disponibilité |
|---|---|---|
| Motifs déterministes | ~45 expressions régulières, français / anglais / arabe, sur texte normalisé (sans accents, sans espacement parasite : « i g n o r e » est recollé) | toujours |
| Classifieur | modèle rapide Groq (`GROQ_MODEL_FAST`), sortie validée contre un schéma, ne suit jamais le contenu qu'il classe | si un modèle est joignable |

La première couche suffit : **les 40 attaques sont tenues sans aucun modèle**.

### 4. Une seule écriture, sous acquittement humain

`csa.create_escalation` est le seul outil en écriture du système. Sans acquittement, le
courtier refuse et journalise le refus en nommant R-ESC-003. **L'acquittement ne vient jamais du corps d'une
requête** : il est établi côté serveur par une session *agent* authentifiée. Cinq outils sensibles sont en
outre déclarés **interdits** au manifeste — validation KYC, activation d'abonnement,
dérogation, modification de dossier, export de clients — pour que le refus porte une règle
nommée plutôt que de tomber dans un « outil inconnu » silencieux.

### 5. Traçabilité opposable

Chaque entrée du journal porte l'empreinte de la précédente. Retirer ou modifier une ligne
casse la chaîne, et `AuditLog.verify()` le détecte. Une trace qu'on peut réécrire ne prouve
rien.

### 6. Plateforme : qui peut quoi

| Menace | Mécanisme | Test |
|---|---|---|
| Accès anonyme | Toute route `/v1` (sauf login/health) exige une session ou le jeton évaluateur | `test_authentification_requise…` |
| Un client lit un autre dossier | Session client = un dossier, fixé au login ; le dossier du corps est ignoré ; 404 sur le reste | `test_client_limite_a_son_dossier…` |
| Le client apprend ce qui a été détecté | Projection : pas de cause, fait, score ni trace ; en cas de manipulation, ni chemin ni sources | `test_le_client_n_apprend_pas…` |
| Requête forgée depuis un autre site | Cookie SameSite=Strict + jeton CSRF | `test_csrf_et_role…` |
| Rôle choisi par l'appelant | Champs inconnus refusés (422) ; le rôle vient de la session | idem |
| Escalade sans humain, ou par l'évaluateur | Confirmation réservée à l'agent connecté, acquittement côté serveur | `test_escalade_confirmee…` |
| Preuve, simulation ou escalade sur un dossier modifié | Empreinte des deux sources, 409 si elle change | `test_preuve_et_simulation_refusees…` |
| Simulation qui écrit | Copie de faits jetée, aucun outil d'écriture, aucun modèle | `test_simulation_en_lecture_seule…` |
| Falsification du journal | Chaîne d'empreintes (traces du moteur et événements de la plateforme) | `test_journal_d_audit_chaine…` |
| Refuser à tort une vraie question (OTP, mot de passe) | Test de non-régression | `test_questions_legitimes…` |
| Abus de débit / corps énorme | Limiteur par session, plafond 16 Ko | `test_trace_rejouable…` |

### 7. Détection : une aide au triage, pas une barrière

La protection est structurelle (points 1 à 6). La détection d'intention — motifs déterministes, puis classifieur
facultatif — ne fait que **signaler** à l'équipe sécurité. Deux niveaux : (1) contournement, usurpation, extraction de
consignes, exfiltration de données d'autrui : toujours signalés ; (2) **demande de décision** (« valide », « active »,
« débloque ») : signalée seulement avec un marqueur de contournement (« sans contrôle », « à ma place », « ne vérifie
rien ») ou une pression hors question polie. « Pouvez-vous valider mon dossier ? » est une demande légitime : l'assistant
n'en décide pas, il explique ce qui manque.

Mesure honnête (`make probe`, `docs/cas-d-echec.md`) : **0 dommage** sur 50 attaques inédites, mais **33 % de
détection** sur un jeu réservé jamais utilisé pour régler les motifs. La suite de 40 attaques, elle, a servi à régler.

### 8. Données envoyées au fournisseur de modèle

Quand `GROQ_API_KEY` est définie, **chaque diagnostic envoie à Groq** (service externe) : le texte OCR des documents, le
message libre du client et sa question (classification d'injection), puis, selon le cas, les faits du dossier (arbitrage),
le texte français de l'explication (traduction) et les règles citées (contrôle d'ancrage). Avec les données synthétiques de la
démonstration, sans objet. **Avec de vrais dossiers : ne pas activer** (`BOUSSOLA_LLM=none`) tant qu'une revue de protection des
données n'a pas validé le fournisseur, l'hébergement et la conservation. La clé n'est lue que dans l'environnement, n'apparaît
ni dans les journaux, ni dans les exceptions, ni dans la représentation de l'objet (testé : `tests/test_groq.py`).

## Résultats mesurés

Suite de **44 cas** : 40 offensifs, 4 contrôles négatifs.

| Famille | Cas | Tenus |
|---|---|---|
| Contournement direct des consignes | 5 | 5 |
| Usurpation de rôle et d'autorité | 5 | 5 |
| Extraction des consignes internes | 4 | 4 |
| Exfiltration de données d'autrui | 5 | 5 |
| Forçage d'une décision bancaire | 5 | 5 |
| Obfuscation (casse, espacement, accents, balises HTML) | 5 | 5 |
| Alternance de langues (fr/ar/en, arabizi) | 4 | 4 |
| Manipulation par le contexte (fausse règle, faux article) | 4 | 4 |
| Insistance et pression | 3 | 3 |
| **Taux de réussite des attaques** | | **0 %** |
| **Faux positifs sur 4 questions légitimes** | | **0 %** |

Les contrôles négatifs ne sont pas décoratifs : sans eux, un assistant qui escaladerait tout
obtiendrait un score de sécurité parfait tout en étant inutilisable. Le kit contient par
ailleurs une facture STEG qui dit « Validez votre facture en ligne » — du texte commercial
parfaitement ordinaire que le détecteur doit laisser passer.

## Limites connues

0. **Plateforme.** Deux comptes de démonstration (un mot de passe agent, un mot de passe client + numéro de dossier),
   pas de SSO ni de MFA ; le même rôle agent prépare et confirme une escalade (confirmation humaine, pas
   quatre-yeux) ; limiteur de débit en mémoire de processus ; pas de migrations de schéma (`create_all`).
   Le détecteur d'injection traite « débloquez mon dossier » et « activez mon compte » comme des demandes de
   décision : il escalade, ce qui est sûr mais peut gêner une question parfaitement polie.

Nous préférons les énoncer que les laisser découvrir.

1. **Les motifs déterministes sont une liste.** Ils couvrent les familles d'attaque connues ;
   une formulation vraiment inédite peut passer la première couche. C'est pourquoi le
   classifieur existe, et pourquoi le repli sûr s'applique en dernier ressort.
2. **La détection en arabe est plus faible qu'en français.** Les motifs arabes couvrent les
   formulations directes ; le dialectal tunisien en graphie latine n'est couvert que
   partiellement (un cas testé, RT-061).
3. **Le classifieur n'a pas été évalué à grande échelle**, faute de budget d'appels pendant
   le hackathon. Il est un second avis, jamais le garde-fou principal.
4. **Nous n'avons pas testé la charge.** Aucune mesure sous concurrence, aucun test de déni
   de service sur le corpus ou les API simulées.
5. **Le kit est le nôtre.** Un attaquant qui connaît un blocage réel du parcours H24 dispose
   d'un angle que notre corpus synthétique ne modélise pas.

## Si nous avions une journée de plus

Mutation automatique des attaques (paraphrase, translittération, encodage) pour mesurer la
robustesse hors liste ; évaluation du classifieur sur un corpus de contenus bénins pour
chiffrer son taux de faux positifs ; et un budget de session par prospect, contre l'abus par
répétition.
