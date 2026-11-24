# BOUSSOLA — édition fusionnée

**Assistant de diagnostic des blocages du parcours « Devenir client » — BNA H24**
Proposition pour le hackathon BNA Bank × IndabaX Tunisia, édition 2026.

> Un message d'erreur générique ne dit pas si le blocage vient d'un document manquant,
> d'une incompatibilité entre le profil et l'offre, d'une règle d'unicité ou d'une simple
> lenteur technique. Le client abandonne, et l'agent perd du temps à reconstituer la cause
> à partir de plusieurs statuts.

BOUSSOLA lit l'état réel d'un dossier à travers deux API en lecture seule, identifie la cause
parmi un **référentiel fermé de 37 causes**, **cite la règle applicable**, calcule le **chemin
de déblocage le plus court**, et **s'arrête pour demander un humain** quand les faits ne
permettent pas de trancher.

Il ne prend **aucune décision bancaire**. Jamais.

> Cette édition réunit le moteur de diagnostic de Boussola et la plateforme sécurisée du « H24 Diagnostic Lab »
> (sessions, rôles, PostgreSQL, preuve liée au dossier, simulation « et si ? », escalade confirmée, Docker).
> Détail et provenance de chaque pièce : [`docs/fusion.md`](docs/fusion.md).
> **Équipe : commencer par [`docs/GUIDE-EQUIPE.md`](docs/GUIDE-EQUIPE.md)** (présenter à la BNA, puis intégrer).

---

## Le parti pris

> **Le diagnostic est déterministe. Le modèle ne fait que traduire.**

La plupart des approches donnent le dossier à un modèle de langage et lui demandent
« pourquoi est-ce bloqué ? ». Cela produit des causes plausibles et invérifiables.

Ici, la chaîne est inversée :

```
  dossier + état des deux API
     │
  A  extraction de faits typés        Python pur, zéro modèle
     │                                 doc.cin.expire=true, otp.tentatives=3/3,
     │                                 offre.revenu_insuffisant=true (799 < 800)
     │
  B  graphe causal                     37 nœuds, prérequis durs, arêtes pondérées
     │                                 → causes classées + confiance calibrée
     │
  C  arbitrage                         SEULEMENT si deux familles sont à égalité.
     │                                 Le modèle CHOISIT dans la liste fermée
     │                                 ou déclare qu'il ne peut pas trancher.
     │
  D  chemin de déblocage               recherche sur le graphe : l'ensemble minimal
     │                                 d'actions ordonnées qui rend le dossier recevable
     │
  E  rendu client / agent              gabarit français déterministe ;
                                       le modèle ne sert qu'à l'arabe et à l'anglais
```

Conséquence directe : **le modèle ne peut pas inventer une cause**, parce qu'il ne peut
choisir que parmi des nœuds dont les prérequis factuels sont déjà vérifiés. Il ne peut pas
inventer une règle, parce que les citations viennent des ancres déclarées par le nœud retenu
et non d'une recherche de similarité. Et si on le débranche entièrement, le système continue
de fonctionner — plus laconique, et un peu plus prudent.

---

## Mesures

Sur le **jeu privé** (133 dossiers, graine différente, jamais utilisé pour le réglage) :

| Mesure | Résultat |
|---|---|
| Cause exacte (top-1), 133 dossiers, 12 familles | **100 %** |
| Rappel des citations | **1.00** (précision 0.65) |
| F1 de l'escalade | **1.00** |
| Ancrage structurel | **1.00** — aucune action ni ancre hors référentiel |
| Abstention | 10,5 % — dont 5 cas d'ambiguïté pure |
| Latence médiane | **< 1 ms** · coût : **0 USD** sans modèle |

Ces chiffres sont obtenus **sans aucun appel à un modèle de langage** : le diagnostic ne dépend pas du modèle.

### Sécurité : ce qui est garanti, et ce qui ne l'est pas

