# ARCHITECTURE.md — BidReady

Single-workspace web app: a **FastAPI** backend runs a document/AI pipeline as background jobs and serves
a JSON API; a **React + Vite** SPA consumes it. All storage is local (SQLite + files). The only optional
external call is the Claude API; an offline rule-based provider covers the same prompts without network.

```
Browser (React SPA) ──JSON──▶ FastAPI routers ──▶ services / pipeline stages ──▶ get_llm(): Claude | offline
                                   │                         │
                                   ├── SQLite (SQLModel): rows, page texts, embeddings (float32 blobs)
                                   └── backend/data/files: uploads, generated packages (DOCX/PDF/XLSX/ZIP)
```

## 1. Folder structure

```
ise/
├── README.md  DEMO.md  CLAUDE.md  PRODUCT_SPEC.md  ARCHITECTURE.md  TASKS.md  DEV_SETUP.md
├── .env.example  Makefile  .claude/launch.json
├── samples/                               # generated demo data (scripts/make_samples.py), all fictional
│   ├── hmis-tender/{rfp.pdf, corrigendum-1.pdf, gold_requirements.json}
│   └── company/{Nimbus_*.pdf, Nimbus_Past_Proposal_Mysuru.docx, company_profile.json}
├── backend/
│   ├── pyproject.toml  uv.lock  alembic.ini  alembic/versions/{0001_initial_schema, 0002_knowledge_outcome}.py
│   ├── app/
│   │   ├── main.py                        # app factory, lifespan (migrate, seed admin, job runner), SPA serving
│   │   ├── core/   config.py db.py security.py deps.py errors.py logging.py
│   │   ├── models/tables.py               # every SQLModel table
│   │   ├── schemas/api.py                 # request/response models
│   │   ├── schemas/llm.py                 # structured outputs for each prompt
│   │   ├── api/    health auth company jobs projects requirements
│   │   ├── services/
│   │   │   ├── files.py                   # upload streaming, PDF/DOCX sniffing, size limit
│   │   │   ├── company.py                 # single company row + index_knowledge job
│   │   │   ├── profile.py                 # form-field filling, eligibility checks
│   │   │   ├── scoring.py                 # pure formulas: review, readiness, go/no-go, page budgets
│   │   │   └── audit.py                   # audit trail writes
│   │   ├── jobs/runner.py                 # job table + thread pool + retry; @register("kind")
│   │   ├── llm/
│   │   │   ├── client.py                  # get_llm(), AnthropicLLM, Prompt loader, UsageMeter
│   │   │   ├── offline.py                 # OfflineLLM: rule-based handler per prompt
│   │   │   └── prompts/*.md               # versioned prompts (version:, ---system---, ---user---)
│   │   ├── pipeline/
│   │   │   ├── textutil.py                # normalise, sentences, key terms, quote verification
│   │   │   ├── parse.py                   # PyMuPDF text+tables / python-docx / OCR fallback
│   │   │   ├── chunk.py                   # top-level sections with [[page N]] markers
│   │   │   ├── analyse.py                 # job "analyse": classify, requirements, rules, criteria, linking
│   │   │   ├── embed.py  index.py  retrieve.py   # embeddings, knowledge chunks, hybrid search
│   │   │   ├── draft.py  review.py        # job "draft": cited answers + live compliance review
│   │   │   ├── validate.py                # readiness blockers, go/no-go
│   │   │   ├── extras.py                  # outline, consistency checker, job "addendum"
│   │   │   └── package.py                 # job "package": DOCX/PDF/XLSX + ZIP
│   │   └── scripts/  seed_demo.py  dump_openapi.py
│   ├── scripts/  make_samples.py  eval_extraction.py
│   ├── tests/   unit/ pipeline/ api/  conftest.py
│   └── data/                              # gitignored: app.db, files/
└── frontend/
    ├── package.json  vite.config.ts  eslint.config.js  components.json  openapi.json
    └── src/
        ├── main.tsx  App.tsx  router.tsx  index.css
        ├── lib/   api.ts queryClient.ts queryKeys.ts keyboard.ts format.ts utils.ts
        ├── types/api.ts                   # generated (pnpm gen:api) — do not edit
        ├── test/  setup.ts mockApi.ts
        ├── components/ui/                 # shadcn generated
        ├── components/common/             # AppShell Sidebar PageHeader StatusChip ScoreRing Dropzone
        │                                  # EmptyState ErrorState LoadingRows
        └── features/
            ├── landing/    LandingPage Hero HeroScene (three.js, lazy) BeforeAfter HowItWorks
            │               MatrixPreview Features Closing Reveal SceneBoundary useReducedMotion
            ├── auth/       LoginPage RequireAuth api
            ├── dashboard/  DashboardPage
            ├── company/    CompanyPage api
            ├── knowledge/  KnowledgePage
            ├── jobs/       JobProgress api
            ├── projects/   NewProjectPage ProjectPage api types tabs steps
            ├── overview/   OverviewTab DraftCard
            ├── matrix/     MatrixTab RowPanel DiffView
            ├── rules/      RulesTab
            ├── addenda/    AddendaTab
            └── package/    PackageTab
```

