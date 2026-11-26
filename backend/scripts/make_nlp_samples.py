"""Generate a sample knowledge pack for an IT / AI company bidding on an NLP search tender.

All content is FICTIONAL sample data for demos. Writes ../samples/nlp-company/:
  Surya_Company_Profile.pdf
  Surya_Case_Studies.pdf
  Surya_Proposal_eProcurement_NLP_Search_WON.docx      (marked won)
  Surya_Proposal_Bank_Chatbot_LOST.docx                (marked lost)
  manifest.json            doc type + bid outcome per file (used by the loader)
  company_profile.json     values for the Company profile screen

Run:  cd backend && uv run python scripts/make_nlp_samples.py
Load: cd backend && uv run python -m app.scripts.load_company_pack ../samples/nlp-company --apply-profile
"""

import json
from pathlib import Path

from docx import Document
from docx.shared import Pt
from make_samples import esc, table, write_pdf

OUT = Path(__file__).resolve().parents[2] / "samples" / "nlp-company"
NAME = "Surya Private Limited"
SAMPLE = "Sample document - fictional data for demonstration only."

PROFILE = {
    "legal_name": NAME,
    "short_name": "Surya",
    "address": "7th Floor, Embassy Tech Square, Outer Ring Road, Bengaluru, Karnataka 560103",
    "gstin": "29AAKCS7314M1Z2",
    "pan": "AAKCS7314M",
    "udyam_no": "",
    "signatory_name": "Rohan Mehta",
    "signatory_designation": "Vice President, Government Business",
    "email": "bids@surya-ai.example",
    "phone": "+91 80 4718 2200",
    "website": "surya-ai.example",
    "year_established": 2011,
    "turnover": [
        {"fy": "2022-23", "amount_inr": 312_000_000},
        {"fy": "2023-24", "amount_inr": 368_000_000},
        {"fy": "2024-25", "amount_inr": 415_000_000},
    ],
    "certifications": [
        {"name": "ISO 9001:2015", "number": "QMS-SU-40218", "valid_until": "2028-01-31"},
        {"name": "ISO 27001:2022", "number": "ISMS-SU-11873", "valid_until": "2027-08-31"},
        {"name": "ISO 20000-1:2018", "number": "ITSM-SU-5521", "valid_until": "2027-11-30"},
        {"name": "CMMI Level 3", "number": "CMMI-DEV-3-77102", "valid_until": "2027-05-31"},
    ],
    "style_sample": "",
}

MANIFEST = {
    "Surya_Company_Profile.pdf": {"doc_type": "profile", "outcome": "unknown"},
    "Surya_Case_Studies.pdf": {"doc_type": "case_study", "outcome": "unknown"},
    "Surya_Proposal_eProcurement_NLP_Search_WON.docx": {
        "doc_type": "past_proposal",
        "outcome": "won",
    },
    "Surya_Proposal_Bank_Chatbot_LOST.docx": {"doc_type": "past_proposal", "outcome": "lost"},
}


