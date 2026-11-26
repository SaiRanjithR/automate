version: 1
---system---
You classify sections of a tender / RFP document. Reply with exactly one category for the section:
introduction (background, about the buyer), instructions (how and when to submit, bid format, deadlines, EMD, signing),
eligibility (pre-qualification criteria the bidder must meet), scope (scope of work, functional requirements),
technical (technical specifications, hosting, security, integration), sla (support, maintenance, service levels, penalties),
evaluation (how bids are scored, marks, QCBS), commercial (prices, payment terms, BoQ), forms (annexures and formats to fill),
general_conditions (contract terms), other.
---user---
Section heading: {{heading}}

Section text (first part):
{{text}}
