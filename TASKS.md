# TASKS.md — BidReady milestone tracker

Rules: do tasks in order; one task per change; a task is done only when its **Verify** passes and
`make check` is green (from task 1.9 onward). Tick `[x]` in the same change. Feature references
(F-A … F-H, ACn) point to `PRODUCT_SPEC.md`.


## Implementation notes (deviations from the original plan)

All tasks below are done and `make check` passes (backend 48 tests, frontend 21 tests). Where the build
differs from a task's wording, this list wins; ARCHITECTURE.md describes the result.

- **2.1–2.3** One Alembic revision (`0001_initial_schema`) holds every table; migrations also run at startup.
  `review_result` lives on `response` (`review_score`, `review_issues`). Added `rfppage` and `knowledgechunk`.
- **2.10** Job progress is polled by the UI (`GET /jobs/{id}`); the SSE endpoint exists but the UI does not need it.
- **3A.3** Tables come from PyMuPDF `find_tables` (pdfplumber removed). OCR uses PyMuPDF + Tesseract when installed.
- **3A.4 / 3A.6** No ChromaDB: embeddings are float32 blobs in SQLite, searched with NumPy + BM25.
  Embeddings use fastembed (ONNX bge-small) instead of sentence-transformers (no PyTorch).
- **3B.1** Tests use the offline provider (`app/llm/offline.py`) instead of a `fake_llm` fixture; the same
  provider powers the no-key demo mode. Claude calls use structured outputs (`beta.messages.parse`) with
  server-side refusal fallbacks; default model `claude-opus-5-5`.
- **3D.2–3D.5** No docxtpl / LibreOffice: one block model renders DOCX (python-docx) and PDF (PyMuPDF Story).
  The package has 11 files (DOCX + PDF for letters/proposal/annexures/eligibility, 2 XLSX, README PDF) + ZIP.
- **3C.4** Plain table instead of TanStack Table; filtering is server-side and URL-driven.
- **4A.5** Demo data is generated (`make samples`) and fictional; `make seed-demo` / `make demo-reset` load it.
- **Post-build (real GeM RFP feedback)** Chunking and offline extraction hardened for real tenders (headings
  without spaces, disclaimers, buyer duties, "will" obligations, table bullets, lead-in lists, RFP No.,
  dd-mm-yyyy deadlines, EMD in lakh/crore); undertakings drafted as commitments to the RFP clause;
  knowledge documents tagged won/lost (migration `0002`) and won-bid evidence ranked higher; re-analysis
  delete-order bug fixed. Tests: `tests/pipeline/test_real_world_patterns.py`.

---

## Phase 1 — Foundation & Setup

- [x] **1.1 Repo skeleton.** Create `backend/`, `frontend/`, `samples/`, root `.gitignore` (Python, Node, `backend/data/`, `.env`, `frontend/dist`), keep the five docs + `.env.example` at root.
  Verify: `ls` shows the tree from ARCHITECTURE §1 top level; `git check-ignore backend/data/x .env` prints both.
- [x] **1.2 Backend project.** `uv init --app` in `backend/`, Python 3.12, add runtime deps (fastapi, uvicorn[standard], pydantic-settings, sqlmodel, alembic, python-multipart, argon2-cffi, pyjwt) and dev deps (pytest, httpx, ruff, mypy).
  Verify: `cd backend && uv sync && uv run python -c "import fastapi, sqlmodel"` exits 0.
- [x] **1.3 Settings + app factory.** `core/config.py` (all vars from `.env.example`), `main.py` with lifespan, `GET /api/health` → `{"status":"ok"}`.
  Verify: `make dev-backend` then `curl -s localhost:8000/api/health` returns ok.
- [x] **1.4 Errors + logging.** `core/errors.py` domain exceptions and handler producing the ARCHITECTURE §3 error shape; `core/logging.py`.
  Verify: unit test raising `NotFoundError` from a test route returns 404 with `error.code == "not_found"`.
- [x] **1.5 Ruff + mypy config.** Ruff rules `E,F,I,B,UP,SIM,RUF`, line length 100; mypy strict on `app/`.
  Verify: `uv run ruff check . && uv run ruff format --check . && uv run mypy app` pass.
- [x] **1.6 Frontend project.** Vite React-TS in `frontend/` with pnpm; TS strict + `noUncheckedIndexedAccess`; `@/` alias; Vite proxy `/api → http://localhost:8000`.
  Verify: `pnpm build` succeeds; `pnpm dev` serves the default page.