def profile_html() -> str:
    return f"""
<h1>{esc(NAME)}</h1>
<p class="c">Company Profile 2026 · {esc(SAMPLE)}</p>
<h2>1. About us</h2>
<p>{esc(NAME)} was incorporated in Bengaluru in 2011 under the Companies Act, 1956 and is registered with GSTN. We have 15 years of continuous operations as an IT and ITES company providing software implementation, data analytics and artificial intelligence services.</p>
<p>We employ 320 employees, including 85 data scientists and machine learning engineers and a dedicated search engineering practice.</p>
<p>We have delivered data analytics and AI solutions for central and state government departments, public sector undertakings and large e-commerce marketplaces.</p>
<h2>2. Financials</h2>
<p>Our turnover from IT and ITES services exceeded INR 25 crore in each of the last three financial years, and our net worth has been positive in each of those years.</p>
{table(["Financial year", "ITES turnover (INR crore)", "Net worth (INR crore)"], [["2022-23", "31.20", "18.40"], ["2023-24", "36.80", "22.90"], ["2024-25", "41.50", "27.60"]])}
<h2>3. Certifications</h2>
{table(["Certification", "Number", "Valid until"], [[c["name"], c["number"], c["valid_until"]] for c in PROFILE["certifications"]])}
<h2>4. NLP and search capabilities</h2>
<p>Our search engineering team builds NLP pipelines that perform stop word removal, stemming, lemmatization, tokenization, normalization and noise removal on user search strings to generate optimized query strings.</p>
<p>Our string optimizer isolates product feature information by focusing on words specific to the product, such as brand, size, material and model number.</p>
<p>We build category classifiers using TF-IDF, word2vec, Support Vector Machine, Naive Bayes and transformer models to identify the product or service category in a search string.</p>
<p>We pass the predicted product category as an input along with the search string to Apache Solr and Elasticsearch, which improves the relevance of search results.</p>
<p>We train Named Entity Recognition models on catalogue metadata to identify product and service features in natural language search text.</p>
<p>Our data engineers study and curate metadata for product and service categories before model training.</p>
<h2>5. Platform engineering</h2>
<p>We expose NLP capabilities as containerised micro-services and REST APIs that are consumed by web services and by Apache Solr.</p>
<p>We host micro-services on MeitY-empanelled cloud services inside a Virtual Private Cloud with virtual networks, load balancing, web application firewalls, auto-scaling and high availability across two availability zones.</p>
<p>We have optimised and refurbished existing Apache Solr search clusters in coordination with the client's managed service provider, including schema redesign, synonym management and relevance tuning.</p>
<p>Our change management framework uses Git-based versioning with change history, date and user information for every commit, and tracks migration of code from development to staging to production with security scanning at each stage.</p>
<p>Environment configuration is managed as code, so the production version can be recreated in a separate environment for debugging and troubleshooting, and upgrades, patch releases and security updates are applied through the same pipeline.</p>
"""


def case_studies_html() -> str:
    rows = [
        [
            "Deccan State e-Procurement Agency (fictional)",
            "NLP-based product search for a state e-procurement portal",
            "INR 3.40 crore",
            "2024",
            "Government",
        ],
        [
            "BharatBazaar Marketplace (fictional)",
            "Product category classifier for 2 million listings",
            "INR 1.60 crore",
            "2023",
            "Private",
        ],
        [
            "Western Region Transport Corporation (fictional)",
            "Turnkey analytics platform for ticketing and fleet data",
            "INR 5.20 crore",
            "2022",
            "Government (PSU)",
        ],
        [
            "Coastal Power Distribution Ltd (fictional)",
            "Customer-service chatbot with intent classification",
            "INR 1.10 crore",
            "2021",
            "Government (PSU)",
        ],
    ]
    return f"""
<h1>Case Studies</h1>
<p class="c">{esc(NAME)} · {esc(SAMPLE)}</p>
<h2>Summary of relevant projects (last 5 years)</h2>
{table(["Client", "Project", "Order value", "Year", "Sector"], rows)}
<h2>1. NLP-based product search, Deccan State e-Procurement Agency (2024)</h2>
<p>We delivered a turnkey NLP search enhancement worth INR 3.40 crore for a government e-procurement portal with 1.8 million catalogue items.</p>
<p>The solution combined a string optimizer, a category classifier and a Named Entity Recognition model integrated with the existing Apache Solr search.</p>
<p>Search accuracy on the top 10 results improved from 62% to 88% within 4 months of go-live, and zero-result searches fell by 47%.</p>
<p>The NLP optimizer was deployed as micro-services on a MeitY-empanelled cloud with load balancing and firewalls.</p>
<h2>2. Product category classifier, BharatBazaar Marketplace (2023)</h2>
<p>We built a category classifier using TF-IDF features with Support Vector Machine and fine-tuned transformer models, reaching 93% top-1 accuracy across 4,200 categories.</p>
<h2>3. Turnkey analytics platform, Western Region Transport Corporation (2022)</h2>
<p>We implemented a turnkey data analytics platform worth INR 5.20 crore for a government transport corporation, covering data lake, dashboards and demand forecasting.</p>
<h2>4. Customer-service chatbot, Coastal Power Distribution Ltd (2021)</h2>
<p>We implemented an intent-classification chatbot handling 30,000 consumer queries a month in English and Kannada.</p>
"""