| Mesure | Résultat | Lecture |
|---|---|---|
| **Dommage** (décision affirmée, configuration révélée, autre dossier exposé, outil interdit) sur 50 attaques inédites | **0 / 50** | Garanti par construction : le chemin de décision est déterministe, aucun texte libre ne l'atteint. |
| Suite d'attaques (40 cas + 4 questions légitimes) | 40/40 tenues, 0 faux positif | **Réglée dessus** : ne prouve rien sur des formulations inédites. |
| **Détection** d'attaques inédites, jeu **réservé** (24 cas, jamais utilisés pour régler) | **8 / 24 (33 %)** | **Faible.** Le détecteur à motifs généralise mal ; il sert au triage, pas à la sécurité. |
| Faux positifs sur 52 questions légitimes (jeux de réglage et réservé) | 0 / 52 | |

La détection n'est donc **pas** ce qui protège : une attaque non détectée reçoit simplement un diagnostic ordinaire,
sans aucune action. Les 16 attaques non détectées du jeu réservé sont listées dans [`docs/cas-d-echec.md`](docs/cas-d-echec.md),
avec ce que l'on ferait ensuite. `make probe` les rejoue.

**À lire honnêtement.** Ces chiffres portent sur un kit que nous avons écrit nous-mêmes, faute de kit officiel : un
100 % y dit surtout que le moteur couvre les cas que nous avons su imaginer. C'est pourquoi le kit contient des
**variantes difficiles** — valeurs juste sous le seuil, source CSA muette, texte de document légitime qui ressemble à
une injection, agence fermée ou sans service mais étape déjà dépassée. L'évaluation a trouvé des défauts réels du
moteur (`docs/evaluation.md`), et la sonde adversariale en a trouvé d'autres, dont un détecteur qui refusait des
questions normales (« Pouvez-vous débloquer mon dossier ? », « Quand sera activé mon pack ? »).

**Ce que le modèle ajoute, chiffré.** **5 dossiers sur 133 (3,8 %)** du jeu privé présentent une ambiguïté pure ; ce
sont les seuls où l'arbitrage par le modèle peut changer la réponse.

`make eval-private` régénère les mesures du moteur, `eval/report-private.html` les détaille par famille.

---

## Démarrage

```bash
make install        # uv sync + dépendances web (seule étape en ligne)
make all            # kit → calibration → tests → évaluation publique et privée
make demo           # API simulées :8001 :8002 · API :8000 · interface :3000
# ou, avec PostgreSQL :
make docker-up
```

Puis <http://localhost:3000/login>. Comptes de démonstration (à surcharger avant tout partage :
`AGENT_PASSWORD`, `CLIENT_PASSWORD`, `BOUSSOLA_MOCK_KEY`, `EVALUATOR_TOKEN`) :

| Espace | Identifiants | Ce qu'on y voit |
|---|---|---|
| Client | numéro de dossier (la liste de démo est proposée) + `client-demo-change-me` | l'étape où ça bloque, ce qu'il reste à faire, « Pourquoi cette réponse ? », « Et si c'était réglé ? » |
| Agent | `agent-demo-change-me` | causes et confiance, onglet **Preuve** (faits → règle → suite), simulation par cause, message à transmettre, trace scellée, escalade en deux temps |
| Agent | — | `/jury` : les mesures ci-dessus, recalculées |

Un client n'accède qu'à **son** dossier, choisi à la connexion. Il ne voit ni code de cause, ni score, ni trace.

Si les ports sont occupés : `make demo PORT_API=8010 PORT_H24=8011 PORT_CSA=8012 PORT_WEB=3010`.
`make demo-check` rejoue les étapes du script de démonstration contre la pile en marche.
**Arabe et anglais** : avec un modèle, traduction ; sans, gabarit annoncé comme tel (étape + libellé de cause, détail en français).
**Modèle de langage (facultatif) : Groq.** Copier `.env.example` en `.env`, y mettre `GROQ_API_KEY=...`, puis `make llm-check`
(vérifie la clé et les modèles de *votre* compte). Sans clé, tout fonctionne, sans modèle. Les mesures (`make eval-private`, `make test`)
sont toujours calculées **sans** modèle. Ne jamais committer la clé.
**Sans réseau ni clé d'API** : `make demo-offline` (le moteur bascule en déterministe pur).

