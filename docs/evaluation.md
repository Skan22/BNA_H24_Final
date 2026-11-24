# Rapport d'évaluation

## Protocole

Deux jeux, deux graines, deux tirages distincts. Le **jeu public** (181 dossiers, graine 42) a
servi à régler le moteur et à calibrer la confiance. Le **jeu privé** (133 dossiers, graine
1337) n'a jamais servi à l'ajustement : c'est le seul chiffre que nous mettons en avant.

La vérité terrain vit dans `ground_truth.json`, un fichier **séparé** des dossiers. Un test
(`test_le_moteur_ne_lit_jamais_la_verite_terrain`) vérifie qu'aucun module du moteur ne le
mentionne. Le kit se régénère bit à bit à l'identique (`make verify-kit`).

## Résultats — jeu privé, 133 dossiers (12 familles, dont « choix de l'agence »)

| Mesure | Résultat | Lecture |
|---|---|---|
| Cause exacte, top-1 | **100 %** | la bonne cause arrive en tête |
| Cause exacte, top-3 | **100 %** | — |
| Citations : rappel | **1.00** | aucune règle attendue n'est oubliée |
| Citations : précision | 0.65 | nous citons des règles de contexte en plus |
| Escalade : F1 | **1.00** | on escalade quand il faut, et seulement alors |
| Ancrage structurel | **1.00** | aucune action ni ancre hors référentiel |
| Abstention | 10,5 % | cas de sécurité, de contradiction entre référentiels, d'ambiguïté pure (5) |
| Suite d'attaques | 40/40 tenues, 0 faux positif | **réglée dessus** — voir la sonde ci-dessous |
| Sonde hors suite, jeu réservé | dommage 0/24 · détection **8/24** · faux positifs 0/24 | `make probe`, `docs/cas-d-echec.md` |
| Latence médiane | < 1 ms | chemin déterministe, sans appel modèle |
| Coût | 0 USD | idem |

Détail par famille : `eval/report-private.html`, ou la vue `/jury`.

## Ce que ces chiffres ne disent pas

**Un 100 % sur un kit qu'on a écrit soi-même mesure la couverture du kit, pas la solution.**
Le kit officiel n'existant pas, nous avons produit le nôtre — et nous savons ce que cela vaut.

Trois garde-fous ont été mis en place contre l'auto-complaisance :

1. **Deux tirages réellement distincts.** Graines différentes, répartitions différentes. Le
   privé n'est pas une copie du public.
2. **Des variantes difficiles**, présentes dans les deux jeux :
   - une facture STEG disant « Validez votre facture en ligne » — texte commercial légitime
     que le détecteur d'injection ne doit **pas** attraper ;
   - un dossier à **deux blocages réels** (pièce expirée *et* justificatif manquant) où la
     bonne réponse est le blocage le plus amont du parcours ;
   - un délai d'agence à 47 h, juste **sous** le seuil de 48 h — aucune anomalie à signaler ;
   - un justificatif à 91 jours, juste **au-delà** des trois mois ;
   - un revenu à 799 DT pour un seuil à 800 DT ;
   - un **CSA muet** : le back-office ne répond pas, et le moteur ne doit pas en conclure
     une désynchronisation.
3. **Des contrôles négatifs dans la suite d'attaques**, sans lesquels un assistant qui
   escalade tout obtiendrait un score de sécurité parfait.

## Défauts trouvés par l'évaluation pendant le développement

L'intérêt d'un évaluateur est de trouver ce qu'on n'avait pas vu. Quatre exemples réels :

| Défaut | Découverte | Correction |
|---|---|---|
| `ori.statut_hors_parcours` se déclenchait pour **tout** prospect en profession libérale | 3 dossiers mal classés | exercer en libéral n'interdit pas un compte privé : seule la demande d'une **offre professionnelle** sort du parcours |
| Une souscription déjà active était masquée par un refus d'éligibilité | 1 dossier (C-DUP-003 → C-OFR-002) | inhibiteur : détenir déjà l'offre rend sa condition de revenu sans objet |
| Le cas « manipulation » remontait `C-UNK-000` comme cause | lecture du diagnostic | séparation entre *s'arrêter faute de savoir* et *s'arrêter parce qu'on sait, et que c'est à un humain de trancher* |
| Le texte client annonçait « tentative de manipulation détectée » | lecture du diagnostic | R-SEC-006 : on ne dit pas à un attaquant ce qu'on a vu ; le détail reste côté agent |
| Les motifs « hors périmètre » étaient cherchés dans le texte **brut** alors qu'ils sont écrits sans accent — « numéro » ne matchait jamais | RT-030 est tombée après régénération du kit | recherche sur le texte normalisé ; seuls les identifiants de dossier, en capitales ASCII, restent cherchés dans le brut |
| Le verrou OTP restait une cause active au-delà des trente minutes prévues par R-OTP-003 | apparition d'ambiguïtés inattendues | fait `otp.verrou_expire` + inhibiteur : un verrou levé ne bloque plus rien, et envoyer le client attendre serait faux |
| Une décision de politique nommée « au moins une cause plausible » s'affichait comme *déclenchée* en fonctionnement normal | lecture de la trace | convention inversée : `triggered` signifie désormais toujours « cette règle a provoqué un arrêt » |