- [x] **1.7 Tailwind v4 + shadcn/ui.** Install `tailwindcss @tailwindcss/vite`, init shadcn (radix-nova preset), add button, input, label, card, badge, table, tabs, dialog, alert-dialog, sheet, dropdown-menu, select, textarea, tooltip, progress, skeleton, sonner, form. Theme + status tokens in `index.css` per ARCHITECTURE §8. Fonts Inter, JetBrains Mono, Source Serif 4 via `@fontsource-variable/*`.
  Verify: a temporary page renders a primary Button and each StatusChip colour in light and dark.
- [x] **1.8 Frontend lint/test.** ESLint 9 flat config (typescript-eslint, react-hooks, jsx-a11y), Prettier, Vitest + Testing Library + jsdom.
  Verify: `pnpm lint && pnpm typecheck && pnpm test` pass with one sample test.
- [x] **1.9 Makefile.** Targets: `setup`, `dev`, `dev-backend`, `dev-frontend`, `lint`, `format`, `typecheck`, `test`, `check`, `migrate`, `migration`, `gen-api`, `eval`, `clean-data` (see DEV_SETUP).
  Verify: `make check` runs all backend + frontend checks and passes.
- [x] **1.10 App shell.** React Router 8 routes: `/login`, `/`, `/company`, `/knowledge`, `/projects/new`, `/projects/:id/:tab`; `AppShell` with Sidebar; placeholder pages; `EmptyState`, `ErrorState`, `LoadingRows`, `PageHeader` components.
  Verify: navigating each route renders its placeholder inside the shell; component tests for EmptyState/ErrorState.

## Phase 2 — Data Layer & Auth

- [x] **2.1 DB + Alembic.** `core/db.py` (SQLite at `DATABASE_URL`, `check_same_thread=False`, WAL), Alembic configured with SQLModel metadata.
  Verify: `make migrate` creates `backend/data/app.db`.
- [x] **2.2 Core models.** `user`, `company`, `knowledge_doc`, `project`, `rfp_file`, `job` per ARCHITECTURE §2; migration `0001_core`.
  Verify: `make migrate` applies; pytest creates/reads each model in an in-memory DB.
- [x] **2.3 Requirement models.** `requirement`, `response`, `review_result`, `submission_rules`, `evaluation_criterion`, `win_theme`; migration `0002_requirements`.
  Verify: migration applies on top of 0001; model round-trip tests pass.
- [x] **2.4 Security utils.** `core/security.py`: argon2 hash/verify, JWT create/decode with expiry.
  Verify: unit tests for correct/incorrect password and expired token.
- [x] **2.5 Admin seed.** Lifespan creates admin from env when `user` is empty (AC F-A.5).
  Verify: fresh DB + start → one user exists; second start creates none.
- [x] **2.6 Auth endpoints.** `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`; `current_user` dependency guarding all other routes.
  Verify: API tests for AC F-A.2–4; protected route without cookie → 401.
- [x] **2.7 Frontend API layer.** `pnpm gen:api` (openapi-typescript from `http://localhost:8000/api/openapi.json` → `src/types/api.ts`); typed `lib/api.ts` fetch wrapper (credentials include, error shape parsing); `queryClient`, `queryKeys`.
  Verify: `useMe()` hook test with mocked fetch returns typed user; 401 path tested.
- [x] **2.8 Login page + guard.** Login form (react-hook-form + zod), `RequireAuth`, logout in sidebar.
  Verify: manual: wrong password shows AC F-A.3 message; correct login reaches Dashboard; logout returns to /login.
- [x] **2.9 File storage service.** `services/files.py`: save upload under `data/files/<kind>/<uuid>_<name>`, content-type sniff (PDF magic bytes, DOCX zip + `[Content_Types].xml`), 50 MB limit.
  Verify: unit tests accept PDF/DOCX fixtures, reject a renamed `.txt` and an oversize stream.
- [x] **2.10 Job runner.** `jobs/runner.py` with job rows, progress updates, SSE endpoint, retry endpoint.
  Verify: test job with 3 stages emits 3 progress events and `done`; a failing job ends `failed` and retry re-runs it.

## Phase 3 — Core Feature Build

### 3A. Company & knowledge (F-B)
- [x] **3A.1 Company API.** `GET/PUT /api/company` with GSTIN/PAN validation.
  Verify: API tests for valid save and invalid GSTIN (422).
- [x] **3A.2 Company page.** Form sections: legal, signatory, turnover by year (repeatable), certifications (repeatable), logo/letterhead upload.
  Verify: manual save → reload shows values; zod errors shown inline.
- [x] **3A.3 Parser.** `pipeline/parse.py`: PyMuPDF blocks with page, font size, bold, bbox; pdfplumber tables → `table_row` blocks; DOCX via python-docx; OCR fallback for pages < 50 chars (skip gracefully if tesseract missing, with warning).
  Verify: fixture PDF test asserts page numbers, a heading, and a table row are extracted.
