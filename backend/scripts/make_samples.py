"""Generate the demo dataset in ../samples (all organisations and people are fictional).

samples/hmis-tender/rfp.pdf                 the tender (RFP) to upload as a new project
samples/hmis-tender/corrigendum-1.pdf       the addendum (deadline extension, changed and new clauses)
samples/hmis-tender/gold_requirements.json  hand-labelled requirements for `make eval`
samples/company/*.pdf|docx                  knowledge base for the fictional bidder
samples/company/company_profile.json        values to load into the Company profile screen

Run:  cd backend && uv run python scripts/make_samples.py
"""

import html
import json
from pathlib import Path

import pymupdf
from docx import Document
from docx.shared import Pt

ROOT = Path(__file__).resolve().parents[2] / "samples"
TENDER = ROOT / "hmis-tender"
COMPANY = ROOT / "company"

TENDER_NO = "DSHM/HMIS/2026/014"
BUYER = "Deccan State Health Mission (fictional)"
TITLE = "Supply, Implementation and Maintenance of a Hospital Management Information System (HMIS) for 25 District Hospitals"

CSS = """
* { font-family: sans-serif; font-size: 10.5pt; line-height: 1.35; }
h1 { font-size: 17pt; color: #1f2a44; text-align: center; }
h2 { font-size: 13.5pt; font-weight: bold; margin-top: 14px; color: #1f2a44; }
h3 { font-size: 11.5pt; font-weight: bold; margin-top: 8px; }
p.c { text-align: center; }
table { border-collapse: collapse; width: 100%; margin-top: 4px; }
th, td { border: 1px solid #555555; padding: 3px; font-size: 9.5pt; vertical-align: top; }
th { background-color: #e8ecf5; }
p.break { page-break-after: always; }
"""


