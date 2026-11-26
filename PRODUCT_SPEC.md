# PRODUCT_SPEC.md — BidReady

## 1. Value proposition

**Upload a tender, get back a ready-to-sign bid package in minutes instead of days.**

BidReady reads an RFP / tender (plus its attachments and addenda), extracts every requirement,
submission rule and scoring criterion, drafts evidence-backed answers from the company's own documents,
reviews each answer for compliance as it is written, and assembles the files in the exact format the
tender demands. People keep the judgement calls: prices, the digital signature, the upload, and final approval.

Hackathon theme fit — *Automate Your Boring Task*: it removes manual requirement "shredding",
copy-pasting old answers, re-typing company details into forms, and hand-checking format rules.

## 2. Target audience

| Persona | Need |
| --- | --- |
| Bid / proposal manager at an SME | Turn a 100+ page tender into a complete, compliant draft fast |
| MSME founder bidding alone on GeM / CPPP | Know eligibility instantly; get forms auto-filled |
| Subject-matter expert | Verify pre-drafted answers with sources instead of writing from scratch |
| Authorised signatory | Receive a correctly named package plus a submission checklist |

Primary market: small and mid-size vendors bidding on Indian public tenders (GeM, CPPP, state portals).
Works for private-sector and English-language international RFPs too.

## 3. Scope

### In scope (build these)
- **P0 (MVP, must work in the demo)**
  1. Login (single workspace, admin-created users).
  2. Company profile and knowledge-base upload (PDF, DOCX) with indexing.
  3. Project creation from RFP upload: main document + attachments (PDF/DOCX, text-based; OCR fallback for scanned pages).
  4. Extraction of requirements, submission rules, and evaluation criteria (with marks/weights).
  5. Win themes (up to 3 per project).
  6. Auto-drafted, cited, criteria-aware answers with compliance status, confidence, and gap flags.
  7. Live compliance review score and issues on every drafted answer.
  8. Interactive compliance matrix: filter, edit, re-draft, approve.
  9. Pre-submission validator with readiness score and blockers.
  10. Package generation: covering letter, technical proposal, compliance matrix (XLSX), filled annexures,
      eligibility checklist, financial BoQ template, submission README — DOCX + PDF, zipped, named per the rules.
- **P1 (stretch, in this order)**
  11. Structured go / no-go.
  12. Addendum diff (added / modified / removed requirements, re-draft affected rows).
  13. Consistency checker across answers.
  14. Proposal outline with page budget per section.
  15. Click-to-source PDF viewer highlighting.
  16. Audit trail per answer.
  17. Answer library learning loop (won/lost outcome boosts retrieval).

### Out of scope (do NOT build, even partially)
- Entering prices or computing bid prices.
- Digital signature (DSC) application or portal upload/submission automation.
- Tender discovery, opportunity pipeline, CRM features.
- Competitor intelligence (beyond a manual 1–5 rating in go / no-go).
- Real-time multi-user collaboration, comments, row assignment, role-based permissions.
- Multi-tenant SaaS, billing, sign-up, password reset emails, SSO.
- Non-English documents; handwritten or image-only tenders beyond basic OCR.
- Fine-tuning or training any model; integrations (SharePoint, Google Drive, Salesforce, email).
- Mobile layouts below 1024 px width (desktop-first; must not break, need not be optimised).
- Security certifications (SOC 2, FedRAMP).

## 4. Glossary

