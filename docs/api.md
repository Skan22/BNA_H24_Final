# API de la plateforme

Source de vérité : `contracts/openapi.json` (généré : `make contracts`). Documentation interactive : `/docs`.
Les schémas du moteur (`Diagnosis`, `Dossier`) sont dans `contracts/*.schema.json`.

## Authentification

`POST /v1/auth/login` `{username: "agent"|"client", password, dossier_id?}` pose un cookie `boussola_session`
(HttpOnly, SameSite=Strict, `Secure` si `COOKIE_SECURE=true`) et renvoie un jeton `csrf`, à renvoyer en
`X-CSRF-Token` sur toute requête non-GET. Un **client** doit nommer un dossier existant : sa session ne porte que
sur lui. Une erreur de mot de passe ou de dossier renvoie le même 401.
`GET /v1/auth/me` · `POST /v1/auth/logout`.

Un correcteur automatique peut utiliser `Authorization: Bearer <EVALUATOR_TOKEN>` : même vue qu'un agent, sans
droit de préparer ni de confirmer une escalade.

## Diagnostic

| Endpoint | Rôle |
|---|---|
| `POST /v1/diagnoses` `{dossier_id?, question?, locale}` | Diagnostic. Agent/évaluateur : objet `Diagnosis` complet. Client : vue restreinte (`reference`, étape, explication FR/AR/EN, chemin de déblocage, sources visibles). Pour un client `dossier_id` est ignoré. |
| `GET /v1/diagnoses/{id}` | Relecture, même projection. |
| `GET /v1/diagnoses/{id}/trace` | Agent : journal du moteur, chaîné et revérifié. |
| `GET /v1/diagnoses/{id}/explanation` | Chaîne de preuve : faits → règle citée → suite. Agent : faits, poids, sources. Client : langage clair, sans codes. **409** si le dossier a changé. |
| `POST /v1/diagnoses/{id}/preview` `{cause_id}` (agent) ou `{step}` (client) | Simulation « et si ? », lecture seule. Refusée pour manipulation et repli sûr (409). |

`resolved` d'une simulation signifie « plus aucun blocage dans l'hypothèse », jamais « la banque a approuvé ».

## Escalade

`POST /v1/escalations` `{diagnosis_id, note}` — agent seulement, idempotent, uniquement si le diagnostic exige une
validation humaine. `POST /v1/escalations/{id}/confirm` — agent seulement ; relit l'instantané (409 s'il a changé).
Aucune transmission externe : l'escalade est simulée.

## Autres

`GET /v1/dossiers` · `GET /v1/corpus/{anchor}` (le client ne voit pas les procédures internes) ·
`GET /v1/audit?dossier_id=` (agent, avec contrôle d'intégrité de la chaîne) · `GET /v1/eval/summary?split=` ·
`GET /health` · `GET /v1/auth/demo` (seulement si `DEMO_MODE=true`).

## Erreurs

401 identifiants/session · 403 rôle ou CSRF · 404 dossier ou diagnostic inaccessible (jamais 403, pour ne rien
révéler) · 409 état périmé ou action hors diagnostic · 413 corps > 16 Ko · 422 schéma (champs inconnus refusés) ·
429 débit · 503 source indisponible.