## 2. Data model (SQLModel; Alembic revisions `0001`, `0002`)

| Table | Key fields |
| --- | --- |
| `user` | email (unique), password_hash (argon2), name, is_active |
| `company` | legal_name, short_name, address, gstin, pan, udyam_no, signatory_name, signatory_designation, email, phone, website, year_established, turnover JSON `[{fy, amount_inr}]`, certifications JSON `[{name, number, valid_until}]`, style_sample |
| `knowledgedoc` | company_id, filename, stored_path, doc_type (past_proposal, case_study, profile, product, certificate, other), pages, status (pending, indexing, ready, failed), error, outcome (won, lost, unknown) |
| `knowledgechunk` | doc_id, company_id, page, chunk_index, text, embedding (float32 bytes) |
| `project` | company_id, title, tender_no, buyer, deadline, status (analysing, ready, failed, packaged), readiness_score, outcome (unknown, won, lost), competition_rating, go_no_go JSON, tokens_used, package_path, package_files JSON |
| `rfpfile` | project_id, version (0 original, 1+ addenda), role (main, attachment, addendum), filename, stored_path, pages, parsed_at |
| `rfppage` | rfp_file_id, page, text (used for quote verification and addendum parsing) |
| `requirement` | project_id, rfp_file_id, req_code (`R-4.2-03`), text, section_path, page, type (mandatory, optional), keyword, category, source_quote, criterion_id, outline_section_id, version_status (unchanged, modified, added, removed), previous_text, order |
| `response` | requirement_id (unique), answer, status (pending, fully_compliant, partially_compliant, compliant_with_customisation, non_compliant, gap), confidence, citations JSON `[{chunk_id, doc_id, filename, page, quote}]`, gap_reason, approved, approval_override_reason, edited_by_user, needs_review, review_score, review_issues JSON `[{type, message, severity}]`, model, prompt_version |
| `submissionrules` | project_id (unique), rules JSON (shape of `SubmissionRulesOut` + qcbs_split, min_qualifying_marks) |
| `evaluationcriterion` | project_id, code, name, max_marks, weight, sub_criteria JSON, min_qualifying_marks, page |
| `wintheme` | project_id, text, order |
| `outlinesection` | project_id, title, order, page_budget, criterion_id |
| `factconflict` | project_id, key, values JSON `[{value, rows:[{requirement_id, req_code}]}]`, resolved |
| `auditevent` | project_id, entity, entity_id, action (ai_draft, edit, approve, unapprove, unapproved_by_addendum), actor (`user:<id>` / `model:<name>`), before, after, prompt_version, at |
| `answerlibrary` | company_id, requirement_text, answer, source_project_id, source_requirement_id, outcome, embedding |
| `job` | project_id, kind, params JSON, status (queued, running, succeeded, failed), stage, progress, message, error, counts JSON |

Vectors live in SQLite. Retrieval loads one company's chunks into a NumPy matrix per drafting job;
at hackathon scale (thousands of chunks) brute-force cosine is faster and simpler than a vector database.

## 3. API conventions

- Base path `/api`, JSON, `snake_case`. OpenAPI at `/api/openapi.json`, docs at `/api/docs`.
- Errors: `{"error": {"code": "...", "message": "..."}}` — `unauthorized` 401, `not_found` 404,
  `conflict` 409, `validation_failed` 422, `llm_error` 502, `internal` 500 (details never leaked).
- Long work returns `202 {"job_id", "project_id"}`; the UI polls `GET /api/jobs/{id}` (SSE also available at
  `/api/jobs/{id}/events`); `POST /api/jobs/{id}/retry` re-runs a finished job with the same params.