RFP / tender (buyer's document) · Requirement (an obligation on the bidder, usually "shall/must") ·
Compliance status (`fully_compliant`, `partially_compliant`, `non_compliant`, `compliant_with_customisation`, `gap`) ·
Submission rules (how/where/format to submit) · Evaluation criterion (how bids are scored) ·
Annexure / form (fixed-format document to fill) · Addendum / corrigendum (official change to the RFP) ·
EMD (earnest money deposit) · BoQ (bill of quantities, price sheet) · DSC (digital signature certificate) ·
QCBS (quality-and-cost-based selection, e.g. 70:30).

## 5. User flows and acceptance criteria

Acceptance criteria are written so an agent can verify them with a test or a manual check against the
sample tender in `samples/`.

### F-A. Login
Flow: user opens app → login page → enters email + password → lands on Dashboard.
- [ ] AC1: Unauthenticated access to any page except `/login` redirects to `/login`.
- [ ] AC2: Valid credentials set an httpOnly session cookie and redirect to `/`.
- [ ] AC3: Invalid credentials show "Email or password is incorrect" without revealing which.
- [ ] AC4: Logout clears the cookie; API calls then return 401.
- [ ] AC5: The admin user is created from `ADMIN_EMAIL` / `ADMIN_PASSWORD` on first startup if no users exist.

### F-B. Company profile and knowledge base
Flow: Company page → fill legal details, signatory, turnover by year, certifications → Save.
Knowledge page → upload files → each shows "Indexing…" then "Ready (N pages)".
- [ ] AC1: Profile fields persist and reload; GSTIN (15 chars) and PAN (10 chars) formats validated client and server side.
- [ ] AC2: Upload accepts PDF/DOCX ≤ 50 MB; other types rejected with a clear message (type checked by content).
- [ ] AC3: An indexed file's chunks are retrievable: the search box returns relevant passages with file name and page.
- [ ] AC4: Deleting a file removes its chunks from the vector store.

### F-C. Create project and extract
Flow: New project → drop RFP + attachments → "Analyse" → progress steps with live counts
(Parsing → Finding requirements → Reading submission rules → Reading scoring criteria) → Overview.
- [ ] AC1: Text-based 100-page PDF completes parsing in < 20 s; pages with < 50 chars of text are OCR'd.
- [ ] AC2: Every extracted requirement has text, file, section path, page, type (mandatory/optional), category, and a `source_quote` that exists verbatim (fuzzy ≥ 0.9) on that page; items failing this are dropped and logged by count.
- [ ] AC3: Requirements from tables and attachments are included.
- [ ] AC4: On the evaluation set, requirement recall ≥ 90% and precision ≥ 85% (`make eval`).
- [ ] AC5: Submission rules include deadline, portal, covers/volumes, file formats, page limit, font, naming, EMD, eligibility criteria with evidence, and forms list — absent items are `null`, never guessed.
- [ ] AC6: Evaluation criteria include name, max marks/weight, and page; every requirement is linked to one criterion or `null`.
- [ ] AC7: A failed stage shows an error with Retry; retry resumes from that stage.

### F-D. Draft and review answers (compliance matrix)
Flow: Matrix → "Draft all" → rows stream in with status, confidence, review score → user selects a row →
side panel shows requirement quote, answer, citations, review issues → edit / re-draft / approve.
- [ ] AC1: Each answer cites ≥ 1 knowledge source with a verbatim quote; uncited or unverifiable answers become status `gap` with a `gap_reason`.
- [ ] AC2: If top retrieval similarity < 0.35, the row is `gap` and no answer text is generated.
- [ ] AC3: Drafting prompt includes the linked criterion, its marks, and win themes (verified in prompt snapshot test).
- [ ] AC4: Each draft gets a review score 0–100 and issues typed `missing_part | unsupported_claim | generic | over_budget`.
- [ ] AC5: A row with a high-severity issue can only be approved with an override reason.
- [ ] AC6: Filters (status, category, mandatory, criterion, has issues) and search work together; counts in summary chips match the filtered data.
- [ ] AC7: Editing an answer marks it `edited_by_user`; re-draft accepts an optional hint.
- [ ] AC8: Keyboard: J/K move rows, A approves, E edits, R re-drafts, `/` focuses search.

### F-E. Validate and generate package
Flow: Package tab → readiness score + blockers → fix → "Generate package" → file list with previews → Download ZIP.
- [ ] AC1: Blockers include: unapproved mandatory rows, `gap` mandatory rows, unfilled form fields, missing eligibility evidence, page limit exceeded, deadline passed, (P1) open consistency conflicts.
- [ ] AC2: Readiness score = 100 only when there are zero blockers.
- [ ] AC3: ZIP contains the seven files listed in §3 item 10, named per the extracted naming rule (fallback `<TenderNo>_<CompanyShortName>_<NN>_<DocName>`).
- [ ] AC4: Generated documents use the font, size and margins from the submission rules when present.
- [ ] AC5: Annexures reproduce the RFP form wording; fields filled from the profile; unfillable fields highlighted yellow.
- [ ] AC6: The financial BoQ template contains structure only — no price values.
- [ ] AC7: Generation of a 40-page proposal completes in < 30 s.

### F-F. Go / no-go (P1)
- [ ] AC1: Shows score and four factors (fit, risk, resources, competition) with one-line reasons.
- [ ] AC2: Any failed eligibility criterion forces "No-go" regardless of score.
- [ ] AC3: Changing the competition rating recalculates immediately.

### F-G. Addendum diff (P1)
- [ ] AC1: Uploading an addendum labels each requirement unchanged / modified / added / removed.
- [ ] AC2: Modified rows show a word-level diff; only modified and added rows are re-drafted.
- [ ] AC3: Previously approved answers on modified rows revert to "needs review".

### F-H. Consistency, outline, audit, learning (P1)
- [ ] Consistency: conflicting values for the same fact key across approved answers are listed with links to both rows.
- [ ] Outline: section page budgets sum to the page limit (± 0.5); each requirement assigned to one section.
- [ ] Audit: every edit, approval, and AI draft writes an event visible in the row's history.
- [ ] Learning: approving copies the answer into the library; recording "won" boosts those answers in retrieval (× 1.2).

## 6. Success metrics (demo)

| Metric | Target |
| --- | --- |
| Upload → downloadable package (100-page RFP, ~150 rows) | < 5 minutes |
| Requirement recall / precision | ≥ 90% / ≥ 85% |
| Non-gap answers with a verified citation | 100% |
| Submission rules captured | All stated in the instructions section |
