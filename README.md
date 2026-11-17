# ControlMap

### Cybersecurity Framework Crosswalk and Audit Evidence Mapping

ControlMap is a cybersecurity compliance mapping application designed to help Governance, Risk, and Compliance (GRC) analysts understand and map security controls across multiple cybersecurity frameworks.

## Problem Statement

Organizations must comply with multiple cybersecurity frameworks, including NIST Cybersecurity Framework (CSF) 2.0, NIST SP 800-53 Revision 5, and SEBI's Cybersecurity and Cyber Resilience Framework (CSCRF).

These frameworks describe similar security concepts using different terminology and control structures. Organizations often perform cross-framework mapping manually using spreadsheets, which can lead to inconsistencies, missed requirements, and incorrect applicability assessments.

ControlMap aims to simplify this process through structured control mappings and evidence recommendations.

## Project Objectives

- Map security requirements across NIST CSF 2.0, NIST SP 800-53 Rev 5, and SEBI CSCRF.
- Identify related controls across different frameworks.
- Determine regulatory applicability based on entity category.
- Explain the evidence auditors expect organizations to maintain.
- Support GRC analysts in preparing for cybersecurity audits.

## Target Users

GRC analysts and cybersecurity compliance teams at stockbroking organizations preparing for SEBI CSCRF audits while maintaining alignment with NIST cybersecurity frameworks.

## Key Features

1. **Framework Crosswalk:** Explore relationships between controls across three cybersecurity frameworks.
2. **Control Search:** Search for controls using framework identifiers.
3. **Applicability Assessment:** Identify requirements applicable to different SEBI entity categories.
4. **Evidence Recommendations:** Understand the documentation and evidence expected during audits.
5. **AI-Assisted Explanations:** Generate understandable explanations based on verified framework data.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend development |
| FastAPI | REST API development |
| uv | Python project and dependency management |
| Ruff | Code linting and formatting |
| Pre-commit | Automated code quality checks |
| Git | Version control |
| GitHub | Source code management |

## Data Sources

- NIST CSF 2.0
- NIST SP 800-53 Revision 5
- NIST OSCAL Content
- NIST CPRT/OLIR mappings
- SEBI CSCRF circular and applicable clarifications
- CERT-In Directions 2022

## Important Design Principle

Control mappings and regulatory applicability must be derived from structured, reviewed data sources.

The AI model must not independently invent control mappings or regulatory requirements.

Every applicability result must identify the relevant SEBI entity category.

## Project Structure

```text
controlmap/
│
├── app/
│   ├── api/
│   ├── core/
│   ├── data/
│   ├── models/
│   └── services/
│
├── docs/
├── tests/
├── pyproject.toml
└── README.md
```

## Project Status

Currently in the initial development and project setup phase.

## License

To be determined.
## User Persona

GRC analyst at a mid-size stockbroker in Chennai preparing for its first SEBI CSCRF audit while the parent group reports against NIST CSF.

## Hardest Technical Problem

Accurately mapping one CSCRF requirement to multiple NIST CSF 2.0 outcomes and NIST SP 800-53 Rev 5 controls.

The application must also determine applicability based on the organization's SEBI entity category.

All mappings must come from structured, reviewed data (OSCAL, CPRT/OLIR, and reviewed mapping tables). The LLM must never invent mappings or regulatory requirements.

## Data Sources

1. NIST CSF 2.0 Core and Informative References.
2. NIST SP 800-53 Rev 5 catalog in OSCAL JSON.
3. NIST CPRT/OLIR mappings.
4. SEBI CSCRF circular dated 20 August 2024, including applicable clarifications and extension circulars.
5. CERT-In Directions 2022.

## Target Evaluation Metrics

| Metric | Target |
|---|---|
| Crosswalk mapping agreement | 90% or higher across 60 controls |
| Entity-category applicability accuracy | 95% or higher across 40 questions |

These are project evaluation targets and must be validated through testing.

## Important Regulatory Disclaimer

ControlMap provides compliance mapping assistance and evidence recommendations. It does not guarantee regulatory compliance or predict audit outcomes. Final compliance decisions require verification against official regulatory documents and auditor assessment.