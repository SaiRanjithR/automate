# DEMO.md — BidReady hackathon demo script (about 4 minutes)

Theme: **Automate Your Boring Task**. The story: a bid manager gets a 8-page tender (real ones run to
100–300 pages) and needs a compliant, ready-to-sign bid package. Today that is 2–3 days of highlighting
PDFs, copying "shall" sentences into Excel, hunting through old proposals and re-typing company details
into forms. BidReady does it in minutes.

All organisations in the demo data are fictional.

## 0. Before you present (5 minutes, once)

```bash
make setup          # installs deps, migrates, downloads the embedding model (needs internet once)
make demo-reset     # wipes local data and loads the demo company + one drafted project
make dev            # backend :8000 + frontend :5173
```

- Open http://localhost:5173 and sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` from your `.env`.
- Keep these files handy in Finder for drag-and-drop:
  - `samples/hmis-tender/rfp.pdf` — the tender
  - `samples/hmis-tender/corrigendum-1.pdf` — the addendum
- **No internet / no API key?** Set `LLM_PROVIDER=offline` in `.env` (already the default in the
  generated local `.env`). Everything below works offline with the rule-based engine.
- **With Claude:** set `LLM_PROVIDER=anthropic` and a valid `ANTHROPIC_API_KEY`, then `make demo-reset`.
  Answers read better and extraction handles messier tenders. Rehearse once: a live run takes 1–3 minutes.

## What the demo data contains (so you know where the "aha" moments are)

| File | What it shows |
| --- | --- |
| `rfp.pdf` | Tender DSHM/HMIS/2026/014 for a hospital system in 25 district hospitals: instructions, eligibility table, 30 numbered clauses + a module table, scoring criteria (QCBS 70:30), 4 annexures incl. a BoQ |
| `corrigendum-1.pdf` | Deadline moved to 22 Dec; uptime 99.5% → 99.9%; training 300 → 500 staff; clause 4.1.7 deleted; new clause 4.2.9 |
| `Nimbus_Company_Profile.pdf` | The bidder's capabilities, certifications, turnover |
| `Nimbus_Case_Studies.pdf` | 4 past hospital projects (eligibility: ≥ 3 similar projects) |
| `Nimbus_Past_Proposal_Mysuru.docx` | Support SLA, team, training approach |

Planted on purpose:
- **Gaps** (no evidence anywhere): biometric attendance integration, state SMS gateway on DLT, diet and
  kitchen module, and the commercial undertakings (price format, bank guarantee).
- **A contradiction** for the consistency check: the profile says *120 employees* (used for R-4.3-06), the
  past proposal says *150-member team* (used for R-4.3-05).
- **Form field the profile cannot fill**: the EMD refund bank account in Annexure-B (shows the yellow highlight).

## Second dataset: IT / AI company for NLP or software tenders

`make nlp-company` generates and loads a fictional IT/AI company pack (`samples/nlp-company/`) and updates
the company profile while keeping your company name (the old profile is saved to
`backend/data/company_profile_backup.json`):

| File | Role |
| --- | --- |
| `Surya_Company_Profile.pdf` | Incorporation, ITES turnover above INR 25 crore, net worth, ISO 9001/27001/20000, CMMI 3, NLP + search + cloud capabilities |
| `Surya_Case_Studies.pdf` | 4 projects incl. a INR 3.4 crore government NLP search and a INR 5.2 crore turnkey analytics platform |
| `Surya_Proposal_eProcurement_NLP_Search_WON.docx` | Past proposal marked **Won**: training curriculum, project plan, team, hosting |
| `Surya_Proposal_Bank_Chatbot_LOST.docx` | Past proposal marked **Lost** (weaker, ranks lower) |

On a GeM NLP search tender this drafts about 32 of 36 requirements with citations (won-bid evidence is
badged), turns penalty / rate-freeze / project-plan clauses into commitments, and leaves a few honest gaps.

## The script

**1. The pain (20 s).** Show `rfp.pdf`. "Every 'shall' here is a line in a compliance matrix someone builds by hand."

**2. Upload (40 s).** *New project* → drop `rfp.pdf` → *Upload and analyse*. Point at the live steps:
parsing → requirements → submission rules → scoring criteria. Lands on **Overview**:
- Key facts pulled from the tender: deadline, CPPP portal, two-bid system, EMD INR 2,00,000, 30-page limit, QCBS 70:30.
- **How bids are scored**: 6 criteria with marks; every requirement is linked to the criterion it earns marks under.
- **Go / no-go**: fit, risk, time and competition, with reasons. Set competition to 3 to show it recalculate.

**3. Draft (40 s).** *Draft all answers* (or open the seeded project if you are short of time).
Open **Compliance matrix**:
- Chips: compliant / partial / **gaps** / approved. Click *gaps* — the planted gaps appear.
- Click **R-4.2-02** (FHIR / ABDM): cited answer, the evidence quote with file and page, review score.
- Click **View in RFP** — the exact clause is highlighted on the original page.
- Click a gap (**R-4.2-07**, SMS gateway): "No evidence found" — BidReady never invents a capability.
- Keyboard: `J`/`K` to move, `A` to approve. Approve two or three rows.

**4. Addendum (40 s).** **Addenda** tab → drop `corrigendum-1.pdf`. Result: 2 modified, 1 new, 1 removed,
deadline moved to 22 Dec. Show the word-level diff (99.5% → 99.9%). Changed rows were re-drafted and sent
back to review.

**5. Rules (20 s).** **Submission rules**: covers and documents, format rules, eligibility checklist (5 of 6
met from the profile; non-blacklisting needs a self-declaration), forms with fields still to fill.

**6. Package (40 s).** **Outline & package**:
- Readiness score and blockers (unapproved mandatory rows, gaps, a form field) with *Fix* links.
- *Run check* in **Consistency check** → the 120 vs 150 headcount contradiction.
- *Generate package* → 11 files plus a ZIP, named exactly as the tender requires
  (`DSHM-HMIS-2026-014_NimbusHealth_02_Technical_Proposal.pdf` …). Open the technical proposal PDF and
  Annexure-A (filled from the profile). *Download ZIP*.

**7. Close (20 s).** "Two to three days of copy-paste → under five minutes, with every claim traceable to a
source. People still decide: prices, signatures and the upload stay with the bid team."

## Likely judge questions

| Question | Answer |
| --- | --- |
| Can it use our previous wins? | Yes. Upload past proposals in the knowledge base and mark them Won or Lost; evidence from won bids ranks higher, and every approved answer goes into an answer library that future bids reuse (won bids first). |
| What about clauses no document can prove (penalties, bank guarantee, rate freeze)? | Those are commitments: BidReady drafts "We confirm that we accept and will comply…" citing the RFP clause itself and flags it for a person to confirm. It never invents a capability. |
| How do you stop hallucinations? | Answers come only from retrieved evidence; every citation quote is checked against the source text; no valid citation means the row becomes a gap; a review pass flags missing parts and unsupported claims; people approve every row. |
| Confidential tenders? | Runs locally (SQLite, local embeddings). Offline mode makes no external calls. With Claude, only the relevant text is sent. |
| Messy real tenders? | Table-aware PDF parsing, attachments, DOCX, OCR fallback for scanned pages (with Tesseract). With Claude, extraction handles narrative and inconsistent formatting. |
| How is this different from Loopio / AutogenAI? | Indian tender formats (two-bid covers, EMD, annexures, DSC rules), the full ready-to-sign package, addendum diffing, and a price small vendors can afford. |
| How accurate is extraction? | `make eval`: 97% recall, 91% precision on the labelled sample tender with the offline engine. |