def won_proposal(path: Path) -> None:
    doc = Document()
    doc.styles["Normal"].font.size = Pt(11)
    doc.add_heading(
        "Technical Proposal: NLP Search Enhancement for the Deccan State e-Procurement Portal",
        level=0,
    )
    doc.add_paragraph(f"Submitted by {NAME}, February 2024. Result: awarded (won). {SAMPLE}")
    sections = {
        "Solution overview": [
            "We will deliver a string optimizer, a category classifier and a Named Entity Recognition model as an NLP optimizer layer in front of the existing Apache Solr search.",
            "The NLP optimizer is exposed as REST APIs and micro-services consumed by the portal web service and by Apache Solr.",
        ],
        "Training plan": [
            "We train client staff in implementation, operations, management, error handling and system administration through classroom sessions and hands-on labs.",
            "The training curriculum covers solution architecture and design, technical operations and functionalities of the solution, techniques of generating reports from the solution, development and deployment of the solution, resolving user queries, and advanced troubleshooting techniques.",
            "Each participant receives role-based manuals, recorded sessions and a sandbox environment for practice.",
        ],
        "Project plan and implementation approach": [
            "We deliver the NLP search enhancement in 16 weeks through four milestones: discovery and metadata study, model building and evaluation, API integration with Solr, and go-live with hypercare.",
            "Our detailed project plan includes a work breakdown structure, milestone deliverables, acceptance criteria and a weekly governance cadence with the client.",
        ],
        "Team": [
            "Our team is led by a full-time PMP-certified project manager with 14 years of experience in government IT projects, supported by 4 data scientists, 3 search engineers and 2 cloud engineers.",
        ],
        "Hosting, security and operations": [
            "The solution is hosted on a MeitY-empanelled cloud in a Virtual Private Cloud with network segmentation, load balancing, firewalls and high availability.",
            "We follow ISO 27001 controls for data security and sign the client's non-disclosure agreement before accessing any data.",
            "All processing of client data happens inside India on the MeitY-empanelled cloud.",
        ],
    }
    for heading, paragraphs in sections.items():
        doc.add_heading(heading, level=1)
        for text in paragraphs:
            doc.add_paragraph(text)
    doc.save(str(path))


def lost_proposal(path: Path) -> None:
    doc = Document()
    doc.styles["Normal"].font.size = Pt(11)
    doc.add_heading("Technical Proposal: Conversational Banking Assistant", level=0)
    doc.add_paragraph(f"Submitted by {NAME}, August 2023. Result: not awarded (lost). {SAMPLE}")
    doc.add_heading("Training", level=1)
    doc.add_paragraph(
        "We provide a two-day training on chatbot administration and report generation for the bank's operations team."
    )
    doc.add_heading("Team", level=1)
    doc.add_paragraph(
        "The project will be managed by a project manager with 8 years of experience in banking IT."
    )
    doc.save(str(path))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    footer = f"{NAME} - sample data"
    write_pdf(OUT / "Surya_Company_Profile.pdf", profile_html(), footer)
    write_pdf(OUT / "Surya_Case_Studies.pdf", case_studies_html(), footer)
    won_proposal(OUT / "Surya_Proposal_eProcurement_NLP_Search_WON.docx")
    lost_proposal(OUT / "Surya_Proposal_Bank_Chatbot_LOST.docx")
    (OUT / "manifest.json").write_text(json.dumps(MANIFEST, indent=2))
    (OUT / "company_profile.json").write_text(json.dumps(PROFILE, indent=2))
    print(f"Sample company pack written to {OUT}")


if __name__ == "__main__":
    main()
