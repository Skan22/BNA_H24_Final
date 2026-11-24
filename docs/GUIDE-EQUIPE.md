# Team guide — presenting BOUSSOLA to BNA, then integrating it

*For the teammate who presents and then integrates. Written in English; the product, the corpus and the BNA-facing
documents are in French. Every command in this guide was run on this project; anything I could not verify is marked
**[unverified]**.*

---

## 0. In one page

**What it is.** An assistant that explains why a customer's "Devenir client" / BNA H24 pack subscription is blocked.
It reads the real state of a dossier through two read-only APIs, picks the cause from a **closed list of 37**, cites
the **rule** that applies, computes the **shortest path to unblock**, and **stops and asks a human** when the facts
don't settle it. It never takes a banking decision.

**The one design idea to remember.** *The diagnosis is deterministic. A language model, when there is one, only
translates and breaks ties.* So the model cannot invent a cause (it can only choose among causes whose prerequisites
are already verified), cannot invent a rule (citations come from the chosen cause's declared anchors), and the whole
system keeps working with the model switched off.

**Where it stands.** A working proof of concept on **100 % synthetic data**: engine, secure web platform (login,
roles, audit), client and agent screens, 6 deliverable documents, a demo film. **It has never touched a real BNA
system, real data, or a live language model** (see §4).

**Three things to say honestly** (they make the pitch stronger, not weaker):
1. "The 100 % accuracy is on a kit we wrote ourselves — it measures coverage of the cases we imagined, not accuracy on
   your dossiers. The pilot's first job is to measure that."
2. "Our attack **detector** only catches about a third of phrasings it was never tuned on. But detection is only
   triage: in 50 unseen attacks, nothing ever got through, because free text cannot reach the decision path."
3. "Packs, thresholds, fees, delays and the branch list are **fictional** except where we say otherwise."

**Three things never to say:** that it is "validated by BNA", that the accuracy is "100 %" without the qualifier, that
it "uses AI to decide".

---

## 1. Before the meeting (30 minutes, once)

### 1.1 Requirements
Python ≥ 3.12 and [`uv`](https://docs.astral.sh/uv/), Node 22 + npm, Docker (optional but recommended), and Chromium
only if you want to run the browser tests or re-record the film.

### 1.2 Get it running
```bash
cd BNA_H24_Final
make install          # uv sync + npm install (the only step that needs internet)
make all              # regenerates the kit, calibrates, runs tests, evaluates public + private sets
make docker-up        # PostgreSQL + mocks + API + web  ->  http://localhost:3000/login
#   or without Docker:
make demo             # mocks :8001 :8002, API :8000, web :3000
```
Then, with the stack running, in another terminal:
```bash
make demo-check       # replays the 7 demo steps against the live stack; must say "Les 7 étapes ... fonctionnent"
make livrables        # checks every deliverable file exists and the README numbers match the code
```

### 1.3 Demo accounts (local only — change before sharing anything)
| Space | Login |
|---|---|
| Agent | password `agent-demo-change-me` |
| Client | a dossier number + password `client-demo-change-me` |

In demo mode (`make demo`, `make docker-up`) both the login page and the agent screen have a **"scénario de
démonstration"** menu with one dossier per cause. **Use the menu, not hard-coded dossier numbers** — numbers change if
the kit is regenerated with different code.

### 1.4 Pre-flight checklist (10 minutes before)
- [ ] `make demo-check` is green.
- [ ] The film plays: `artifacts/BNA_H24_demo.webm` (58 s, captioned). **Your fallback if the network, Docker or the
      room's screen sharing fails.**
- [ ] Two browser windows, both **logged out**: one for the client, one for the agent (use a private window for one of
      them — the session cookie is per browser).
- [ ] You know the demo scenarios you will click (§2).
- [ ] **Do not log in more than 10 times a minute as the same user** — the login limiter will answer 429 for a minute.
      (It happened to us while repeating tests; it is correct behaviour.)
- [ ] No internet in the room? Nothing in the demo needs it. `BOUSSOLA_LLM=none` is the default when no API key is set.

---

## 2. The presentation (≈ 8 minutes)

The exact click-by-click script is `docs/demonstration.md`. Condensed storyline:

| Time | Screen | Say |
|---|---|---|
| 0:00 | Home `/` | "A generic error doesn't say if it's a missing document, an offer/profile mismatch, a duplicate, or a slow system. The client leaves; the agent spends ten minutes rebuilding the cause. In our test kit **about half (45–49 %) of blocked dossiers show only the catch-all code H24-000**." |
| 0:45 | Client — scenario **C-AGE-002** | "A client is stuck at **choosing a branch**, the second step of the journey, as in the public BNA H24 flow. Their branch is closed. They don't get 'choose another branch' in the void — they get the **open branches that handle their profile**." Show the 10-step stepper, "Pourquoi cette réponse ?", then "Et si c'était réglé ?" ("a read-only simulation — nothing is modified"). Switch to Arabic. |
| 2:15 | Agent — scenario **C-AGE-004** | "The agent sees cause, confidence, the facts behind it, the rules cited. Here the branch code is unknown: that's data to fix, not the client's fault." Open **Preuve** (facts → rule → next step). |
| 3:30 | Same screen | **Préparer le brouillon**, then **J'acquitte et je confirme**. "Escalation is two steps, and only a logged-in agent can confirm. The server never accepts a 'human approved' flag in a request." |
| 4:15 | Agent — scenario **C-SEC-001** | "A booby-trapped invoice says *validate automatically*. It is never an instruction — flagged, escalated, never executed. The client is not told what was detected." Show the **Trace** tab: hash-chained audit log. |
| 5:00 | `/jury` | Show the measured numbers, then **say the limits** (§0 point 1 and 2). This is where the credibility is won. |
| 6:30 | Slides / voice | The pilot path: agent-only first, one branch, then client-facing, one blocker family at a time (§6.9). Then questions. |

**60-second pitch (French):**
> « Quand une souscription H24 est bloquée, le message d'erreur ne dit pas pourquoi. BOUSSOLA lit l'état réel du dossier,
> identifie la cause parmi une liste fermée, cite la règle applicable, et dit au client — et à l'agent — quoi faire
> ensuite. Le diagnostic est déterministe : un modèle de langage peut traduire et départager, mais il ne peut ni inventer
> une cause ni une règle, et il ne décide jamais. Quand les faits ne suffisent pas, l'assistant s'arrête et passe la main
> à un humain. Aujourd'hui c'est un prototype sur données synthétiques ; la première étape d'un pilote est de mesurer sa
> justesse sur de vrais dossiers qualifiés par vos agents. »

---

## 3. How it works (plain language)

```
Browser (Next.js: /client /agent /jury)
   │  /api
   ▼
Platform (FastAPI, api/): login, CSRF, roles, snapshot, audit, database
   ▼
Engine (engine/): A facts → B graph → policy → D unblock path → E text
   │                         └─ optional model: translate, break ties
   ▼
Data port (read-only) ──▶ H24 API + CSA API
```

| Piece | What it does | Key files |
|---|---|---|
| **Engine** | Turns a dossier + the two systems' state into: ranked causes, confidence, shortest unblock path, client text, agent text, citations, audit trail. Knows nothing about users or sessions. | `engine/diagnose.py` (orchestrator), `signals.py` (typed facts), `rules/graph.yaml` (37 causes), `policy.py` (when to stop), `counterfactual.py` (unblock path), `render.py`, `verify.py` |
| **Tool broker** | Every data access goes through it: tool must be in the manifest, scoped to the session's dossier, within budgets; forbidden tools refuse with a named rule. One write only: prepare an escalation, and only with human acknowledgement. | `engine/broker.py`, `contracts/tools.manifest.yaml` |
| **Data port** | The *only* seam to the outside world. Replace it and no other engine file changes. | `engine/ports.py`, `engine/port_contract.py` |
| **Corpus** | 17 French documents, 99 rules, each with a stable anchor like `R-AGE-002`. Citations resolve anchors; they are never found by similarity search. | `kit/corpus/*.md` |
| **Platform** | Sessions (HttpOnly cookie + CSRF), roles (agent / client / evaluator), *a client session = one dossier*, role-specific views, persistence, hash-chained audit, snapshot check, simulation, two-step escalation. | `api/main.py`, `api/projection.py`, `api/db.py`, `engine/preview.py` |
| **Web** | Login, client screen, agent screen (diagnosis / proof / message / trace), evaluation page. | `web/app/` |
| **Kit & evaluator** | Synthetic dossiers (two seeds: public for tuning, private for measuring), ground truth in a *separate* file the engine never reads, evaluator, attack suite, adversarial probe. | `kit/`, `eval/` |

**Glossary.** *Cause*: one of 37 entries in `contracts/causes.yaml`, in 11 families (F01 orientation … F10
manipulation, F11 branch choice). *Anchor*: stable id of a corpus rule. *Abstention / repli sûr*: the assistant stops
and escalates instead of guessing (5 ordered rules in `policy.py`). *Snapshot*: a hash of the dossier's state in both
systems at diagnosis time — proof, simulation and escalation are refused if it has changed. *Port*: the data adapter.

**Key design decisions and why** (in case BNA asks):
- **Deterministic first, model second** → verifiable citations, defensible refusals, works offline, near-zero cost.
- **Closed cause list + hard prerequisites per cause** → the structural anti-hallucination guarantee.
- **Safety by capability, not by instruction** → the model has no tools; forbidden actions don't exist as code paths.
- **Ground truth in a separate file** → a test fails if any engine module mentions it.
- **Abstain rather than guess** → a useless escalation costs minutes; a wrong answer costs customer trust.

---

## 4. What is real and what is not

### Numbers you can quote (with their qualifier)
| Claim | Value | Qualifier — say it |
|---|---|---|
| Correct top cause | 100 % on 133 private dossiers, 12 families | Kit written by us. Measures coverage, not accuracy on real dossiers. |
| Citation recall / precision | 1.00 / 0.65 | We cite some context rules beyond the expected ones. |
| Escalation F1 | 1.00 | Same kit. |
| Latency | < 1 ms deterministic | Local, no network, no model. |
| **Harm** from 50 unseen attacks | 0 / 50 | By construction: free text cannot reach the decision path. |
| **Detection** of unseen attacks | **8 / 24 = 33 %** on the reserved set | Weak. Triage only. 25/26 on the tuning set is meaningless. |
| False alarms on normal questions | 0 / 52 | Includes "Pouvez-vous débloquer mon dossier ?" (fixed in this pass). |
| Accessibility | no axe WCAG 2.1 AA violations on tested screens | Not a full audit; no screen-reader or user testing. |

### What is fictional
Everything about BNA's offer except the **public pack names** (Prime, Prime Plus, Premium, Hello Student, TWENSA, and
that Hello Student and TWENSA are free). **Thresholds, fees of other packs, delays, document lists, age limits, the
branch list (8 branches, 3 "special"), the "branch without e-signature" attribute and every rule text are invented.**
The official BNA site was unreachable from our machine; what we know of the public journey comes from a 2022 press
article and search snippets. The **second-step position of "choose a branch"** comes from that article — confirm it.

### What has never been run **[unverified]**
- **A live language model.** The provider is now **Groq** (`engine/llm/provider.py`). It is unit-tested against a fake
  HTTP server, but until someone runs **`make llm-check`** with a real key it has never been executed against Groq. The
  default model ids (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`) are not guaranteed for your account: `llm-check`
  lists what your key can use and tells you what to set in `GROQ_MODEL_STRONG` / `GROQ_MODEL_FAST`. Arabic quality of
  these models is also unmeasured.
- Any real BNA API, data or terminology.
- Load or concurrency beyond a small test (8 threads). The rate limiter is per process.
- Browsers other than Chromium; Windows; Docker on a machine other than ours.
- Screen readers, real users, human review of explanation quality.

---

## 5. Likely BNA questions — honest answers

| Question | Answer |
|---|---|
| **Does AI make the decisions?** | No. The cause is computed by rules. A model may translate and break ties between equally plausible families (4 % of our dossiers). It has no tools. |
| **How accurate is it?** | 100 % on our own synthetic kit — which only shows it covers what we imagined. The honest answer is "unknown on your data"; the pilot measures it (target in our plan: ≥ 85 % top-1 on a held-out set of real qualified cases). |
| **What if the model hallucinates?** | It can only pick among pre-verified causes or translate an already-written French text. But note: the live-model path has not been run yet. |
| **Can it be manipulated by a customer's message or a document?** | Free text never reaches the decision path, so nothing got through in 50 unseen attempts. We *detect* only about a third of new phrasings — so the security team shouldn't rely on its alerts yet. |
| **What data does it need from us?** | Read-only: the dossier, its documents' metadata and OCR text, OTP state, signature state, branch state, events; from the back-office: existing relations, subscriptions, duplicates, status, branch queue. §6.2 has the exact list. One write: "prepare an escalation". |
| **Personal data?** | Demo is synthetic. With real data: see §6.7 — **by default, when a model is configured, OCR text and customer messages are sent to it for injection classification.** Run with `BOUSSOLA_LLM=none` or an in-bank model until data-protection review is done. The audit log keeps evidence such as name mismatches read from documents, with no retention policy yet. |
| **Languages?** | French complete. Arabic and English: model translation if available; otherwise a short pre-written text (step + cause), details in French. Tunisian dialect input is only partly detected. |
| **Why not just give the dossier to an LLM?** | It produces plausible but unverifiable causes. Here every statement traces to a fact, a rule and a version. |
| **Cost?** | 0 without a model. With one: only for translation/tie-breaks; cost tracking exists but has **never been measured with a live provider**. |
| **Does it scale?** | The engine is stateless and fast; the platform uses PostgreSQL. **Never load-tested.** |
| **Who owns the rules?** | A BNA business owner per domain. Rules need stable anchors and versioning (§6.4); a rule that changes without its anchor changing makes past citations lie. |
| **Why a "choose a branch" step?** | It is the first step of the public BNA H24 journey. We added 5 causes (none chosen, closed, doesn't handle the profile, unknown code, e-signature to finish at the branch). The branch data is fictional. |
| **How long to a pilot?** | Our own estimate in `docs/vers-un-pilote.md`: 2 weeks scoping, 4 corpus, 4 calibration, 6 agent-only pilot, 6 client pilot — mostly business work, not engineering. Treat as an estimate. |
| **Can agents correct it?** | Not yet: there is no feedback loop. It is on the pilot list because it is what feeds calibration. |

---

## 6. Integration guide

### 6.1 The map — what to replace, in order
| # | Replace | Why | Effort driver |
|---|---|---|---|
| 1 | **Data port** (`engine/ports.py`) | Connect H24 + CSA read APIs | API access, field mapping |
| 2 | **Catalog** (`kit/catalog.json`): packs, conditions, branches | Our values are invented | BNA business input |
| 3 | **Corpus** (`kit/corpus/`) | Our rules are rewritten, not BNA's | Business ownership, anchors |
| 4 | **Thresholds** (top of `engine/signals.py`) and **graph weights** (`engine/rules/graph.yaml`) | Hand-set on synthetic data | Real qualified cases |
| 5 | **Authentication** (`api/main.py` login) | Demo password + dossier number | BNA identity, SSO |
| 6 | **Language model decision** | Privacy + model approval | Legal/security review |
| 7 | **Deployment hardening** | TLS, secrets, retention, monitoring | Infra |

Do them roughly in that order; **1 → 4 are what makes the diagnosis real**, 5 → 7 make it deployable.

### 6.2 What the engine reads (the data contract)
The model is `contracts/models.py::Dossier` (JSON schema: `contracts/dossier.schema.json`). Fields that drive causes:

| Field(s) | Used for |
|---|---|
| `step`, `status`, `error_code`, `updated_at` | Everything: step-specific causes, generic-code handling (`H24-000`), expiry |
| `prospect`: `nom`, `prenom`, `date_naissance`, `residence`, `statut_pro`, `revenu_mensuel_declare`, `telephone`, `email`, `cin`/`passeport` | Age, eligibility, identity consistency, OTP-phone format (`+216[2459]xxxxxxx`), duplicates |
| `documents[]`: `type`, `statut`, `emis_le`, `expire_le`, `ocr_confidence`, `ocr_text` | Missing / unreadable / expired / old proof of address, identity mismatch. **`ocr_text` is treated as untrusted** |
| `otp`: `tentatives`, `max_tentatives`, `dernier_envoi_at`, `canal` | OTP lock, expired lock (30 min), unreachable phone |
| `signature.statut`, `agence`: `code_agence`, `en_file_depuis`, `sla_heures`, `rdv_honore` | Branch choice, e-signature fallback, SLA, missed appointment |
| `offre.pack_code`, `events[]` (types `REFUS_CONDITION`, `INCIDENT_AMONT`) | Offer/profile mismatch, upstream incident |
| `message_client` | Treated as untrusted free text |
| **CSA**: relations, subscriptions, duplicates (`dossier_id`, `cin`, `email`, `telephone`, `statut`), status (`step`, `status`, `updated_at`, `signature_recue`), branch queue | Existing customer, duplicates, H24/CSA desync |

Behaviours that matter for a real source: **a mute CSA (`None`) must not be read as "desync"** — return `None`, the
engine copes. `search_duplicates` must return only dossiers *linked to this one*, never the full index.

### 6.3 Write your port (the core integration step)
`DataPort` has 9 methods (see `engine/ports.py`). `LocalKitPort` (files) and `HttpPort` (the two mock APIs) are the two
existing examples. Skeleton:

```python
# engine/bna_port.py
class BnaPort:
    def get_dossier(self, dossier_id):            # -> dict shaped like contracts.models.Dossier, or None if unknown
        raw = self._h24.get(f"/…/{dossier_id}")   # BNA's real call
        return None if raw is None else self._to_dossier(raw)      # <- the mapping lives here, in ONE place
    def list_dossiers(self, limit): ...           # [{"dossier_id","step","status","error_code","prospect","pack"}]
    def get_events(self, dossier_id): ...
    def get_document_ocr(self, dossier_id, doc_id): ...
    def get_subscriptions(self, identite): ...
    def get_relations(self, identite): ...
    def search_duplicates(self, dossier_id): ...  # only dossiers linked to this one
    def get_etat_csa(self, dossier_id): ...       # dict or None (mute source)
    def get_agency_queue(self, code_agence): ...  # aggregates only, no names
```
1. Implement it. Keep every mapping from BNA's field names to ours inside `_to_dossier`.
2. **Run the contract check on it before anything else:**
   ```python
   from engine.port_contract import verifier_port
   verifier_port(BnaPort(...), dossier_id="a-real-test-dossier")     # raises with the exact defect
   ```
   (`tests/test_port.py` is the model to copy.)
3. Wire it in without touching the engine. Create `api/bna_app.py`:
   ```python
   from api.main import create_app
   from engine.bna_port import BnaPort
   app = create_app(port=BnaPort())      # run: uvicorn api.bna_app:app
   ```
   (`BOUSSOLA_PORT=http` only selects the two *mock* services; it is not for BNA's real APIs.)
4. If BNA's APIs return a differently-shaped dossier, **adapt in `_to_dossier`, not in the engine.** If a field BNA
   doesn't have is needed by a cause, that cause will simply never fire — list those for the business team.

### 6.4 Corpus (the rules and their citations)
Format: Markdown with YAML front matter (`doc_id`, `titre`, `version`, `effective_date`, `domaine`, `source`), then one
`## R-XXX-NNN — Title` heading per rule. The loader **rejects duplicate anchors**. The test suite fails if the graph
cites an anchor that doesn't exist. **Anchors must be stable**: BNA should own the numbering, and a rule whose meaning
changes without a new anchor/version makes every past citation false.

Client-visible vs internal: documents listed in `api/projection.py::DOCS_INTERNES` are hidden from clients — update it
when you add internal procedures.

### 6.5 Causes, thresholds, calibration
**Thresholds** (all synthetic — replace with BNA's): top of `engine/signals.py` — proof of address 90 days, OCR
legibility 0.70, income-proof threshold 500, inactivity expiry 30 days, OTP lock 30 min, H24/CSA tolerated gap 15 min,
minimum age 18. **Graph weights and policy thresholds** (`min_confidence` 0.55, `ambiguity_margin` 0.12): `graph.yaml`.

**Add a cause — checklist** (the contract tests fail if you forget a link):
1. `contracts/causes.yaml` — id, family, owner, severity, labels in fr/ar/en.
2. `engine/signals.py` — `put("domain.fact", …)` for any new fact (tests check every fact the graph references is produced).
3. `engine/rules/graph.yaml` — node: `requires` (hard prerequisites), `evidence` (weights sum ≤ 1), `inhibits`, `anchors`,
   `remediation` (ordered, with owner and ETA), `allowed_actions`, `requires_human_validation`.
4. `kit/corpus/` — the rule text with its anchor.
5. `kit/generate.py` — a builder **and** a hard variant (a near-miss that must *not* trigger it).
6. `make kit calibrate test eval-private`. New *family* or *step*: also `contracts/models.py::Step`, `web/lib/api.js`
   (`ETAPES`), `engine/render.py` step labels, `engine/counterfactual.py::ORDRE_FAMILLE`, `eval/run.py` and
   `web/app/jury/page.jsx` family labels. (`tests/test_agence.py` shows how the branch step is checked end to end.)

**Calibration.** `make calibrate` fits "raw score → observed accuracy" on the *public* set and writes
`engine/rules/calibration.json`. With real data: replace the kit with real qualified cases (agents label the true
cause), recalibrate on one part, **measure on a held-out part you never tune on.**

### 6.6 Authentication and identity
Today: `POST /v1/auth/login` with a shared password per role; a client names a dossier number; the session is bound to
it server-side. **This is demo-grade.** For a pilot: SSO + MFA for agents; for clients, derive the dossier from the
authenticated banking session (the client must never *type* which dossier they are). The binding already exists
(`SessionRow.dossier_id`, `Principal.permit`), so the change is in `login()` and who fills `dossier_id`. Also add
per-branch authorisation for agents. The server also refuses to start with the demo secrets unless `DEMO_MODE=true`.

### 6.7 The language model — decide this *before* real data
Provider: **Groq** (OpenAI-compatible API). Put `GROQ_API_KEY` in `.env` (copy `.env.example`; git-ignored) — never in code,
chat or tickets — then run `make llm-check`. Modes (env `BOUSSOLA_LLM`): `groq`, `none` (no model; the default in Docker),
`cassette` (replay), `anthropic` and `ollama` (kept as alternatives), `auto` (cassette → Groq if key present → Anthropic).
`make test` and every evaluation run **without** a model, so the measured numbers never depend on it. The model is used for: translation to Arabic/English, tie-breaking between plausible families, an
injection second opinion, and a grounding check. **Important privacy fact:** when a provider is configured, the
injection classifier and the other calls send **OCR text, the customer's message/question, and the facts** to it. With
real dossiers, either keep `BOUSSOLA_LLM=none`, or use an in-bank/approved endpoint after data-protection review.
Test the live path on synthetic data first (`make llm-check`, §4). Groq is an external service: it has not been through any BNA data-protection review.
Everything degrades safely: no model → deterministic answers, ties go to a human.

### 6.8 Deployment hardening checklist
- [ ] Real secrets: `AGENT_PASSWORD`, `CLIENT_PASSWORD`, `EVALUATOR_TOKEN`, `BOUSSOLA_MOCK_KEY` (or whatever replaces it); `DEMO_MODE` unset.
- [ ] TLS in front; `COOKIE_SECURE=true` (cookie becomes `__Host-…`).
- [ ] PostgreSQL (`DATABASE_URL=postgresql+psycopg://…`; install extra `postgres`); backups; **replace `create_all` with migrations (Alembic)**.
- [ ] Shared rate limiter (today per process — several workers each count separately).
- [ ] Data retention + pseudonymisation for diagnoses and audit rows; decide what the audit may keep.
- [ ] `BOUSSOLA_AS_OF=now` so dates (age, expiry, delays) use the real clock; the default is a fixed 2026-09-26 for reproducible tests.
- [ ] Remove the demo endpoints' exposure (`/v1/auth/demo` is 404 unless `DEMO_MODE=true`).
- [ ] Monitoring: abstention rate (rising = corpus has aged), cause distribution drift, escalations agents overturn, security flags.
- [ ] A human-in-the-loop commitment: someone must be accountable for answering escalations, with a delay.

### 6.9 Suggested path (from `docs/vers-un-pilote.md`, our estimates)
0. Scoping (≈2 wks): validate the cause list with the business; freeze the anchor format.
1. Corpus (≈4 wks): anchor the real corpus; plug in the port; citations exact on ~100 real dossiers.
2. Calibration (≈4 wks): tune graph on real qualified cases; target ≥ 85 % top-1 on a held-out set.
3. Agent-only pilot (≈6 wks): one branch, **no client view** — an agent spots errors a customer would believe.
4. Client pilot (≈6 wks): one blocker family at a time; measure abandonment.
What we advise against: widening the cause list before calibrating; replacing the graph with a model alone; lowering the abstention threshold to look more "useful".

---

## 7. Operating reference

### Environment variables
| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./boussola.db` | Platform database |
| `BOUSSOLA_SPLIT` | `public` | Which kit the local port reads |
| `BOUSSOLA_PORT` | `local` | `local` (kit files) or `http` (the two mock APIs) |
| `BOUSSOLA_H24`, `BOUSSOLA_CSA` | `http://127.0.0.1:8001`, `:8002` | Mock API URLs |
| `BOUSSOLA_MOCK_KEY` | `local-mock-change-me` | Shared key between engine and mocks |
| `AGENT_PASSWORD`, `CLIENT_PASSWORD`, `EVALUATOR_TOKEN` | demo values | Secrets; demo values refused unless `DEMO_MODE=true` |
| `DEMO_MODE` | `false` | Enables scenario menu and accepts demo secrets |
| `COOKIE_SECURE` | `false` | `true` behind HTTPS |
| `SESSION_SECONDS`, `REQUESTS_PER_MINUTE` | `3600`, `30` | Session lifetime, per-user rate |
| `BOUSSOLA_LLM` | `auto` | `groq` / `none` / `cassette` / `anthropic` / `ollama` (Docker image default: `none`) |
| `GROQ_API_KEY` | — | Groq key; read only from the environment / `.env`, never logged |
| `GROQ_MODEL_STRONG`, `GROQ_MODEL_FAST` | `openai/gpt-oss-120b`, `openai/gpt-oss-20b` | Arbitrage + translation / injection check + grounding check. Not guaranteed — check with `make llm-check` |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Override for a proxy or in-bank gateway |
| `ANTHROPIC_API_KEY` | — | Only for the Anthropic alternative |
| `BOUSSOLA_AS_OF` | `2026-09-26T10:30:00` | Reference "now"; `now` for live |
| `BOUSSOLA_API` (web, build time) | `http://127.0.0.1:8000` | Where the web proxy sends `/api` |

### `make` targets
`install` · `llm-check` (Groq key, models, one call per tier, Arabic diagnosis — needs internet) · `all` (kit → calibrate → test → eval) · `test` · `eval` / `eval-private` · `redteam` · `probe`
(adversarial probe: tuning set, then reserved set) · `verify-kit` (kit regenerates bit-for-bit) · `contracts` ·
`demo` · `docker-up` · `demo-check` · `e2e` (6 browser journeys + accessibility; needs the stack up;
`CHROMIUM_PATH=/usr/bin/chromium`) · `film` (re-record the demo; first time run `npx playwright install ffmpeg`) ·
`livrables` (deliverables + README-number consistency).

### Repository map
```
contracts/  frozen contracts: causes.yaml, tools.manifest.yaml, models.py -> *.schema.json, openapi.json (generated)
engine/     the diagnosis engine (+ llm/, rag/, rules/graph.yaml, ports.py, port_contract.py, preview.py)
api/        the platform (main.py, projection.py, db.py, config.py)
services/   the two mock APIs (H24, CSA)
kit/        catalog.json, corpus/ (17 docs), generate.py, scenarios/{public,private}/
eval/       run.py, redteam.py + attacks.yaml, probe.py, calibrate.py, reports (generated)
web/        Next.js app + e2e/ (Playwright + axe) + film
tests/      101 tests     tools/  demo_check, check_livrables, verify_kit, collect_film
docs/       README for each topic (see §8)     artifacts/  BNA_H24_demo.webm (generated)
```

### Troubleshooting (every item below happened to us)
| Symptom | Cause / fix |
|---|---|
| `429 Trop de demandes` at login | More than 10 logins/min for one user+dossier. Wait 60 s. |
| `api` container exits at first `docker compose up` | Started before Postgres/mocks were ready or a port clash; `docker compose up -d` again (health checks now order startup). |
| `address already in use` on 8000/3000 | A previous `make demo` still running: find with `ss -ltnp`, stop that PID. Or use `PORT_API=8010 PORT_WEB=3010 make demo`. |
| Browser tests fail with "strict mode violation" | A text appears in two places; make the selector more specific (roles, `.card`, `b`). |
| `make film` fails: executable doesn't exist (ffmpeg) | `cd web && npx playwright install ffmpeg`. |
| Dossier numbers in a script stopped working | The kit was regenerated; resolve dossiers by cause through `/api/v1/auth/demo` instead. |
| `Secrets par défaut refusés` at startup | Set real secrets, or `DEMO_MODE=true` for a demo. |
| The `/jury` page is empty | Reports are generated files: `make eval eval-private` (the Docker image generates them at build). |
| `make` target lists in the README disagree with the Makefile | `make livrables` catches README/code drift; this happened once. |

---

## 8. Which document to read for what
| Need | Document |
|---|---|
| Exact demo click-path | `docs/demonstration.md` |
| Score the project against BNA's grid, with evidence and gaps | `docs/grille-bna.md` |
| Failure cases and honest limits | `docs/cas-d-echec.md` |
| Threat model and tested controls | `docs/securite.md` |
| Metrics, methodology, defects found by evaluation | `docs/evaluation.md` |
| API reference | `docs/api.md`, `contracts/openapi.json`, `/docs` on the running API |
| Architecture | `docs/architecture.md` |
| Pilot plan | `docs/vers-un-pilote.md` |
| Where each part came from (two prototypes were merged) | `docs/fusion.md` |
| What the public BNA site told us, and what we changed | `docs/ameliorations.md` |

---

## 9. Open items to settle with BNA (do not guess these)
1. The real offer: packs (Premium Plus? the three TWENSA variants?), eligibility, thresholds, fees.
2. The real journey order, including **where "choose a branch" sits** and the e-signature/branch fork.
3. The real branch referential: hours, capacity, which branches serve non-residents, which offer e-signature.
4. Document lists per profile and their validity rules.
5. Whether a language model may be used at all, where it may run, and what may be sent to it.
6. Who is accountable for escalations, with what delay; whether separation of duties is required.
7. Retention and pseudonymisation rules for diagnoses and the audit log.
8. Client authentication: which BNA session proves who the client is.

## 10. Quick commands to verify the project is healthy (expected results)
```bash
make test            # 101 passed
make eval-private    # top-1 100 %, citations recall 1.00, 133 dossiers
make redteam         # 40/40 attacks held, 0 false positives
make probe           # tuning set 25/26 detected; reserved set 8/24 detected; harm 0; false positives 0
make verify-kit      # both splits "identique"
make demo-check      # 7 steps pass (stack running)
make e2e             # 6 passed (stack running; wait a minute between repeated runs)
make livrables       # all deliverables present, README consistent
```
If one of these disagrees with this guide, **trust the command, not the guide**, and fix the guide.
