# BidReady — RFP Compliance Matrix & Auto-Drafter

Upload a tender, get back a ready-to-sign bid package in minutes instead of days.

BidReady reads an RFP (with attachments and addenda), extracts every requirement, submission rule and
scoring criterion, drafts cited answers from your own documents, reviews each answer for compliance,
and generates the covering letter, technical proposal, compliance matrix, filled annexures, eligibility
checklist, BoQ template and submission checklist — named and formatted as the tender requires.

Built for the hackathon theme **Automate Your Boring Task**.

## Quick start

```bash
cp .env.example .env    # set JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD; optionally ANTHROPIC_API_KEY
make setup
make seed-demo          # optional: demo company + a drafted sample project (hospital tender)
make nlp-company        # optional: sample IT/AI company docs for NLP / software tenders
make dev                # http://localhost:5173 (landing page; the app is at /dashboard)
```

No API key? `LLM_PROVIDER=offline` runs everything with a deterministic rule-based engine.

## Docs

| File | What it covers |
| --- | --- |
| [DEMO.md](DEMO.md) | 4-minute demo script, demo data story, judge Q&A |
| [PRODUCT_SPEC.md](PRODUCT_SPEC.md) | Scope, user flows, acceptance criteria |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Folder layout, data model, API, pipeline, guardrails, design system |
| [DEV_SETUP.md](DEV_SETUP.md) | Prerequisites, environment variables, commands, troubleshooting |
| [TASKS.md](TASKS.md) | Build tracker |
| [CLAUDE.md](CLAUDE.md) | Rules for AI coding agents working in this repo |

## Stack

FastAPI · SQLModel/SQLite · PyMuPDF · fastembed (bge-small) · Claude (`claude-opus-5-5`) or offline engine ·
python-docx · openpyxl · React 19 · Vite · Tailwind v4 · shadcn/ui · TanStack Query.

## Status

`make check` → backend 48 tests, frontend 21 tests, ruff, mypy strict, ESLint, Prettier, tsc — all passing.
Extraction on the labelled sample tender: 97% recall, 91% precision (`make eval`).