- Uploads are `multipart/form-data` (`files`, `main`, `attachments`, `file`).

| Area | Endpoints |
| --- | --- |
| Auth | `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` |
| Company | `GET/PUT /company`, `GET/POST /knowledge`, `DELETE /knowledge/{id}`, `GET /knowledge/search?q=` |
| Projects | `GET/POST /projects`, `GET/DELETE /projects/{id}`, `POST /projects/{id}/reanalyse` |
| Overview | `GET/PUT /projects/{id}/win-themes`, `GET /projects/{id}/criteria`, `GET /projects/{id}/rules`, `GET/PUT /projects/{id}/go-no-go`, `PUT /projects/{id}/outcome` |
| Matrix | `GET /projects/{id}/requirements` (status, category, mandatory, criterion_id, has_issues, version_status, include_removed, q), `PATCH /requirements/{id}`, `GET /requirements/{id}/diff`, `PATCH /responses/{id}`, `POST /responses/{id}/redraft`, `GET /responses/{id}/history`, `POST /projects/{id}/draft`, `GET /projects/{id}/requirements/{rid}/source.png` |
| Package | `GET /projects/{id}/validate`, `GET/POST /projects/{id}/outline`, `POST /projects/{id}/consistency`, `GET /projects/{id}/conflicts`, `PUT /projects/{id}/conflicts/{cid}/resolve`, `POST /projects/{id}/addenda`, `POST/GET /projects/{id}/package`, `GET /projects/{id}/package/download`, `GET /projects/{id}/package/files/{name}` |

## 4. Auth flow

1. Startup runs migrations and creates the admin from `ADMIN_EMAIL` / `ADMIN_PASSWORD` if no users exist.
2. `POST /api/auth/login` → JWT (HS256, `JWT_SECRET`, `sub=user_id`) in cookie `session`
   (`HttpOnly`, `SameSite=Lax`, `Secure` when the request is https).
3. `current_user` guards every route except login, logout and health.
4. Frontend: `useMe()`; `RequireAuth` redirects to `/login?next=…`; any 401 clears the cache and redirects.
5. Dev: Vite proxies `/api` → `:8000`. Production: FastAPI serves `frontend/dist` on the same port.

## 5. Pipeline and jobs

| Job | Stages |
| --- | --- |
| `analyse` | parse every file → store page texts → chunk (see below) → `classify_chunk` → `extract_submission_rules` (gives the buyer's name) → `extract_requirements` per requirement chunk (parallel, buyer's own duties excluded) → quote check → de-dup (token-set ≥ 0.92) → codes → `extract_criteria` → `link_requirements_to_criteria` (batches of 30). Re-analysis deletes children before parents (responses → requirements → outline → criteria). |
| `index_knowledge` | parse → ~180-word sentence windows (40-word overlap) → embed → `knowledgechunk` |
| `draft` | per requirement (8 parallel): hybrid search (0.7 cosine + 0.3 saturated BM25, × 1.15 for chunks from won-bid documents / × 0.9 lost; top 6; plus answer library × 1.2 won / 0.9 lost) → floor → `draft_response` → citation check → `review_response` + code checks → save + audit. If the result is a gap and the clause is an **undertaking** (submit / furnish / penalties / rate freeze / validity / NDA / project plan …), the answer is an explicit commitment citing the RFP clause (`kind: rfp_clause`, low-severity review note), never a capability claim. |
| `addendum` | parse the addendum → extract obligations → "Clause X is amended / deleted / New clause X is added" → modified (word diff, needs review), added, removed; deadline extension; re-draft changed rows |
| `package` | build outline if missing → render 11 files → ZIP |

Jobs run on a thread pool (`JOB_WORKERS`, default 2); `jobs_inline=True` runs them synchronously (tests, seed).

**Chunking rules (real tenders).** A section starts at a top-level heading whose number follows the previous
one (`1.Introduction`, `2 Eligibility`, no space needed; numbered list items inside a section are ignored),
at a second-level heading of the current section (`5.6Service Level Agreement`), at an all-caps bold heading
(`DISCLAIMER`), or at an annexure / appendix heading (`9.1Annexure 1: …`). Disclaimer, introduction,
assumptions and instruction sections are not mined for requirements. Offline extraction also recognises
"will / is responsible for" obligations with the bidder or solution as subject, bullet deliverables inside table
cells, lead-in lists ("… should cover the following areas:" + items), and treats "should" in eligibility as
mandatory; sentences whose subject is the buyer, the RFP document itself, or an example are skipped.