- [x] **3A.4 Embeddings + index.** `pipeline/index.py`: chunk 500–800 tokens / 100 overlap, embed with bge-small, upsert to Chroma `knowledge`; delete by doc_id.
  Verify: index fixture doc, query returns its chunk with filename + page; delete removes it.
- [x] **3A.5 Knowledge API + page.** Upload (multipart, multiple) starts index job; list with status; delete; `GET /api/knowledge/search?q=`.
  Verify: AC F-B.2–4 via API tests; manual upload shows Indexing → Ready.
- [x] **3A.6 Hybrid retrieval.** `pipeline/retrieve.py`: top-6 vector + BM25, min-max normalise, 0.6/0.4 blend, return score.
  Verify: unit test where keyword-only match is still retrieved; scores in [0,1].

### 3B. Project creation & extraction (F-C)
- [x] **3B.1 LLM client.** `llm/client.py` `complete_json()` with schema validation, one retry, token log, project token cap; prompt loader with `version:` header; `fake_llm` pytest fixture.
  Verify: tests for valid output, invalid-then-valid retry, invalid-twice → `LLMError`.
- [x] **3B.2 Project create API.** `POST /api/projects` multipart (main + attachments) → project + rfp_files → starts `analyse` job.
  Verify: API test returns 202 with job_id; files stored; rfp_file roles set.
- [x] **3B.3 Chunk + classify.** `pipeline/chunk.py`: group blocks by heading into ≤ 6k-token chunks with section_path; `classify_chunk` prompt.
  Verify: fixture test chunk count and section paths; classification uses fake_llm.
- [x] **3B.4 Requirement extraction.** Keyword pre-pass + `extract_requirements` prompt per chunk (parallel), quote verification, de-dup (cosine > 0.92), `req_code` assignment.
  Verify: unit tests for quote rejection and de-dup; fixture end-to-end with fake_llm stores requirements.
- [x] **3B.5 Submission rules extraction.** `extract_rules` prompt → `SubmissionRules`; forms with detected fields; nulls for absent items.
  Verify: fixture test; missing deadline stays null (AC F-C.5).
- [x] **3B.6 Evaluation criteria extraction + linking.** `extract_criteria` + `link_requirements_to_criteria` (batches of 30) with embedding fallback.
  Verify: fixture test: criteria stored with marks; every requirement has criterion or null.
- [x] **3B.7 Evaluation script.** `scripts/eval_extraction.py` comparing against `samples/*/gold_requirements.json` (match = fuzzy ≥ 85 on text), prints recall/precision; `make eval`.
  Verify: runs on one sample with real LLM key; numbers printed (target AC F-C.4).
- [x] **3B.8 New project page.** Dropzone (main + attachments), Analyse button, `JobProgress` step list via SSE with live counts, error + Retry.
  Verify: manual run on sample tender reaches Overview; killing the LLM key shows error + Retry.
- [x] **3B.9 Overview page.** Key facts, evaluation criteria list with marks, win themes editor (max 3) — `GET/PUT /api/projects/{id}/win-themes`.
  Verify: manual: facts match the sample tender; 4th win theme is blocked.
- [x] **3B.10 Rules page.** Covers/documents checklist, format rules, forms with fill status, eligibility evidence checklist.
  Verify: manual against sample tender's instructions section.

### 3C. Drafting, review & matrix (F-D)
- [x] **3C.1 Draft service.** `pipeline/draft.py`: retrieval floor → gap; `draft_response` prompt with criterion, marks, win themes, profile; citation verification; status/confidence; per-row job with Semaphore(8); SSE `row` events.
  Verify: unit tests for AC F-D.1–3 (prompt snapshot contains criterion + themes).
- [x] **3C.2 Review service.** `pipeline/review.py`: code checks (citations, word budget default 150, banned phrases) + `review_response` prompt → `review_result`.
  Verify: unit tests: uncited sentence → `unsupported_claim`; banned phrase → `generic`; score range 0–100.
- [x] **3C.3 Matrix APIs.** `GET /api/projects/{id}/requirements` (filters, pagination, joined response + review), `PATCH /api/requirements/{id}`, `PATCH /api/responses/{id}` (edit/approve with override rule), `POST /api/responses/{id}/redraft`, `POST /api/projects/{id}/draft`.
  Verify: API tests incl. AC F-D.5 (approve with high-severity issue and no reason → 409).
- [x] **3C.4 MatrixTable.** TanStack Table columns: ID (mono), Requirement, Criterion, Mandatory, Status chip, Review score, Confidence; virtualised; filters + search in URL params; summary chips.
  Verify: component test for filter combination and chip counts (AC F-D.6).