def write_pdf(path: Path, body: str, footer: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mediabox = pymupdf.paper_rect("a4")
    where = pymupdf.Rect(56, 56, mediabox.width - 56, mediabox.height - 64)
    writer = pymupdf.DocumentWriter(str(path))
    for part in body.split('<p class="break"></p>'):
        story = pymupdf.Story(html=part, user_css=CSS)
        more = True
        while more:
            device = writer.begin_page(mediabox)
            more, _ = story.place(where)
            story.draw(device)
            writer.end_page()
    writer.close()
    with pymupdf.open(path) as doc:
        total = doc.page_count
        for number, page in enumerate(doc, start=1):
            page.insert_text(
                (56, mediabox.height - 34),
                f"{footer}    Page {number} of {total}",
                fontsize=8,
                color=(0.4, 0.4, 0.4),
            )
        doc.saveIncr()


def esc(text: str) -> str:
    return html.escape(text)


def table(header: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in header)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


# ---------------------------------------------------------------- tender content

# (clause, text, is_bidder_requirement)
SCOPE_FUNCTIONAL = [
    (
        "4.1.1",
        "The solution shall provide patient registration with Ayushman Bharat Health Account (ABHA) number linkage at every registration counter.",
        True,
    ),
    (
        "4.1.2",
        "The solution shall provide outpatient (OPD) and inpatient (IPD) management including admission, transfer and discharge summaries.",
        True,
    ),
    (
        "4.1.3",
        "The solution shall include pharmacy, laboratory and radiology modules integrated with the electronic medical record.",
        True,
    ),
    (
        "4.1.4",
        "The solution shall generate itemised patient bills and support cashless claims under the state health insurance scheme.",
        True,
    ),
    (
        "4.1.5",
        "The solution shall provide a dashboard of bed occupancy, OPD footfall and drug stock for the Mission headquarters.",
        True,
    ),
    ("4.1.6", "The user interface shall be available in English and Kannada.", True),
    (
        "4.1.7",
        "The solution shall integrate with the biometric attendance system of the hospitals.",
        True,
    ),
    (
        "4.1.8",
        "The bidder should provide Android and iOS mobile applications for doctors to view patient records.",
        True,
    ),
]
FUNCTIONAL_TABLE = [
    ["M1", "Blood bank management with donor registry and component tracking", "Mandatory"],
    ["M2", "Operation theatre scheduling with surgeon and anaesthetist rosters", "Mandatory"],
    ["M3", "Diet and kitchen management for admitted patients", "Desirable"],
    ["M4", "Telemedicine consultation with video and e-prescription", "Desirable"],
]
SCOPE_TECHNICAL = [
    (
        "4.2.1",
        "The solution shall be hosted on a MeitY-empanelled cloud with all data stored within India.",
        True,
    ),
    (
        "4.2.2",
        "The solution shall support HL7 FHIR R4 interfaces and be certified for ABDM milestones M1, M2 and M3.",
        True,
    ),
    (
        "4.2.3",
        "The bidder shall guarantee 99.5% monthly uptime for the production environment.",
        True,
    ),
    (
        "4.2.4",
        "All data shall be encrypted at rest using AES-256 and in transit using TLS 1.2 or higher.",
        True,
    ),
    (
        "4.2.5",
        "The solution shall provide role-based access control and a tamper-proof audit trail of every record access.",
        True,
    ),
    (
        "4.2.6",
        "The bidder shall get a security audit (VAPT) done by a CERT-In empanelled auditor before go-live and annually thereafter.",
        True,
    ),
    (
        "4.2.7",
        "The solution shall integrate with the state SMS gateway registered on DLT for appointment and report notifications.",
        True,
    ),
    (
        "4.2.8",
        "The bidder shall provide a disaster recovery site with a recovery point objective of 15 minutes.",
        True,
    ),
]
SCOPE_IMPLEMENTATION = [
    (
        "4.3.1",
        "The bidder shall complete go-live in all 25 district hospitals within 6 months of the work order.",
        True,
    ),
    (
        "4.3.2",
        "The bidder shall train at least 300 hospital staff, including doctors, nurses and administrators.",
        True,
    ),
    (
        "4.3.3",
        "The bidder shall migrate existing patient data of the last 3 years from the legacy system.",
        True,
    ),
    (
        "4.3.4",
        "The bidder shall deploy one on-site support engineer at each district hospital for the first 6 months after go-live.",
        True,
    ),
    (
        "4.3.5",
        "The Mission shall provide office space and network connectivity at each hospital.",
        False,
    ),
    (
        "4.3.6",
        "The bidder shall deploy a project team led by a PMP-certified project manager with at least 10 years of experience in hospital IT.",
        True,
    ),
    (
        "4.3.7",
        "The bidder shall have at least 100 employees on its payroll, including implementation engineers.",
        True,
    ),
]
SCOPE_SUPPORT = [
    (
        "4.4.1",
        "The bidder shall provide a 24x7 helpdesk with a response time of 4 hours for critical incidents.",
        True,
    ),
    (
        "4.4.2",
        "The bidder shall provide annual maintenance and support for 5 years after go-live.",
        True,
    ),
    (
        "4.4.3",
        "The bidder shall pay a penalty of 0.5% of the quarterly fee for every 0.1% of uptime below the guaranteed level.",
        True,
    ),
]
COMMERCIAL = [
    (
        "6.1",
        "The bidder shall quote prices in Indian Rupees inclusive of all taxes in the BoQ format at Annexure-D.",
        True,
    ),
    ("6.2", "Bids shall remain valid for 180 days from the last date of submission.", False),
    (
        "6.3",
        "The bidder shall furnish a performance bank guarantee of 5% of the contract value within 15 days of the work order.",
        True,
    ),
]
ELIGIBILITY_ROWS = [
    [
        "1",
        "Average annual turnover of at least INR 5 crore in the last 3 financial years",
        "CA-certified turnover statement",
    ],
    [
        "2",
        "At least 3 HMIS projects in government or private hospitals completed in the last 5 years",
        "Work orders and completion certificates",
    ],
    ["3", "Valid ISO 9001 and ISO 27001 certifications", "Copies of certificates"],
    ["4", "CMMI Level 3 or above", "Copy of appraisal certificate"],
    ["5", "Registered in India for at least 5 years", "Certificate of incorporation"],
    ["6", "Not blacklisted by any government department", "Self-declaration as per Annexure-C"],
]
CRITERIA_ROWS = [
    ["1", "Company experience", "Similar HMIS projects; number of hospitals deployed", "20"],
    [
        "2",
        "Proposed solution and approach",
        "Functional fit; technical architecture; security",
        "30",
    ],
    ["3", "Implementation plan", "Timelines; training plan; data migration", "15"],
    ["4", "Team", "Qualifications of project manager and key staff", "15"],
    ["5", "Support and SLA", "Helpdesk; uptime; maintenance", "10"],
    ["6", "Presentation and product demo", "Live demonstration to the committee", "10"],
]


def clauses_html(items: list[tuple[str, str, bool]]) -> str:
    return "".join(f"<p>{c} {esc(t)}</p>" for c, t, _ in items)


def tender_html() -> str:
    return f"""
<h1>Request for Proposal</h1>
<p class="c"><b>Request for Proposal for {esc(TITLE)}</b></p>
<p class="c">Tender No: {TENDER_NO}</p>
<p class="c">Issued by: {esc(BUYER)}, Health Bhavan, Bengaluru 560001</p>
<p class="c">Date of issue: 10 November 2026</p>
<p class="break"></p>
<h2>1. Introduction</h2>
<p>The Deccan State Health Mission runs 25 district hospitals that today use paper registers and a legacy billing system. The Mission invites proposals from eligible bidders to supply, implement and maintain a modern Hospital Management Information System (HMIS) across all district hospitals.</p>
<h2>2. Instructions to Bidders</h2>
<h3>2.1 Important dates</h3>
{table(["Event", "Date"], [["Pre-bid meeting", "20 November 2026, 11:00 IST"], ["Last date for bid submission", "15 December 2026, 15:00 IST"], ["Opening of technical bids", "16 December 2026, 11:00 IST"]])}
<p>2.2 Bids shall be submitted online on the Central Public Procurement Portal (CPPP) at eprocure.gov.in. Bids received by any other means shall be rejected.</p>
<p>2.3 This tender follows a two-bid system. The bid shall be submitted in two covers as listed below.</p>
<p>Cover-1 (Technical Bid) shall contain:</p>
<p>a) Covering letter as per Annexure-A</p>
<p>b) Bidder details as per Annexure-B</p>
<p>c) Technical proposal</p>
<p>d) Point-by-point compliance statement for Section 4</p>
<p>e) Eligibility documents listed in Section 3</p>
<p>f) Declaration of non-blacklisting as per Annexure-C</p>
<p>Cover-2 (Financial Bid) shall contain:</p>
<p>a) Price bid in the BoQ format at Annexure-D</p>
<p>2.4 The technical proposal shall not exceed 30 pages, using Arial font size 11 pt with margins of 1 inch on all sides.</p>
<p>2.5 All documents shall be uploaded in PDF format, each not larger than 10 MB, and named as follows: &lt;TenderNo&gt;_&lt;BidderName&gt;_&lt;DocumentName&gt;.pdf</p>
<p>2.6 Every page of the bid shall be signed and stamped by the authorised signatory, and the bid shall be digitally signed with a Class 3 Digital Signature Certificate (DSC).</p>
<p>2.7 Bidders shall pay an Earnest Money Deposit (EMD) of INR 2,00,000 through the portal. Micro and Small Enterprises registered on Udyam are exempt from paying EMD on submission of a valid Udyam certificate.</p>
<p>2.8 Bids shall remain valid for 180 days from the last date of submission.</p>
<h2>3. Eligibility Criteria</h2>
<p>The bidder must meet every criterion below on the last date of submission. Bids not meeting any criterion will be rejected without technical evaluation.</p>
{table(["S.No", "Eligibility criterion", "Evidence required"], ELIGIBILITY_ROWS)}
<p class="break"></p>
<h2>4. Scope of Work</h2>
<h3>4.1 Functional Requirements</h3>
{clauses_html(SCOPE_FUNCTIONAL)}
<p>4.1.9 In addition, the solution shall cover the modules listed below.</p>
{table(["Ref", "Module", "Priority"], FUNCTIONAL_TABLE)}
<h3>4.2 Technical Requirements</h3>
{clauses_html(SCOPE_TECHNICAL)}
<h3>4.3 Implementation and Training</h3>
{clauses_html(SCOPE_IMPLEMENTATION)}
<h3>4.4 Support and Service Levels</h3>
{clauses_html(SCOPE_SUPPORT)}
<p class="break"></p>
<h2>5. Evaluation Criteria</h2>
<p>5.1 Bids will be evaluated using Quality and Cost Based Selection (QCBS) with a weightage of 70:30 for technical and financial scores.</p>
<p>5.2 Bidders must obtain a minimum technical score of 70 marks to qualify for financial bid opening.</p>
{table(["S.No", "Criterion", "Sub-criteria", "Max Marks"], CRITERIA_ROWS)}
<h2>6. Commercial Terms</h2>
{clauses_html(COMMERCIAL)}
<p>6.4 The Mission will pay 40% of the implementation fee on go-live and the balance in equal quarterly instalments during the support period.</p>
<p class="break"></p>
<h2>Annexure-A: Bid Submission Letter</h2>
<p>To,</p>
<p>The Mission Director, {esc(BUYER)}</p>
<p>Ref: Tender No [Tender Number]</p>
<p>We, [Name of Bidder], having our registered office at [Registered Address], hereby submit our bid for the above tender. We accept all terms and conditions of the tender without any deviation.</p>
<p>Authorised signatory: [Name of Authorised Signatory]</p>
<p>Designation: [Designation]</p>
<p>Date: [Date]</p>
<h2>Annexure-B: Bidder Details</h2>
<p>Name of the bidder: [Name of Bidder]</p>
<p>Registered address: [Registered Address]</p>
<p>GSTIN: [GSTIN]</p>
<p>PAN: [PAN]</p>
<p>Udyam registration number: [Udyam Number]</p>
<p>Year of incorporation: [Year of Incorporation]</p>
<p>Contact email: [Email]</p>
<p>Contact phone: [Phone]</p>
<p>Bank account for refund of EMD: [Bank Account Number and IFSC]</p>
<h2>Annexure-C: Declaration of Non-Blacklisting</h2>
<p>We, [Name of Bidder], declare that we have not been blacklisted or debarred by any central or state government department or public sector undertaking as on the date of this bid.</p>
<p>Authorised signatory: [Name of Authorised Signatory]</p>
<p>Date: [Date]</p>
<p class="break"></p>
<h2>Annexure-D: Financial Bid (BoQ)</h2>
{table(["S.No", "Item", "Quantity", "Unit", "Unit Rate (INR)", "Total (INR)"], [["1", "HMIS software licences and implementation", "25", "Hospital", "", ""], ["2", "Cloud hosting for 5 years", "60", "Month", "", ""], ["3", "Training of hospital staff", "300", "Person", "", ""], ["4", "On-site support engineers (6 months)", "150", "Person-month", "", ""], ["5", "Annual maintenance and support", "5", "Year", "", ""]])}
"""


def corrigendum_html() -> str:
    return f"""
<h1>Corrigendum No. 1</h1>
<p class="c">Tender No: {TENDER_NO}</p>
<p class="c">{esc(TITLE)}</p>
<p class="c">Date: 28 November 2026</p>
<h2>1. Changes to the Tender</h2>
<p>1.1 The last date for bid submission is extended to 22 December 2026, 15:00 IST.</p>
<p>1.2 Clause 4.2.3 is amended to read: The bidder shall guarantee 99.9% monthly uptime for the production environment.</p>
<p>1.3 Clause 4.3.2 is amended to read: The bidder shall train at least 500 hospital staff, including doctors, nurses and administrators.</p>
<p>1.4 Clause 4.1.7 stands deleted.</p>
<p>1.5 New clause 4.2.9 is added: The solution shall integrate with the state e-Hospital dashboard through secure APIs and publish daily hospital statistics.</p>
<p>All other terms and conditions of the tender remain unchanged.</p>
"""


# ---------------------------------------------------------------- company knowledge


PROFILE = {
    "legal_name": "Nimbus Health Tech Private Limited",
    "short_name": "NimbusHealth",
    "address": "4th Floor, Prestige Tech Park, Outer Ring Road, Bengaluru, Karnataka 560103",
    "gstin": "29AAGCN4821K1Z7",
    "pan": "AAGCN4821K",
    "udyam_no": "UDYAM-KR-03-0045821",
    "signatory_name": "Ananya Rao",
    "signatory_designation": "Director, Public Sector Business",
    "email": "bids@nimbushealth.example",
    "phone": "+91 80 4000 1200",
    "website": "nimbushealth.example",
    "year_established": 2012,
    "turnover": [
        {"fy": "2023-24", "amount_inr": 52_000_000},
        {"fy": "2024-25", "amount_inr": 68_000_000},
        {"fy": "2025-26", "amount_inr": 81_000_000},
    ],
    "certifications": [
        {"name": "ISO 9001:2015", "number": "QMS-IN-22817", "valid_until": "2028-03-31"},
        {"name": "ISO 27001:2022", "number": "ISMS-IN-10442", "valid_until": "2027-09-30"},
        {"name": "CMMI Level 3", "number": "CMMI-DEV-3-58120", "valid_until": "2027-06-30"},
    ],
    "style_sample": "",
}


def company_profile_html() -> str:
    return f"""
<h1>Nimbus Health Tech Private Limited</h1>
<p class="c">Company Profile 2026</p>
<h2>About us</h2>
<p>Nimbus Health Tech Private Limited was incorporated in Bengaluru in 2012 and has 14 years of experience in hospital software. We employ 120 employees across Bengaluru, Hyderabad and Pune, including 45 implementation engineers.</p>
<p>Our flagship product NimbusHMS is a cloud-native Hospital Management Information System used by 38 public and private hospitals across Karnataka, Telangana and Maharashtra.</p>
<h2>NimbusHMS modules</h2>
<p>NimbusHMS covers patient registration with ABHA number linkage, outpatient and inpatient management with admission, transfer and discharge summaries, pharmacy, laboratory and radiology modules integrated with the electronic medical record, and itemised billing with cashless insurance claims.</p>
<p>NimbusHMS includes a blood bank module with donor registry and component tracking, and an operation theatre scheduling module with surgeon and anaesthetist rosters.</p>
<p>NimbusHMS provides real-time dashboards of bed occupancy, OPD footfall and drug stock for hospital and state administrators.</p>
<p>The NimbusHMS user interface is available in English, Hindi and Kannada.</p>
<p>Doctors use the NimbusHMS Android and iOS mobile applications to view patient records and lab results.</p>
<h2>Technology and security</h2>
<p>NimbusHMS is hosted on a MeitY-empanelled cloud data centre in Mumbai, and all patient data is stored within India.</p>
<p>NimbusHMS supports HL7 FHIR R4 interfaces and is certified by the National Health Authority for ABDM milestones M1, M2 and M3.</p>
<p>We guarantee 99.9% monthly uptime for production environments under our standard SLA.</p>
<p>All data in NimbusHMS is encrypted at rest using AES-256 and in transit using TLS 1.3.</p>
<p>NimbusHMS provides role-based access control and a tamper-proof audit trail of every record access.</p>
<p>A disaster recovery site in Hyderabad replicates production continuously with a recovery point objective of 15 minutes.</p>
<p>NimbusHMS exposes secure REST APIs to publish daily hospital statistics to state health dashboards.</p>
<h2>Certifications</h2>
{table(["Certification", "Number", "Valid until"], [[c["name"], c["number"], c["valid_until"]] for c in PROFILE["certifications"]])}
<h2>Financials</h2>
{table(["Financial year", "Turnover (INR crore)"], [["2023-24", "5.20"], ["2024-25", "6.80"], ["2025-26", "8.10"]])}
"""


def case_studies_html() -> str:
    return """
<h1>Case Studies: NimbusHMS in Public Hospitals</h1>
<h2>1. Mysuru District Hospitals Network (2024)</h2>
<p>We implemented NimbusHMS in 12 district hospitals for the Mysuru Health Society and completed go-live in 5 months from the work order.</p>
<p>We trained 450 hospital staff including doctors, nurses and administrators through classroom and on-the-job training.</p>
<p>We migrated 4 years of legacy patient data covering 1.2 million patient records with full validation.</p>
<p>We placed one on-site support engineer at each hospital for the first 3 months after go-live.</p>
<h2>2. Coastal Health Network (2023)</h2>
<p>We implemented NimbusHMS across 8 government hospitals of the Coastal Health Network, including pharmacy, laboratory and radiology modules.</p>
<p>The project integrated NimbusHMS with the state insurance scheme for cashless claims and reduced claim turnaround from 21 days to 6 days.</p>
<h2>3. Telangana Medical College Hospitals (2022)</h2>
<p>We deployed NimbusHMS in 5 medical college hospitals with 3,200 beds and ABDM-compliant health records.</p>
<h2>4. Pune Municipal Hospitals (2021)</h2>
<p>We implemented NimbusHMS in 6 municipal hospitals of Pune with telemedicine consultation and e-prescription.</p>
"""


def write_past_proposal(path: Path) -> None:
    doc = Document()
    doc.styles["Normal"].font.size = Pt(11)
    doc.add_heading("Technical Proposal: HMIS for Mysuru Health Society", level=0)
    doc.add_paragraph(
        "Submitted by Nimbus Health Tech Private Limited, March 2024 (selected and awarded)."
    )
    doc.add_heading("Support and maintenance", level=1)
    doc.add_paragraph(
        "We operate a 24x7 helpdesk with a response time of 2 hours for critical incidents and 8 hours for high-priority incidents."
    )
    doc.add_paragraph(
        "We provide annual maintenance and support for 5 years after go-live, including all software updates and statutory changes."
    )
    doc.add_paragraph(
        "Our SLA includes service credits for uptime below the guaranteed level, calculated on the quarterly fee."
    )
    doc.add_heading("Team", level=1)
    doc.add_paragraph(
        "Our 150-member team includes a PMP-certified project manager with 15 years of experience in hospital IT, 12 implementation engineers and 4 clinical trainers."
    )
    doc.add_heading("Training approach", level=1)
    doc.add_paragraph(
        "We train hospital staff in role-based batches of 25 using a training sandbox, with refresher sessions after go-live."
    )
    doc.add_heading("Security testing", level=1)
    doc.add_paragraph(
        "We get a VAPT security audit done by an independent auditor before go-live and every year thereafter."
    )
    doc.save(str(path))


# ---------------------------------------------------------------- gold labels


def gold() -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for clause, text, is_req in (
        SCOPE_FUNCTIONAL + SCOPE_TECHNICAL + SCOPE_IMPLEMENTATION + SCOPE_SUPPORT + COMMERCIAL
    ):
        if is_req:
            items.append(
                {
                    "clause": clause,
                    "text": text,
                    "type": "optional" if " should " in text else "mandatory",
                }
            )
    items.append(
        {
            "clause": "4.1.9",
            "text": "In addition, the solution shall cover the modules listed below.",
            "type": "mandatory",
        }
    )
    for ref, module, priority in FUNCTIONAL_TABLE:
        items.append(
            {
                "clause": ref,
                "text": module,
                "type": "mandatory" if priority == "Mandatory" else "optional",
            }
        )
    return items


def main() -> None:
    TENDER.mkdir(parents=True, exist_ok=True)
    COMPANY.mkdir(parents=True, exist_ok=True)
    write_pdf(TENDER / "rfp.pdf", tender_html(), f"Tender No {TENDER_NO}")
    write_pdf(
        TENDER / "corrigendum-1.pdf", corrigendum_html(), f"Tender No {TENDER_NO} - Corrigendum 1"
    )
    (TENDER / "gold_requirements.json").write_text(json.dumps(gold(), indent=2))
    write_pdf(
        COMPANY / "Nimbus_Company_Profile.pdf",
        company_profile_html(),
        "Nimbus Health Tech - Company Profile",
    )
    write_pdf(
        COMPANY / "Nimbus_Case_Studies.pdf",
        case_studies_html(),
        "Nimbus Health Tech - Case Studies",
    )
    write_past_proposal(COMPANY / "Nimbus_Past_Proposal_Mysuru.docx")
    (COMPANY / "company_profile.json").write_text(json.dumps(PROFILE, indent=2))
    print(f"Samples written to {ROOT}")


if __name__ == "__main__":
    main()