## 6. LLM layer and guardrails (non-negotiable)

- `get_llm(settings).complete(prompt_name, variables, schema, usage)` → `LLMResult(value, prompt_version, model)`.
  Variables carry both rendered text (for Claude) and structured lists (for the offline provider).
- **Claude**: `client.beta.messages.parse(model=LLM_MODEL, output_format=<Pydantic schema>,
  output_config={"effort": LLM_EFFORT}, betas=["server-side-fallback-2026-07-01"], fallbacks="default")`.
  Refusals and `max_tokens` stops raise or retry once; SDK errors map to `LLMError` with a user-safe message.
- **Offline**: deterministic regex/heuristics; answers are built only from verbatim evidence sentences.
- Requirement `source_quote` must be found (fuzzy ≥ 90) on its page ±1, or the requirement is dropped.
- Every citation quote must be found in its chunk; an answer left without a valid citation becomes a `gap`.
- Retrieval floor (`RETRIEVAL_MIN_SCORE`, 0.35; 0.12 for hash vectors) skips drafting for clearly unrelated evidence.
- Review: no citations (high), over word budget (medium), filler phrases (medium), missing parts (high if
  mandatory), unsupported claims (medium), low specificity (low). Score = 100 − 30/15/5 per issue.
  Approving a row with a high issue needs an override reason (409 otherwise).
- `UsageMeter` enforces `LLM_MAX_TOKENS_PER_PROJECT`. Logs record prompt version and token counts, never content.

## 7. Frontend state

- Server state: TanStack Query hooks in `features/*/api.ts`; keys in `lib/queryKeys.ts`;
  `useInvalidateProject(id)` refreshes everything derived from a project after drafting, edits or addenda.
- Jobs: `useJob(id)` polls every 0.7 s while running; `JobProgress` renders stage steps, counts, errors and Retry.
- URL state: matrix filters (`status`, `mandatory`, `criterion`, `issues`, `changed`, `q`) and the selected `row`.
- Local state: `useState`; forms use react-hook-form + zod mirroring backend validation (GSTIN, PAN).
- Keyboard (`lib/keyboard.ts`): J/K move, A approve, E edit, R re-draft, `/` search — ignored while typing or in dialogs.
- Routes: `/` public landing page, `/login`, and the signed-in app under `/dashboard`, `/company`, `/knowledge`,
  `/projects/...`. The landing hero is a react-three-fiber scene (lazy chunk, colours read from theme CSS
  variables, one canvas at a time, static frame under `prefers-reduced-motion`, fallback if WebGL fails).

## 8. Design system

- shadcn/ui (`radix-nova`) on Tailwind v4; tokens in `src/index.css`: primary `#2952CC` (dark `#6E8EFB`),
  status `--status-full/partial/custom/noncompliant/gap/draft` used as `text-status-*`, `bg-status-*/10`.
- Fonts: Inter (UI), JetBrains Mono (requirement IDs), Source Serif 4 (quotes from documents).
- Matrix: 60/40 split — table + sticky `RowPanel` (quote, View in RFP, answer, evidence, review issues,
  approve / edit / re-draft, status, history).
- Every data view: `LoadingRows` / `EmptyState` (with next action) / `ErrorState` (with Retry);
  status always icon + text + colour; destructive actions confirm with `AlertDialog`.

## 9. Generated documents

One block model (`package.py`) renders to DOCX (python-docx) and PDF (PyMuPDF HTML Story) — no LibreOffice.
Font, size and margins come from the extracted format rules (defaults Calibri 11, 1 inch). Header: bidder +
tender number; footer: bidder, "Page X of Y", signature-and-seal line. Files:
`01_Covering_Letter` (DOCX+PDF), `02_Technical_Proposal` (DOCX+PDF; outline order, compliance summary,
deviations), `03_Compliance_Matrix.xlsx` (frozen header, filters, status fills, landscape),
`04_Annexures_Filled` (DOCX+PDF; RFP wording, profile values, unfilled placeholders highlighted yellow),
`05_Eligibility_Checklist` (DOCX+PDF), `06_Financial_Bid_Template.xlsx` (BoQ structure, prices blank),
`README_Submission_Checklist.pdf`. Names follow the RFP's naming rule, e.g.
`DSHM-HMIS-2026-014_NimbusHealth_02_Technical_Proposal.pdf`.
