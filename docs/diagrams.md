# Diagrammes d'architecture et UML

Tous les diagrammes sont en [Mermaid](https://mermaid.js.org/) : GitHub les affiche directement, et ils restent
versionnés comme du texte. Ils sont dessinés **d'après le code** (`contracts/models.py`, `engine/`, `api/`,
`compose.yaml`), pas d'après l'intention. Si le code change, le diagramme doit changer.

| # | Diagramme | Type | Répond à la question |
|---|---|---|---|
| 1 | [Contexte du système](#1-contexte-du-système) | C4 niveau 1 | Qui utilise quoi, et avec quels systèmes ? |
| 2 | [Cas d'usage](#2-cas-dusage) | UML cas d'usage | Que peut faire chaque rôle, et que lui est interdit ? |
| 3 | [Conteneurs et déploiement](#3-conteneurs-et-déploiement) | C4 niveau 2 / déploiement | Quels processus tournent, sur quels ports ? |
| 4 | [Pipeline du moteur](#4-pipeline-du-moteur) | Flux | Comment un dossier devient un diagnostic ? |
| 5 | [Diagramme de classes : domaine](#5-diagramme-de-classes--domaine) | UML classes | Quelles sont les données échangées ? |
| 6 | [Diagramme de classes : accès, sécurité, modèle](#6-diagramme-de-classes--accès-sécurité-modèle) | UML classes | Qui a le droit d'appeler quoi ? |
| 7 | [Séquence : un diagnostic](#7-séquence--un-diagnostic-client) | UML séquence | Que se passe-t-il lors d'un clic ? |
| 8 | [Séquence : l'escalade en deux temps](#8-séquence--lescalade-en-deux-temps) | UML séquence | Comment la seule écriture est-elle protégée ? |
| 9 | [Politique d'abstention](#9-politique-dabstention) | Organigramme | Quand le système s'arrête-t-il ? |
| 10 | [Parcours et statuts du dossier](#10-parcours-et-statuts-du-dossier) | UML états | Où le dossier peut-il bloquer ? |
| 11 | [Cycle de vie d'une escalade](#11-cycle-de-vie-dune-escalade) | UML états | Qui peut faire passer l'escalade d'un état à l'autre ? |
| 12 | [Modèle de données](#12-modèle-de-données) | ER | Qu'est-ce qui est stocké ? |
| 13 | [Frontières de confiance](#13-frontières-de-confiance) | Sécurité | Où sont les contrôles ? |
| 14 | [Chaîne d'audit](#14-chaîne-daudit) | Flux | Comment détecter une falsification ? |
| 15 | [Raccordement à la BNA](#15-raccordement-à-la-bna) | Flux | Que remplace-t-on pour passer au réel ? |

---

## 1. Contexte du système

```mermaid
flowchart LR
  client(["👤 Client<br/>prospect bloqué"])
  agent(["🧑‍💼 Agent d'agence<br/>ou back-office"])
  jury(["📋 Évaluateur<br/>jury"])

  subgraph B["BOUSSOLA"]
    direction TB
    web["Interface web<br/>Next.js"]
    api["Plateforme<br/>FastAPI"]
    eng["Moteur de diagnostic<br/>déterministe"]
    web --> api --> eng
  end

  h24[("API parcours H24<br/>lecture seule")]
  csa[("API back-office CSA<br/>lecture seule<br/>+ 1 écriture acquittée")]
  llm{{"Modèle de langage<br/>Groq · facultatif"}}

  client -- "« pourquoi ça bloque ? »" --> web
  agent -- "diagnostic, preuve,<br/>escalade" --> web
  jury -- "mesures, audit" --> web
  eng -- "GET" --> h24
  eng -- "GET · POST escalade" --> csa
  eng -. "traduction, arbitrage<br/>texte non fiable" .-> llm

  classDef ext fill:#f4f4f4,stroke:#888,color:#222
  class h24,csa,llm ext
```

> Le trait pointillé est le seul qui peut manquer : sans modèle, le diagnostic est identique.

---

## 2. Cas d'usage

```mermaid
flowchart LR
  C(["Client"])
  A(["Agent"])
  E(["Évaluateur"])
  M(["Modèle de langage"])

  subgraph SYS["BOUSSOLA"]
    direction TB
    U1["Voir où mon dossier bloque<br/>et ce qu'il reste à faire"]
    U2["Lire l'explication<br/>en FR / AR / EN"]
    U3["Simuler « et si c'était réglé ? »<br/>(lecture seule)"]
    U4["Voir causes, confiance, faits"]
    U5["Consulter la chaîne de preuve<br/>faits → règle → suite"]
    U6["Copier le message à transmettre"]
    U7["Préparer une escalade"]
    U8["Confirmer l'escalade"]
    U9["Lire les mesures et l'audit"]
    U10["Traduire / départager<br/>deux causes à égalité"]
  end

  C --> U1 & U2 & U3
  A --> U3 & U4 & U5 & U6 & U7 & U8
  E --> U9
  U7 -. "«include»" .-> U4
  U8 -. "«include»" .-> U7
  U2 -. "«extend»" .-> U10
  U10 --- M

  SYS ~~~ X1
  X1["❌ Valider un KYC<br/>❌ Activer un pack<br/>❌ Modifier une règle<br/>❌ Modifier le dossier<br/>❌ Exporter des clients"]
  style X1 fill:#fbeaea,stroke:#a12d2d,color:#7a1f1f
```

Un client n'atteint que **son** dossier. Un évaluateur ne peut ni préparer ni confirmer une escalade. Les cinq actions
interdites sont déclarées au manifeste d'outils : elles sont refusées par le courtier, pas par une consigne.

---

## 3. Conteneurs et déploiement

```mermaid
flowchart TB
  user(["Navigateur"])

  subgraph HOST["Hôte — docker compose"]
    direction TB
    web["web<br/>Next.js :3000<br/>relais /api → API"]
    api["api<br/>FastAPI :8000<br/>moteur + plateforme"]
    h24["h24-mock :8001<br/>parcours H24 simulé"]
    csa["csa-mock :8002<br/>back-office CSA simulé"]
    db[("db<br/>PostgreSQL 17")]
  end

  groq{{"api.groq.com<br/>HTTPS · si GROQ_API_KEY"}}

  user -- "HTTP 127.0.0.1:3000" --> web
  web -- "HTTP" --> api
  api -- "SQL" --> db
  api -- "clé de service" --> h24
  api -- "clé de service" --> csa
  api -. "JSON validé" .-> groq

  api -. "depends_on: service_healthy" .-> db
  api -. "depends_on: service_healthy" .-> h24
  api -. "depends_on: service_healthy" .-> csa
  web -. "depends_on: service_healthy" .-> api

  classDef ext fill:#f4f4f4,stroke:#888,color:#222
  class groq ext
```

Sans Docker : `make demo` lance les mêmes processus avec SQLite et le kit local (`BOUSSOLA_PORT=local`). Les ports sont
liés à `127.0.0.1` ; seul le service `api` parle au modèle.

---

## 4. Pipeline du moteur

```mermaid
flowchart TB
  IN["dossier_id + question"] --> OPEN["open_session<br/>1 session = 1 dossier"]
  OPEN --> WORLD["build_worldview<br/>lectures via le courtier"]
  WORLD --> QUA["quarantaine<br/>classifieur d'injection<br/>(modèle rapide, facultatif)"]
  QUA --> A

  subgraph DET["Chemin déterministe — aucun modèle"]
    A["A · signals<br/>faits typés"] --> B["B · graphe causal<br/>37 causes · requires · inhibits"]
    B --> POL["Politique<br/>6 arrêts ordonnés"]
    POL --> D["D · counterfactual<br/>chemin de déblocage minimal"]
  end

  B -. "égalité entre familles<br/>et référentiels d'accord" .-> C["C · adjudicate<br/>modèle fort · liste fermée"]
  C -. "réordonne, n'ajoute rien" .-> POL

  D --> CIT["Citations<br/>ancres du nœud retenu"]
  CIT --> E["E · render<br/>client FR (gabarit) · agent"]
  E -. "ar / en" .-> TR["traduction<br/>modèle ou gabarit annoncé"]
  E --> VER["verify<br/>ancrage structurel + modèle"]
  VER --> OUT["Diagnosis<br/>causes · chemin · sources<br/>trace · tête d'audit"]

  style DET fill:#e6f2ec,stroke:#0f6b47
  style C fill:#fdf4e0,stroke:#b8860b
  style QUA fill:#fdf4e0,stroke:#b8860b
  style TR fill:#fdf4e0,stroke:#b8860b
```

Vert : toujours exécuté. Ambre : facultatif ; en son absence le moteur s'abstient plus souvent, il n'invente rien.

---

## 5. Diagramme de classes : domaine

Les modèles Pydantic de `contracts/models.py`. Les types de la **sortie** (bas) sont ceux de l'API.

```mermaid
classDiagram
  direction LR

  class Dossier {
    +str dossier_id
    +Step step
    +Status status
    +str error_code
    +str canal
    +str created_at
    +str updated_at
  }
  class Prospect {
    +str prospect_id
    +str date_naissance
    +str nationalite
    +Residence residence
    +StatutPro statut_pro
    +int revenu_mensuel_declare
  }
  class Document {
    +str doc_id
    +DocType type
    +DocStatut statut
    +str expire_le
    +float ocr_confidence
    +str ocr_text
  }
  class OtpState {
    +int tentatives
    +int max_tentatives
    +str dernier_code_statut
  }
  class SignatureState {
    +str statut
  }
  class AgenceState {
    +str code_agence
    +int sla_heures
    +bool rdv_honore
  }
  class Offre {
    +str pack_code
    +str pack_label
  }
  class Event {
    +str at
    +str source
    +str type
    +str detail
  }

  Dossier "1" *-- "1" Prospect
  Dossier "1" *-- "0..1" Offre
  Dossier "1" *-- "0..*" Document
  Dossier "1" *-- "1" OtpState
  Dossier "1" *-- "1" SignatureState
  Dossier "1" *-- "1" AgenceState
  Dossier "1" *-- "0..*" Event

  class Diagnosis {
    +str trace_id
    +str dossier_id
    +float confidence
    +bool abstained
    +bool human_validation_required
    +list allowed_actions
    +top_cause() str
  }
  class CauseCandidate {
    +str cause_id
    +str family
    +str label_fr
    +float confidence
    +Owner owner
    +list anchors
  }
  class Evidence {
    +str fact
    +Any value
    +float weight
    +str source
  }
  class UnblockStep {
    +int order
    +str action
    +Owner owner
    +int eta_hours
  }
  class Citation {
    +str anchor
    +str doc_id
    +str titre
    +str extrait
    +str version
  }
  class ExplanationClient {
    +str fr
    +str ar
    +str en
    +str traduction
  }
  class ExplanationAgent {
    +str summary
    +str suggested_message
    +str escalation_draft
  }
  class Trace {
    +dict graph_scores
    +bool adjudicated
    +float groundedness_score
    +str audit_chain_head
    +int latency_ms
    +str provider
    +float cost_usd
  }
  class ToolCallRecord {
    +int seq
    +str tool
    +str args_digest
    +bool allowed
    +str reason
  }
  class PolicyDecision {
    +str rule
    +bool triggered
    +str detail
  }

  Diagnosis "1" *-- "1..3" CauseCandidate
  CauseCandidate "1" *-- "0..*" Evidence
  Diagnosis "1" *-- "0..*" UnblockStep
  Diagnosis "1" *-- "0..*" Citation
  Diagnosis "1" *-- "1" ExplanationClient
  Diagnosis "1" *-- "1" ExplanationAgent
  Diagnosis "1" *-- "1" Trace
  Trace "1" *-- "0..*" ToolCallRecord
  Trace "1" *-- "0..*" PolicyDecision
  Dossier ..> Diagnosis : «diagnostique»

  class Step {
    <<enumeration>>
    ORIENTATION
    CHOIX_AGENCE
    IDENTITE
    COORDONNEES
    PROFIL
    CHOIX_OFFRE
    DOCUMENTS
    SIGNATURE
    VALIDATION_AGENCE
    ACTIVATION
  }
  class Status {
    <<enumeration>>
    EN_COURS
    EN_ATTENTE
    BLOQUE
    REJETE
    ACTIVE
  }
  class Owner {
    <<enumeration>>
    client
    agence
    back_office
    securite
  }
  Dossier ..> Step
  Dossier ..> Status
  CauseCandidate ..> Owner
```

---

## 6. Diagramme de classes : accès, sécurité, modèle

```mermaid
classDiagram
  direction TB

  class DataPort {
    <<interface>>
    +get_dossier(id) dict
    +list_dossiers(limit) list
    +get_events(id) list
    +get_document_ocr(id, doc) dict
    +get_subscriptions(identite) list
    +get_relations(identite) list
    +search_duplicates(id) list
    +get_etat_csa(id) dict
    +get_agency_queue(code) dict
  }
  class LocalKitPort {
    +split: public | private
  }
  class HttpPort {
    +h24: str
    +csa: str
    +timeout: float
  }
  class BnaPort {
    <<à écrire — voir docs/vers-un-pilote.md>>
  }
  DataPort <|.. LocalKitPort
  DataPort <|.. HttpPort
  DataPort <|.. BnaPort

  class Session {
    +str trace_id
    +str dossier_id
    +str identite
    +bool human_ack
    +int llm_calls
    +elapsed_ms() int
    +budget_exceeded() str
  }
  class Broker {
    -DataPort port
    -Session s
    -_authorize(tool, args)
    +call(tool, args) Any
    +try_call(tool, args) Any
    -_dispatch(tool, args)
  }
  class ToolRefused {
    +str tool
    +str reason
    +str rule
  }
  class AuditLog {
    +str trace_id
    +list entries
    +head() str
    +append(kind, payload) str
    +verify() tuple
    +bundle() dict
  }
  class Manifest {
    <<tools.manifest.yaml>>
    11 outils autorisés
    5 outils interdits
    budgets
  }

  Broker --> DataPort : lit via
  Broker --> Session : contrôle
  Broker ..> Manifest : liste blanche
  Broker ..> ToolRefused : lève
  Session *-- AuditLog
  Broker --> AuditLog : journalise chaque appel

  class LLMProvider {
    <<interface>>
    +name: str
    +usage: Usage
    +structured(system, user, schema, tier) BaseModel
  }
  class GroqProvider {
    +BASE_URL
    -models par niveau
    -key  jamais affichée
  }
  class AnthropicProvider
  class OllamaProvider
  class CassetteProvider {
    rejeu hors ligne
  }
  class ChainProvider {
    essaie dans l'ordre
  }
  class NullProvider {
    toujours indisponible
  }
  LLMProvider <|.. GroqProvider
  LLMProvider <|.. AnthropicProvider
  LLMProvider <|.. OllamaProvider
  LLMProvider <|.. CassetteProvider
  LLMProvider <|.. ChainProvider
  LLMProvider <|.. NullProvider
  ChainProvider o-- LLMProvider

  class Diagnose {
    <<fonction diagnose>>
    +diagnose(port, request, provider) Diagnosis
  }
  Diagnose --> Broker : crée une session
  Diagnose --> LLMProvider : optionnel
```

`NullProvider` n'est pas un cas d'erreur : c'est le mode nominal des mesures. Les sorties du modèle sont validées par
Pydantic ; une sortie invalide est redemandée une fois, puis ignorée.

---

## 7. Séquence : un diagnostic client

```mermaid
sequenceDiagram
  autonumber
  actor C as Client
  participant W as Web (Next.js)
  participant P as Plateforme (api/main.py)
  participant E as Moteur (diagnose)
  participant B as Courtier
  participant S as H24 / CSA
  participant L as Modèle (Groq)
  participant D as Base de données

  C->>W: ouvre /client, demande le diagnostic
  W->>P: POST /v1/diagnoses (cookie + CSRF)
  P->>P: session valide ? rôle client ? limiteur de débit
  P->>P: dossier forcé = celui de la session
  P->>S: snapshot_of(dossier) — empreinte des 2 sources
  P->>E: diagnose(port, requête, provider)
  E->>B: open_session(dossier_id)
  loop lectures (≤ 12 appels)
    E->>B: call(h24.get_dossier, csa.get_etat, …)
    B->>B: manifeste ? périmètre ? budget ?
    B->>S: GET (lecture seule)
    S-->>B: état
    B-->>E: résultat + entrée d'audit
  end
  opt contenus non fiables présents et clé Groq
    E->>L: classifier(enveloppes inertes)
    L-->>E: verdict JSON validé
  end
  E->>E: A faits → B graphe → politique → D chemin
  opt ambiguïté pure
    E->>L: adjudicate(liste fermée)
    L-->>E: cause_id ou « je ne peux pas trancher »
  end
  E->>E: E rendu FR · citations · verify
  opt locale ar ou en
    E->>L: traduire (texte déjà rédigé)
    L-->>E: traduction validée, sinon gabarit
  end
  E-->>P: Diagnosis + journal d'audit scellé
  P->>D: INSERT diagnoses + audit_events (chaîné)
  P->>P: projection par rôle
  P-->>W: vue client : étape, actions, texte — sans code de cause ni score
  W-->>C: « Où ça bloque / Ce qu'il reste à faire »
```

---

## 8. Séquence : l'escalade en deux temps

L'acquittement humain **n'est jamais un champ de requête**. Il est établi par la session agent authentifiée.

```mermaid
sequenceDiagram
  autonumber
  actor A as Agent
  participant P as Plateforme
  participant D as Base
  participant S as Sources (H24 + CSA)
  participant B as Courtier
  participant X as CSA : create_escalation

  A->>P: POST /v1/escalations {diagnosis_id, note}
  P->>P: rôle agent obligatoire (client et évaluateur : 403)
  P->>D: lire le diagnostic
  alt human_validation_required = faux
    P-->>A: 409 « pas d'escalade nécessaire »
  else
    P->>D: INSERT escalations (status = draft, snapshot)
    P->>D: audit « escalation_drafted »
    P-->>A: brouillon + synthèse, rien n'est envoyé
  end

  Note over A: l'agent relit le brouillon

  A->>P: POST /v1/escalations/{id}/confirm
  P->>S: snapshot_of(dossier)
  alt empreinte différente du brouillon
    P-->>A: 409 « le dossier a changé, relancez le diagnostic »
  else dossier inchangé
    P->>B: Session(human_ack = True) — posé par la plateforme
    P->>B: call(csa.create_escalation)
    B->>B: écriture + acquittement ? périmètre ? budget ?
    B->>X: POST (synthétique)
    X-->>B: reference
    B-->>P: reference
    P->>D: status = confirmed + audit « escalation_confirmed »
    P-->>A: confirmé, simulé, référence
  end
```

---

## 9. Politique d'abstention

`engine/policy.py` : les contrôles sont **ordonnés**, et le premier qui s'applique arrête l'évaluation. Ordre voulu :
une contradiction entre les deux systèmes (R-SYN-004) prime sur l'arbitrage par le modèle.

```mermaid
flowchart TB
  START(["causes classées par le graphe"]) --> S1{"1 · contenu ou demande suspects ?<br/>R-SEC-003 / 004"}
  S1 -- oui --> STOP
  S1 -- non --> S2{"2 · budget d'appels, de modèle<br/>ou de temps dépassé ?"}
  S2 -- oui --> STOP
  S2 -- non --> S3{"3 · aucune cause plausible ?"}
  S3 -- oui --> STOP
  S3 -- non --> S4{"4 · H24 et CSA en désaccord<br/>et la cause de tête n'est pas C-SYN ?<br/>R-SYN-004"}
  S4 -- oui --> STOP
  S4 -- non --> S5{"5 · plusieurs familles à égalité<br/>et le modèle n'a pas tranché ?<br/>R-SEC-005"}
  S5 -- oui --> STOP
  S5 -- non --> S6{"6 · confiance calibrée<br/>sous le seuil ?"}
  S6 -- oui --> STOP
  S6 -- non --> OK["Diagnostic retenu<br/>(validation humaine seulement si<br/>la cause l'exige)"]

  STOP["S'ARRÊTER<br/>abstained = vrai · human_validation_required = vrai<br/>message : « un conseiller va regarder »"]

  style STOP fill:#fbeaea,stroke:#a12d2d
  style OK fill:#e6f2ec,stroke:#0f6b47
```

---

## 10. Parcours et statuts du dossier

Les dix étapes du parcours (`Step`), puis les statuts (`Status`). Le diagnostic porte sur l'étape courante.

```mermaid
stateDiagram-v2
  direction LR
  [*] --> ORIENTATION
  ORIENTATION --> CHOIX_AGENCE
  CHOIX_AGENCE --> IDENTITE
  IDENTITE --> COORDONNEES
  COORDONNEES --> PROFIL
  PROFIL --> CHOIX_OFFRE
  CHOIX_OFFRE --> DOCUMENTS
  DOCUMENTS --> SIGNATURE
  SIGNATURE --> VALIDATION_AGENCE
  VALIDATION_AGENCE --> ACTIVATION
  ACTIVATION --> [*]

  note right of CHOIX_AGENCE
    agence fermée ou sans service :
    agences de remplacement nommées
  end note
  note right of DOCUMENTS
    pièce expirée, illisible, manquante
  end note
  note right of VALIDATION_AGENCE
    file d'attente, SLA dépassé,
    rendez-vous non honoré
  end note
```

```mermaid
stateDiagram-v2
  [*] --> EN_COURS
  EN_COURS --> EN_ATTENTE : attend le client,<br/>l'agence ou le back-office
  EN_ATTENTE --> EN_COURS : action effectuée
  EN_COURS --> BLOQUE : erreur technique<br/>ou règle non satisfaite
  EN_ATTENTE --> BLOQUE : délai dépassé
  BLOQUE --> EN_COURS : blocage levé
  BLOQUE --> REJETE : refus de la banque
  EN_COURS --> ACTIVE : activation par la BNA
  ACTIVE --> [*]
  REJETE --> [*]
  note right of BLOQUE
    BOUSSOLA intervient ici : elle explique,
    elle ne débloque ni ne rejette jamais.
  end note
```

---

## 11. Cycle de vie d'une escalade

```mermaid
stateDiagram-v2
  [*] --> Absente
  Absente --> Brouillon : agent · POST /escalations<br/>(seulement si validation humaine requise)
  Brouillon --> Brouillon : nouvel appel → même brouillon (unique par diagnostic)
  Brouillon --> Confirmée : agent · POST /confirm<br/>dossier inchangé · acquittement posé par la plateforme
  Brouillon --> Périmée : le dossier a changé → 409<br/>relancer un diagnostic
  Périmée --> Absente : nouveau diagnostic
  Confirmée --> Confirmée : rappel idempotent
  Confirmée --> [*]

  note right of Confirmée
    Seule écriture du système, vers le CSA simulé.
    Jamais déclenchée par un client,
    un évaluateur ou le modèle.
  end note
```

---

## 12. Modèle de données

`api/db.py` — SQLAlchemy ; SQLite en local, PostgreSQL sous Docker. Le jeton de session n'est jamais stocké en clair.

```mermaid
erDiagram
  SESSIONS {
    string token_hash PK "SHA-256 du jeton"
    string role "agent | client | evaluator"
    string csrf
    string dossier_id "client : 1 session = 1 dossier"
    datetime expires_at
  }
  DIAGNOSES {
    string id PK "= trace_id"
    string dossier_id
    string actor
    string snapshot "empreinte H24 + CSA"
    json payload "Diagnosis complet"
    json bundle "journal d'audit scellé du moteur"
    datetime created_at
  }
  ESCALATIONS {
    string id PK
    string diagnosis_id UK "un brouillon par diagnostic"
    string dossier_id
    string status "draft | confirmed"
    string snapshot
    json payload
    datetime created_at
  }
  AUDIT_EVENTS {
    int id PK "autoincrement"
    string dossier_id
    string actor
    string event
    string trace_id
    json detail
    string at
    string prev "empreinte de la ligne précédente"
    string hash "empreinte de cette ligne"
  }

  DIAGNOSES ||--o| ESCALATIONS : "peut donner"
  DIAGNOSES ||--o{ AUDIT_EVENTS : "trace_id"
  ESCALATIONS ||--o{ AUDIT_EVENTS : "trace_id du diagnostic"
```

Les relations se font par valeur (`trace_id`, `dossier_id`), sans clé étrangère SQL : le journal d'audit doit rester
lisible même si une ligne métier est un jour purgée.

---

## 13. Frontières de confiance

```mermaid
flowchart LR
  subgraph Z0["Zone non fiable"]
    BR["Navigateur<br/>texte client, OCR"]
    TX["Contenus de documents<br/>messages libres"]
  end

  subgraph Z1["Zone plateforme"]
    direction TB
    G1["① Session HttpOnly + CSRF<br/>cookie __Host- si HTTPS"]
    G2["② Rôle : agent · client · évaluateur"]
    G3["③ Périmètre : client = 1 dossier"]
    G4["④ Limiteur de débit"]
    G5["⑤ Instantané : 409 si le dossier change"]
    G6["⑥ Projection par rôle"]
    G1 --> G2 --> G3 --> G4 --> G5 --> G6
  end

  subgraph Z2["Zone moteur"]
    direction TB
    Q["⑦ Contenus tiers en blocs inertes<br/>+ détecteur + classifieur"]
    BK["⑧ Courtier : manifeste, périmètre,<br/>budgets, acquittement"]
    DT["⑨ Décision 100 % déterministe<br/>aucun texte libre n'y accède"]
    Q --> DT
    BK --> DT
  end

  subgraph Z3["Données"]
    SRC[("H24 · CSA<br/>lecture seule")]
    AU[("Audit chaîné")]
  end

  BR --> G1
  TX --> Q
  G6 --> BK
  BK --> SRC
  BK --> AU
  G6 --> AU

  style Z0 fill:#fbeaea,stroke:#a12d2d
  style Z1 fill:#fdf4e0,stroke:#b8860b
  style Z2 fill:#e6f2ec,stroke:#0f6b47
```

Le contrôle ⑦ est **faible** (détection d'attaques inédites : 8/24) et ne porte donc pas la sécurité : c'est ⑨ qui la
porte (0 dommage sur 50 attaques). Voir [`securite.md`](securite.md) et [`cas-d-echec.md`](cas-d-echec.md).

---

## 14. Chaîne d'audit

Chaque entrée contient l'empreinte de la précédente : modifier ou supprimer une ligne rompt la chaîne.

```mermaid
flowchart LR
  G["GENESIS"] --> E0["#0 session.open<br/>prev = GENESIS<br/>hash₀ = H(prev ‖ seq,at,kind,payload)"]
  E0 --> E1["#1 tool.call<br/>prev = hash₀<br/>hash₁"]
  E1 --> E2["#2 policy<br/>prev = hash₁<br/>hash₂"]
  E2 --> E3["#3 diagnosis<br/>prev = hash₂<br/>hash₃"]
  E3 --> HEAD(["tête = hash₃<br/>copiée dans Trace.audit_chain_head"])

  V{{"verify() rejoue la chaîne"}} -. "prev ≠ hash précédent<br/>ou hash ≠ recalcul" .-> BAD["chaînage rompu à l'entrée n"]
  V -. sinon .-> GOOD["chaîne intègre"]
```

Deux chaînes distinctes : celle du **moteur** (par diagnostic, dans `diagnoses.bundle`) et celle de la **plateforme**
(`audit_events`, globale, écrite en série sous verrou, plus verrou consultatif PostgreSQL).

---

## 15. Raccordement à la BNA

Une seule interface à remplacer : `DataPort`. Rien d'autre dans le moteur ne change.

```mermaid
flowchart LR
  subgraph NOW["Aujourd'hui — hackathon"]
    direction TB
    K["kit synthétique<br/>LocalKitPort"]
    M["API simulées<br/>HttpPort → :8001 / :8002"]
  end

  subgraph PORTS["Couture"]
    DP{{"DataPort<br/>9 méthodes en lecture"}}
    CT["engine/port_contract.py<br/>tests de conformité"]
  end

  subgraph LATER["Pilote BNA"]
    direction TB
    R["BnaPort<br/>API H24 réelles, lecture seule"]
    SSO["SSO / MFA pour les agents"]
    PGM["PostgreSQL géré + migrations"]
  end

  K --> DP
  M --> DP
  R --> DP
  DP --- CT
  SSO -.-> PGM

  style LATER fill:#fdf4e0,stroke:#b8860b,stroke-dasharray: 5 5
```

Les cinq phases du pilote (lecture seule → ombre → agents → client assisté → client direct) sont détaillées dans
[`vers-un-pilote.md`](vers-un-pilote.md).