## Garde-fous

Chaque interdit du cahier des charges est traduit en mécanisme, pas en consigne :

| Exigence | Mécanisme | Test |
|---|---|---|
| Aucune décision bancaire automatisée | 5 outils déclarés interdits au manifeste, refus tracé avec la règle nommée | `test_outils_interdits` |
| Une session = un dossier | Le courtier lie la session à un `dossier_id` et refuse tout autre | `test_lecture_d_un_autre_dossier_refusee` |
| Aucune activation autonome | Une seule écriture ; l'acquittement vient d'une session agent authentifiée, jamais de la requête | `test_ecriture_sans_acquittement_refusee`, `test_escalade_confirmee…` |
| Un client = un dossier, et il n'apprend rien d'interne | Périmètre fixé au login, vues par rôle, aucune trace de détection côté client | `test_client_limite_a_son_dossier…`, `test_le_client_n_apprend_pas…` |
| Pas d'explication ni d'escalade sur un dossier périmé | Empreinte des deux sources, 409 si elle change | `test_preuve_et_simulation_refusees…` |
| Pas d'invention de règle | Citations issues des ancres du nœud causal, vérifiées contre le corpus | `test_toute_ancre_citee_existe_dans_le_corpus` |
| Résistance aux injections | Contenus tiers encapsulés en blocs inertes + détecteur multilingue + classifieur | `eval/redteam` — 40 cas |
| En cas de doute, s'arrêter | `engine/policy.py` : 5 règles d'abstention ordonnées | `test_repli_sur_sur_donnees_contradictoires` |
| Traçabilité | Journal d'audit chaîné par empreinte, falsification détectable | `test_chaine_d_audit_detecte_la_falsification` |

```bash
make test        # 101 tests, ~3 s
make e2e         # 6 parcours navigateur + accessibilité (pile en marche)
make llm-check   # fournisseur Groq : clé, modèles, un appel par niveau, diagnostic arabe
make probe       # sonde adversariale hors suite (réglage + jeu réservé)
make film        # démonstration filmée -> artifacts/BNA_H24_demo.webm
make livrables   # vérifie les livrables demandés par la proposition
make redteam     # la seule suite d'attaques
```

---

## Structure

```
contracts/     contrats gelés : 37 causes en 11 familles, manifeste d'outils, schémas JSON générés
kit/           corpus (17 documents, 99 règles ancrées) + générateur synthétique
               scenarios/{public,private}/ — la vérité terrain est dans un fichier à part,
               que le moteur ne lit jamais (test dédié)
services/      les deux API simulées (parcours H24, back-office CSA)
engine/        signals · graph · adjudicate · counterfactual · preview · policy · render · verify
               broker (sécurité) · audit (traçabilité) · rag · llm (3 fournisseurs)
api/           plateforme : /v1 (sessions, rôles, preuve, simulation, escalade, audit) — voir docs/api.md
eval/          évaluateur, calibration, suite d'attaques
web/           Next.js — /client /agent /jury
docs/          architecture, sécurité, évaluation, démonstration, vers un pilote
```

---

## Données

**100 % synthétiques.** Noms, identifiants, montants et documents sont tirés au sort à partir
d'une graine. Aucun accès à un système de production BNA, aucune donnée client réelle.
Le corpus documentaire est une réécriture pour les besoins de l'exercice.

`make verify-kit` vérifie que le kit se régénère bit à bit à l'identique — sans quoi aucun
chiffre d'évaluation ne serait vérifiable par un tiers.
