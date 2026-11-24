<div align="center">

# 🧭 BOUSSOLA

### Pourquoi mon dossier BNA H24 est-il bloqué ?

**Un assistant qui diagnostique les blocages du parcours « Devenir client », cite la règle applicable,
et s'arrête pour demander un humain quand il ne sait pas.**

*Hackathon BNA Bank × IndabaX Tunisia — édition 2026*

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?logo=nextdotjs&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/tests-101%20Python%20%2B%206%20navigateur-0f6b47)
![Données](https://img.shields.io/badge/données-100%25%20synthétiques-b8860b)
![Décision bancaire](https://img.shields.io/badge/décision%20bancaire-aucune-a12d2d)

[**Démarrer**](#-démarrer-en-5-minutes) ·
[**Comment ça marche**](#-comment-ça-marche) ·
[**Les mesures**](#-les-mesures-sans-fard) ·
[**Les diagrammes**](docs/diagrams.md) ·
[**Guide d'équipe**](docs/GUIDE-EQUIPE.md)

<br/>

<img src="docs/img/client.png" alt="Espace client : l'étape où le dossier bloque et ce qu'il reste à faire" width="88%"/>

</div>

---

## Sommaire

1. [Le problème](#-le-problème)
2. [Le parti pris](#-le-parti-pris--le-diagnostic-est-déterministe-le-modèle-traduit)
3. [Comment ça marche](#-comment-ça-marche)
4. [Ce que l'on voit](#-ce-que-lon-voit)
5. [Les mesures, sans fard](#-les-mesures-sans-fard)
6. [Garde-fous](#-garde-fous)
7. [Démarrer en 5 minutes](#-démarrer-en-5-minutes)
8. [Modèle de langage : Groq](#-modèle-de-langage--groq-facultatif)
9. [Architecture et diagrammes](#-architecture-et-diagrammes)
10. [Structure du dépôt](#-structure-du-dépôt)
11. [Limites assumées](#-limites-assumées)
12. [Documentation](#-documentation)

---

## 🎯 Le problème

> Un message d'erreur générique ne dit pas si le blocage vient d'un **document manquant**, d'une
> **incompatibilité entre le profil et l'offre**, d'une **règle d'unicité** ou d'une simple **lenteur technique**.
> Le client abandonne, et l'agent perd du temps à reconstituer la cause à partir de plusieurs statuts.

BOUSSOLA lit l'état réel d'un dossier à travers **deux API en lecture seule**, identifie la cause parmi un
**référentiel fermé de 37 causes**, **cite la règle applicable**, calcule le **chemin de déblocage le plus court**,
et **s'arrête pour demander un humain** quand les faits ne permettent pas de trancher.

<table>
<tr>
<td width="33%" valign="top">

**👤 Pour le client**<br/>
Où ça bloque, en mots simples, dans sa langue (FR · AR · EN), avec ce qu'il reste à faire — et les agences de
remplacement quand la sienne est fermée.

</td>
<td width="33%" valign="top">

**🧑‍💼 Pour l'agent**<br/>
Cause, confiance, faits observés, règles citées, message prêt à transmettre, et une escalade préparée en deux temps.

</td>
<td width="33%" valign="top">

**📋 Pour le jury**<br/>
Chaque chiffre est recalculable, chaque exigence interdite est un mécanisme testé, chaque limite est écrite.

</td>
</tr>
</table>

Il ne prend **aucune décision bancaire**. Jamais.

---

## 💡 Le parti pris : le diagnostic est déterministe, le modèle traduit

La plupart des approches donnent le dossier à un modèle de langage et lui demandent « pourquoi est-ce bloqué ? ».
Cela produit des causes **plausibles et invérifiables**. Ici, la chaîne est inversée :

```mermaid
flowchart LR
  IN(["dossier + état<br/>H24 et CSA"]) --> A
  subgraph DET["Chemin déterministe — aucun modèle"]
    direction LR
    A["<b>A</b> · faits typés<br/><i>doc.cin.expire = true</i>"] --> B["<b>B</b> · graphe causal<br/>37 causes · prérequis durs"]
    B --> P["<b>Politique</b><br/>s'abstenir si doute"]
    P --> D["<b>D</b> · chemin de<br/>déblocage minimal"]
  end
  B -. "égalité seulement" .-> C["<b>C</b> · arbitrage<br/>modèle · liste fermée"]
  C -.-> P
  D --> E["<b>E</b> · explication<br/>gabarit FR · modèle pour AR/EN"]
  E --> OUT(["Diagnostic<br/>+ règle citée<br/>+ preuve"])
  style DET fill:#e6f2ec,stroke:#0f6b47
  style C fill:#fdf4e0,stroke:#b8860b
```

| Le modèle **ne peut pas**… | Parce que… |
|---|---|
| inventer une cause | il ne choisit que parmi des nœuds dont les **prérequis factuels sont déjà vérifiés** |
| inventer une règle | les citations viennent des **ancres déclarées par le nœud retenu**, pas d'une recherche de similarité |
| décider à la place de la BNA | aucun texte libre n'atteint le chemin de décision |
| être indispensable | **débranché, le système fonctionne** — plus laconique, un peu plus prudent |

---

## ⚙️ Comment ça marche

Le moteur ne connaît ni sessions ni rôles ; la plateforme les ajoute autour de lui.

```mermaid
flowchart TB
  subgraph NAV["Navigateur — Next.js"]
    C["/client<br/>FR · AR · EN"]
    A["/agent<br/>preuve · trace"]
    J["/jury<br/>mesures"]
  end
  API["<b>Plateforme</b> — FastAPI<br/>sessions · CSRF · rôles · instantané · audit chaîné"]
  DB[("PostgreSQL<br/>ou SQLite")]
  C & A & J --> API
  API --- DB
  API --> ENG["<b>Moteur</b><br/>diagnostic déterministe"]
  ENG ==> BR["<b>Courtier d'outils</b><br/>manifeste · périmètre · budgets · audit"]
  BR --> PORT{{"DataPort<br/>couture d'adaptation"}}
  PORT --> H24["API H24<br/>lecture seule"]
  PORT --> CSA["API CSA<br/>lecture seule<br/>+ 1 écriture acquittée"]
  ENG -. "facultatif" .-> LLM{{"Groq"}}
  style BR fill:#fbeaea,stroke:#a12d2d
  style ENG fill:#e6f2ec,stroke:#0f6b47
```

Trois décisions structurantes :

1. **Le graphe décide, le modèle traduit.** Un nœud causal déclare des `requires` : sans eux, la cause obtient un
   score nul. Un identifiant hors liste renvoyé par le modèle est traité comme une non-réponse.
2. **Les citations viennent des ancres, pas d'une recherche.** Une recherche vectorielle peut ramener une règle voisine
   mais fausse ; une ancre (`R-IDN-003`), non.
3. **Le courtier est la frontière de sécurité, pas le prompt.** Aucun module du moteur ne touche une source de données
   sans passer par lui : manifeste, périmètre de session, budgets, acquittement humain pour la seule écriture.

> **Un parcours en dix étapes**, dont le **choix de l'agence** (comme sur BNA H24) :
> `Orientation → Choix de l'agence → Identité → Coordonnées → Profil → Choix de l'offre → Documents → Signature →
> Validation en agence → Activation`.

Les 16 diagrammes (classes, séquences, états, données, frontières de confiance…) sont dans
**[`docs/diagrams.md`](docs/diagrams.md)**.

---

## 👀 Ce que l'on voit

<table>
<tr>
<td width="50%" valign="top">

**Poste agent** — causes, confiance, faits, règles citées, chemin de déblocage.<br/><br/>
<img src="docs/img/agent.png" alt="Poste agent : causes probables, état constaté, chemin de déblocage"/>

</td>
<td width="50%" valign="top">

**Preuve** — faits observés → règle citée → suite. Refusée si le dossier a changé entre-temps.<br/><br/>
<img src="docs/img/preuve.png" alt="Chaîne de preuve : faits observés, règles citées, suite"/>

</td>
</tr>
</table>

La page `/jury` affiche les mesures ci-dessous, **recalculées** à la demande. Une démonstration filmée de 57 s
est fournie : [`artifacts/BNA_H24_demo.webm`](artifacts/BNA_H24_demo.webm).

---

## 📊 Les mesures, sans fard

Sur le **jeu privé** : 133 dossiers, graine différente, jamais utilisé pour le réglage.

| Mesure | Résultat |
|---|---|
| Cause exacte (top-1), 133 dossiers, 12 familles | **100 %** |
| Rappel des citations | **1.00** (précision 0.65) |
| F1 de l'escalade | **1.00** |
| Ancrage structurel | **1.00** — aucune action ni ancre hors référentiel |
| Abstention | 10,5 % — dont 5 cas d'ambiguïté pure |
| Latence médiane | **< 1 ms** · coût : **0 USD** sans modèle |

Ces chiffres sont obtenus **sans aucun appel à un modèle de langage**.

> ⚠️ **À lire honnêtement.** Ces chiffres portent sur un kit que nous avons écrit nous-mêmes, faute de kit officiel :
> un 100 % y dit surtout que le moteur couvre les cas que nous avons su imaginer. C'est pourquoi le kit contient des
> **variantes difficiles** : valeurs juste sous le seuil, source CSA muette, texte de document légitime qui ressemble
> à une injection, agence fermée mais étape déjà dépassée. L'évaluation a trouvé des défauts réels du moteur
> ([`docs/evaluation.md`](docs/evaluation.md)).

### Sécurité : ce qui est garanti, et ce qui ne l'est pas

| Mesure | Résultat | Lecture |
|---|---|---|
| **Dommage** sur 50 attaques inédites | **0 / 50** | Garanti **par construction** : aucun texte libre n'atteint le chemin de décision. |
| Suite d'attaques (40 cas + 4 légitimes) | 40/40, 0 faux positif | **Réglée dessus** : ne prouve rien sur des formulations inédites. |
| **Détection** d'attaques inédites (24 cas **réservés**) | **8 / 24 (33 %)** | **Faible.** Sert au triage, pas à la sécurité. |
| Faux positifs sur 52 questions légitimes | 0 / 52 | |

La détection n'est donc **pas** ce qui protège : une attaque non détectée reçoit simplement un diagnostic ordinaire,
sans aucune action. Les 16 attaques non détectées sont listées dans [`docs/cas-d-echec.md`](docs/cas-d-echec.md).

**Ce que le modèle ajoute, chiffré :** 5 dossiers sur 133 (3,8 %) présentent une ambiguïté pure ; ce sont les seuls où
l'arbitrage peut changer la réponse.

---

## 🛡️ Garde-fous

Chaque interdit du cahier des charges est traduit en **mécanisme**, pas en consigne.

| Exigence | Mécanisme | Test |
|---|---|---|
| Aucune décision bancaire automatisée | 5 outils déclarés interdits au manifeste, refus tracé | `test_outils_interdits` |
| Une session = un dossier | Le courtier lie la session à un `dossier_id` et refuse tout autre | `test_lecture_d_un_autre_dossier_refusee` |
| Aucune activation autonome | Une seule écriture ; l'acquittement vient d'une **session agent authentifiée**, jamais de la requête | `test_ecriture_sans_acquittement_refusee` |
| Un client n'apprend rien d'interne | Périmètre fixé au login, vues par rôle, aucun code de cause ni score côté client | `test_le_client_n_apprend_pas…` |
| Pas d'explication sur un dossier périmé | Empreinte des deux sources, **409** si elle change | `test_preuve_et_simulation_refusees…` |
| Pas d'invention de règle | Citations issues des ancres du nœud retenu | `test_toute_ancre_citee_existe_dans_le_corpus` |
| Résistance aux injections | Contenus tiers en blocs inertes + détecteur + classifieur | `eval/redteam` — 40 cas |
| En cas de doute, s'arrêter | Règles d'abstention ordonnées | `test_repli_sur_sur_donnees_contradictoires` |
| Traçabilité | Journal d'audit **chaîné par empreinte** | `test_chaine_d_audit_detecte_la_falsification` |

Détail : [`docs/securite.md`](docs/securite.md). Côté plateforme : cookies HttpOnly + CSRF, limiteur de débit, secrets
par défaut refusés hors `DEMO_MODE`, cookie `__Host-` en HTTPS.

---

## 🚀 Démarrer en 5 minutes

**Prérequis :** Python ≥ 3.12 avec [`uv`](https://docs.astral.sh/uv/), Node.js, `make`. Docker en option.

```bash
git clone https://github.com/Skan22/BNA_H24_Final.git && cd BNA_H24_Final

make install        # uv sync + dépendances web (seule étape qui exige le réseau)
make all            # kit → calibration → tests → évaluation publique et privée
make demo           # API simulées :8001 :8002 · API :8000 · interface :3000
```

Ou avec PostgreSQL, tout en conteneurs : `make docker-up`.

Puis ouvrir <http://localhost:3000/login>. Comptes de **démonstration** (à surcharger avant tout partage) :

| Espace | Identifiants | Ce qu'on y voit |
|---|---|---|
| **Client** | numéro de dossier (la liste de démo est proposée) + `client-demo-change-me` | l'étape bloquée, la suite, « Pourquoi cette réponse ? », « Et si c'était réglé ? » |
| **Agent** | `agent-demo-change-me` | causes, **Preuve**, simulation, message à transmettre, trace scellée, escalade en deux temps |
| **Agent** | — | `/jury` : les mesures, recalculées |

Un client n'accède qu'à **son** dossier. Il ne voit ni code de cause, ni score, ni trace.

<details>
<summary><b>Toutes les commandes</b></summary>

```bash
make test          # 101 tests, sans modèle, sans réseau
make eval-private  # le chiffre qui compte : jeu privé, reproductible
make redteam       # suite d'attaques
make probe         # sonde adversariale hors suite (réglage + jeu réservé)
make e2e           # 6 parcours navigateur + accessibilité WCAG 2.1 AA (pile en marche)
make demo-check    # rejoue le script de démonstration contre la pile
make film          # démonstration filmée → artifacts/BNA_H24_demo.webm
make shots         # captures d'écran du README → docs/img/
make verify-kit    # le kit se régénère bit à bit à l'identique
make livrables     # chaque livrable de la proposition existe, le README est cohérent
make llm-check     # fournisseur Groq : clé, modèles, un appel par niveau, diagnostic arabe
make demo-offline  # preuve que tout tourne sans réseau ni clé
```

Ports occupés : `make demo PORT_API=8010 PORT_H24=8011 PORT_CSA=8012 PORT_WEB=3010`.

</details>

---

## 🤖 Modèle de langage : Groq (facultatif)

Le modèle ne sert qu'à **traduire** (arabe, anglais), **départager** deux causes à égalité et **contrôler** les contenus
tiers. Sans clé, tout fonctionne ; l'arabe et l'anglais passent alors par un gabarit annoncé comme tel.

```bash
cp .env.example .env          # puis renseigner GROQ_API_KEY=… (jamais dans un message, jamais committée)
make llm-check                # vérifie la clé et les modèles de VOTRE compte (réseau)
make demo                     # le moteur utilise Groq automatiquement
```

| Variable | Défaut | Rôle |
|---|---|---|
| `GROQ_API_KEY` | — | active Groq |
| `GROQ_MODEL_STRONG` | `openai/gpt-oss-120b` | arbitrage, traduction |
| `GROQ_MODEL_FAST` | `openai/gpt-oss-20b` | classifieur d'injection, contrôle d'ancrage |
| `BOUSSOLA_LLM` | `none` / `groq` | `none` coupe tout modèle |

Les sorties sont en mode JSON, **validées** contre les schémas, redemandées une fois, sinon repli déterministe.
Les mesures (`make eval-private`, `make test`) sont **toujours** calculées sans modèle.

> 🔒 Avec une clé, le texte des documents, les messages et les faits du dossier partent chez Groq, un service externe.
> Acceptable pour ces **données synthétiques** ; **pas** pour de vrais dossiers BNA sans revue de protection des
> données (`docs/securite.md` §8).

---

## 🏗️ Architecture et diagrammes

Tous les diagrammes sont dans **[`docs/diagrams.md`](docs/diagrams.md)**, en Mermaid (affichés par GitHub), dessinés
d'après le code.

| | Diagramme | Type |
|---|---|---|
| 1 | Contexte du système | C4 niveau 1 |
| 2 | Cas d'usage (rôles, interdits) | UML |
| 3 | Conteneurs et déploiement (Docker) | C4 niveau 2 |
| 4 | Pipeline du moteur A → E | flux |
| 5 | Classes — domaine (`Dossier`, `Diagnosis`, `Trace`…) | UML |
| 6 | Classes — `DataPort`, `Broker`, `LLMProvider` | UML |
| 7 | Séquence — un diagnostic client | UML |
| 8 | Séquence — l'escalade en deux temps | UML |
| 9 | Politique d'abstention | organigramme |
| 10 | Parcours en 10 étapes et statuts | UML états |
| 11 | Cycle de vie d'une escalade | UML états |
| 12 | Modèle de données | ER |
| 13 | Frontières de confiance | sécurité |
| 14 | Chaîne d'audit | flux |
| 15 | Raccordement à la BNA | flux |

<details>
<summary><b>Aperçu : séquence d'un diagnostic client</b></summary>

```mermaid
sequenceDiagram
  autonumber
  actor C as Client
  participant P as Plateforme
  participant E as Moteur
  participant B as Courtier
  participant S as H24 / CSA
  participant L as Groq
  C->>P: POST /v1/diagnoses (cookie + CSRF)
  P->>P: rôle, dossier forcé = celui de la session
  P->>S: empreinte des deux sources
  P->>E: diagnose()
  loop lectures (≤ 12)
    E->>B: call(outil)
    B->>B: manifeste ? périmètre ? budget ?
    B->>S: GET lecture seule
  end
  opt ambiguïté pure ou traduction
    E->>L: JSON validé
    L-->>E: réponse (sinon repli déterministe)
  end
  E-->>P: Diagnosis + audit scellé
  P-->>C: vue client — sans code de cause ni score
```

</details>

---

## 📁 Structure du dépôt

```
contracts/   contrats gelés : 37 causes en 11 familles, manifeste d'outils, schémas JSON générés
kit/         corpus (17 documents, 99 règles ancrées) + générateur synthétique déterministe
             scenarios/{public,private}/ — la vérité terrain est dans un fichier que le moteur ne lit jamais
services/    les deux API simulées : parcours H24 (:8001) et back-office CSA (:8002)
engine/      signals · graph · adjudicate · counterfactual · preview · policy · render · verify
             broker (sécurité) · audit (traçabilité) · ports (couture) · llm (Groq, Anthropic, Ollama)
api/         plateforme : /v1 — sessions, rôles, preuve, simulation, escalade, audit
eval/        évaluateur, calibration, suite d'attaques, sonde adversariale
web/         Next.js — /client /agent /jury · tests Playwright + axe
docs/        architecture, diagrammes, sécurité, évaluation, démonstration, vers un pilote
```

**Données : 100 % synthétiques.** Noms, identifiants, montants et documents sont tirés au sort d'une graine ; le
référentiel d'agences est fictif ; le corpus est une réécriture pour l'exercice. Aucun accès à un système de
production BNA. `make verify-kit` prouve que le kit se régénère à l'identique, sans quoi aucun chiffre ne serait
vérifiable.

---

## 🧱 Limites assumées

Une solution qui cache ses limites ne mérite pas la confiance de la banque. Les nôtres :

- **Kit écrit par nous.** Le 100 % mesure la couverture de nos cas, pas la réalité. Aucun dossier réel.
- **Détection d'attaques inédites : 33 %.** La sécurité repose sur l'architecture, pas sur la détection.
- **Pas de SSO ni de MFA** ; limiteur de débit par processus ; pas de migrations de schéma.
- **Qualité de l'arabe avec Groq non mesurée** ; pas d'évaluation de lisibilité par de vrais clients.
- **Valeur non mesurée** sur de vrais abandons de parcours.
- **Seuils et référentiel d'agences fictifs.**

Le chemin vers un pilote réel, en cinq phases, est décrit dans [`docs/vers-un-pilote.md`](docs/vers-un-pilote.md).

---

## 📚 Documentation

| Document | Contenu |
|---|---|
| [`docs/GUIDE-EQUIPE.md`](docs/GUIDE-EQUIPE.md) · [PDF](docs/GUIDE-EQUIPE.pdf) | **À lire en premier** : présenter à la BNA, puis intégrer |
| [`docs/diagrams.md`](docs/diagrams.md) | 16 diagrammes d'architecture et UML |
| [`docs/architecture.md`](docs/architecture.md) | les cinq étages, la dégradation contrôlée |
| [`docs/securite.md`](docs/securite.md) | menaces testées, limites, données envoyées au modèle |
| [`docs/evaluation.md`](docs/evaluation.md) · [`cas-d-echec.md`](docs/cas-d-echec.md) | méthode, mesures, échecs |
| [`docs/grille-bna.md`](docs/grille-bna.md) | la grille d'évaluation, critère par critère |
| [`docs/api.md`](docs/api.md) · `contracts/openapi.json` | contrats d'API |
| [`docs/demonstration.md`](docs/demonstration.md) | script de la démonstration |
| [`docs/vers-un-pilote.md`](docs/vers-un-pilote.md) | du hackathon au pilote |
| [`docs/fusion.md`](docs/fusion.md) | origine de chaque pièce (moteur Boussola + plateforme « H24 Diagnostic Lab ») |

<div align="center">

<sub>BOUSSOLA explique. Elle ne décide jamais.</sub>

</div>