Deux défauts étaient dans le kit lui-même, et non dans le moteur :

- un étudiant tiré au sort pouvait dépasser les bornes d'âge du pack Hello Student, ce qui donnait au
  dossier deux causes réelles alors que la vérité terrain n'en déclarait qu'une ;
- deux prospects tirés au hasard pouvaient partager un courriel, créant un **doublon
  involontaire** — donc une seconde cause réelle, absente elle aussi de la vérité terrain.
  Le générateur garantit désormais l'unicité champ par champ ; les doublons **voulus** sont
  posés explicitement par les constructeurs.

Dans les deux cas la vérité terrain avait tort, et l'évaluation l'a montré. C'est précisément
ce qu'on attend d'un évaluateur.

## Ce que le modèle de langage apporte, mesuré

Toutes les mesures ci-dessus sont obtenues **sans aucun appel de modèle**. L'arbitrage ne se
déclenche que sur une ambiguïté pure : plusieurs familles à égalité, et des référentiels
d'accord entre eux.

| Jeu | Dossiers | Ambiguïté pure | Part |
|---|---|---|---|
| public | 181 | 7 | 3,9 % |
| privé | 133 | 5 | 3,8 % |

Sur ces cas, et sur eux seuls, le modèle peut changer la réponse. Partout ailleurs il ne
change rien — et quand il est absent, ces dossiers partent simplement en validation humaine,
ce qui reste une réponse correcte.

Deux garde-fous encadrent cet arbitrage, tous deux testés avec un fournisseur factice
(`tests/test_modele.py`, aucune clé d'API requise) :

1. un identifiant de cause absent de la liste des candidats est traité comme une
   **non-réponse**, jamais comme une cause ;
2. une contradiction entre référentiels **prime sur l'arbitrage** : le modèle n'a pas
   autorité pour décider lequel des deux systèmes a raison (R-SYN-004).

## Calibration de la confiance

Un score de graphe n'est pas une probabilité. `eval/calibrate.py` mesure, **sur le jeu public
uniquement**, la justesse réellement observée par tranche de score, et écrit la table de
correspondance dans `engine/rules/calibration.json`. Une tranche sous 8 observations conserve
le score brut plutôt que d'inventer une calibration.

Constat honnête : sur ce kit, aucune tranche ne descend sous le seuil de repli (0,55). La
règle d'abstention pour confiance insuffisante existe et est testée, mais **elle ne se
déclenche jamais sur nos données** — les abstentions viennent toutes de l'ambiguïté, de la
contradiction entre référentiels ou de la sécurité. Sur un corpus réel, plus bruité, elle
prendrait son sens.

## Reproduire

```bash
make verify-kit     # le kit se régénère à l'identique
make calibrate      # calibration sur le jeu public
make eval           # jeu public, garde-fou de régression
make eval-private   # jeu privé — le chiffre qui compte
make test           # 101 tests, dont les seuils de régression
```


## Propriétés vérifiées en plus de la vérité terrain (`tests/test_invariance.py`)

Sur les 181 dossiers du kit public : le diagnostic est **déterministe** ; il est **invariant à l'ordre** des documents
et des événements ; une **question anodine** ne change ni la cause ni l'abstention ; aucune cause hors du référentiel
ni action hors liste ; hors ligne, le gabarit arabe/anglais nomme la cause et **ne révèle rien** sur une manipulation.
Ces tests visent les défauts qu'un 100 % sur un kit écrit par les auteurs ne montrerait pas.

## Accessibilité et interface (`web/e2e/ui.spec.ts`)

Quatre parcours réels dans Chromium contre la pile en marche, avec axe (WCAG 2.0/2.1 A et AA) sur les écrans de
connexion, client, preuve, simulation et agent. Ils ont trouvé quatre défauts réels, corrigés : listes déroulantes sans
nom accessible, texte gris et ambre trop pâles, lignes de causes atténuées par une opacité qui faisait chuter le contraste.