- [x] **3C.5 RowPanel.** Requirement quote (serif) + source link, answer editor, citations, review issues with fix actions, Approve / Approve with reason / Re-draft (hint) / Edit.
  Verify: component tests for approve-with-reason flow; manual edit sets `edited_by_user`.
- [x] **3C.6 Live streaming + shortcuts.** `useJobEvents` merges SSE rows into cache; keyboard J/K/A/E/R and `/`.
  Verify: manual "Draft all" shows rows filling progressively; shortcut test in Vitest.

### 3D. Validate & package (F-E)
- [x] **3D.1 Validator.** `pipeline/validate.py` + `services/scoring.py` readiness; `GET /api/projects/{id}/validate`.
  Verify: unit tests for each blocker type in AC F-E.1 and score 100 only at zero blockers.
- [x] **3D.2 Templates.** Create the five DOCX templates in `app/templates/` with docxtpl tags; font/margin override helper.
  Verify: render each with fixture context; open with python-docx and assert key fields present.
- [x] **3D.3 XLSX builders.** Compliance matrix (frozen header, filters, status fills, landscape) and BoQ template (structure only, no prices).
  Verify: openpyxl tests assert header, freeze pane, no numeric price cells (AC F-E.6).
- [x] **3D.4 Annexure filling.** Reproduce each form's text, fill fields from profile, highlight unfilled in yellow.
  Verify: fixture form with one unknown field → highlighted run present.
- [x] **3D.5 PDF conversion + ZIP.** soffice conversion (60 s timeout, clear error if soffice missing), naming rule, zip; package job; download endpoint.
  Verify: API test (soffice mocked) zip contains 7 expected names; manual real run < 30 s (AC F-E.7).
- [x] **3D.6 Package page.** Readiness ScoreRing, blockers with links to rows/rules, Generate button (disabled while blockers unless "Generate anyway" confirm), file list with page counts, Download.
  Verify: manual full flow on sample tender produces a ZIP that opens correctly.

## Phase 4 — Polish, UX & Edge Cases

### 4A. Hardening (required)
- [x] **4A.1 Loading/empty/error audit.** Every query view uses LoadingRows / EmptyState / ErrorState.
  Verify: checklist of pages in PR description; manual with API stopped shows ErrorState everywhere.
- [x] **4A.2 Edge cases.** Scanned PDF (OCR path), DOCX RFP, RFP with no evaluation section, empty knowledge base (all gaps, clear banner), deadline already passed, 300-page RFP.
  Verify: one pipeline test per case with fixtures/fake_llm; no unhandled exceptions.
- [x] **4A.3 Accessibility pass.** aria-labels on icon buttons, focus management in RowPanel, StatusChip icon+text, contrast check.
  Verify: `eslint-plugin-jsx-a11y` clean; manual keyboard-only run through matrix.
- [x] **4A.4 Dashboard.** Project cards with deadline countdown, readiness ring, gap count, go/no-go badge (if computed), outcome.
  Verify: manual with 2 projects.
- [x] **4A.5 Demo seed.** `make seed-demo` loads one sample tender + sample company docs (public/synthetic only).
  Verify: fresh clone → `make setup seed-demo dev` → demo flow works.
- [x] **4A.6 Production build.** FastAPI serves `frontend/dist`; single `make start`.
  Verify: `make build start` serves app on :8000 with login working.

### 4B. P1 stretch (in this order; skip any not reached)
- [x] **4B.1 Go / no-go (F-F).** `scoring.go_no_go()` pure function + endpoint + Overview card with factors and competition input.
  Verify: unit tests incl. failed eligibility → no-go; UI recalculates on rating change.
- [x] **4B.2 Addendum diff (F-G).** Upload addendum, parse/extract, match (cosine > 0.85 + text ratio), label rows, word diff UI, re-draft modified/added.
  Verify: fixture addendum test for all four labels; approved modified rows revert to needs review.
- [x] **4B.3 Consistency checker (F-H).** `extract_facts`, conflicts table, Package page list, validator blocker.
  Verify: fixture with team size 50 vs 40 yields one conflict.
- [x] **4B.4 Outline generator.** Page budgets from marks, requirement→section assignment, Package page bars, package renders in outline order.
  Verify: budgets sum to page limit ± 0.5.
- [x] **4B.5 Click-to-source.** react-pdf viewer, page endpoint, bbox highlight.
  Verify: clicking a requirement opens its page with highlight.
- [x] **4B.6 Audit trail.** `audit_event` writes on draft/edit/approve; history tab in RowPanel.
  Verify: edit then approve → two events with actor and before/after.
- [x] **4B.7 Learning loop.** Answer library on approve; project outcome endpoint; retrieval multiplier by outcome.
  Verify: retrieval test shows won answer ranked above identical unknown answer.
