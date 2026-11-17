# ControlMap – Software Requirements Specification

## 1. Introduction

ControlMap is a cybersecurity framework crosswalk and audit evidence mapping application designed to assist GRC analysts in identifying relationships between NIST CSF 2.0, NIST SP 800-53 Revision 5, and SEBI CSCRF requirements.

This document defines the functional and non-functional requirements of the application.

## 2. Functional Requirements

### FR-01: Framework Control Search
The system shall allow users to search for cybersecurity controls using framework names, control identifiers, and keywords across the supported frameworks.

### FR-02: Cross-Framework Mapping
The system shall display related controls across NIST CSF 2.0, NIST SP 800-53 Rev 5, and SEBI CSCRF using reviewed and structured mapping data.

### FR-03: Entity Category Applicability
The system shall identify whether a CSCRF requirement applies to a selected SEBI entity category, including Mid-size and Qualified RE categories.

### FR-04: Audit Evidence Recommendations
The system shall provide relevant audit evidence recommendations for selected cybersecurity requirements, including supporting documents and expected records.

### FR-05: AI-Assisted Explanations
The system shall generate understandable explanations for framework requirements using verified source data and must clearly identify unsupported questions.

## 3. Non-Functional Requirements

### NFR-01: Response Latency
The system shall return standard control search and crosswalk API responses within 2 seconds at the 95th percentile (p95), excluding external LLM generation time.

### NFR-02: Mapping Accuracy
The system shall achieve at least 90% agreement with reviewed mappings across a test set of 60 controls.

### NFR-03: Applicability Accuracy
The system shall achieve at least 95% correctness across a test set of 40 entity-category applicability questions.

### NFR-04: Cost Efficiency
The average LLM processing cost shall not exceed $0.02 per answered question under the defined evaluation workload.

### NFR-05: Security and Reliability
The system shall protect API credentials using environment variables, prevent secrets from entering Git history, and validate user inputs before processing requests.

## 4. Performance Evaluation Metrics

| Metric | Target |
|---|---|
| Crosswalk mapping agreement | 90% or higher across 60 controls |
| Entity applicability accuracy | 95% or higher across 40 questions |
| API p95 latency | ≤ 2 seconds |
| Average LLM cost per question | ≤ $0.02 |
| Functional requirements | 5 |
| Non-functional requirements | 5 |

## 5. Constraints

- Framework mappings must originate from structured, reviewed sources.
- AI-generated mappings must not be treated as authoritative.
- Entity category must be specified when presenting CSCRF applicability.
- The application must not guarantee audit outcomes.
- Regulatory references must include relevant control identifiers and circular dates.

## 6. Acceptance Criteria

The initial version of ControlMap will be considered ready for evaluation when:

1. Users can search supported framework controls.
2. The system can display reviewed cross-framework mappings.
3. Entity category applicability can be identified.
4. Audit evidence recommendations can be displayed.
5. AI explanations are grounded in verified information.
6. Unanswerable questions are handled safely.
7. The defined accuracy and performance targets can be evaluated through tests.