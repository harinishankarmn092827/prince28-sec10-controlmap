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

1. **Framework Crosswalk:** Explore relationships between controls across multiple frameworks.
2. **Control Search:** Search for controls using framework identifiers.
3. **Applicability Assessment:** Identify requirements applicable to different SEBI entity categories.
4. **Evidence Recommendations:** Understand the documentation and evidence expected during audits.
5. **AI-Assisted Explanations:** Planned capability for understandable explanations grounded in verified framework data.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.13 | Backend development |
| FastAPI | REST API development |
| SQLAlchemy | Database ORM |
| PostgreSQL | Relational database |
| Alembic | Database migrations |
| Redis | Caching infrastructure |
| Docker | Containerization |
| Docker Compose | Multi-container orchestration |
| uv | Python dependency management |
| pytest | Automated testing |
| pytest-cov | Test coverage reporting |
| Ruff | Code linting and formatting |
| Pre-commit | Automated code quality checks |
| Git | Version control |
| GitHub | Source code management |

## Architecture

ControlMap uses a containerized backend architecture:

- **API:** FastAPI application.
- **Database:** PostgreSQL for storing documents and control records.
- **Cache:** Redis service.
- **Migrations:** Alembic for database schema management.
- **Testing:** Separate unit and PostgreSQL integration tests.

## Run Locally Using Docker

### Prerequisites

- Docker Desktop
- Git

### Start the application

Clone the repository:

```bash
git clone https://github.com/harinishankarmn092827/prince28-sec10-controlmap.git
cd prince28-sec10-controlmap
```

Start the application:

```bash
docker compose up --build -d
```

Docker Compose starts:

- FastAPI application
- PostgreSQL database
- Redis cache

Database migrations are applied automatically during API startup.

### Access the application

| Resource | URL |
|---|---|
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |
| Readiness Check | http://localhost:8000/ready |

### Check container status

```bash
docker compose ps
```

### View application logs

```bash
docker compose logs -f api
```

### Stop the application

```bash
docker compose down
```

To remove containers and their persistent database/cache volumes:

```bash
docker compose down -v
```

**Warning:** The `-v` option deletes the local PostgreSQL and Redis data volumes.

## Running Tests

Install development dependencies:

```bash
uv sync --dev
```

Run unit tests:

```bash
uv run python -m pytest tests/unit -v
```

Run integration tests:

Configure the isolated PostgreSQL test database using `TEST_DATABASE_URL` before executing integration tests.

Run:

```bash
uv run python -m pytest tests/integration -v
```

Run all tests:

```bash
uv run python -m pytest -v
```

Generate a coverage report:

```bash
uv run python -m pytest tests/unit --cov=app --cov=scripts --cov-report=term-missing --cov-report=html
```

The HTML coverage report is generated in:

```text
htmlcov/index.html
```

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
prince28-sec10-controlmap/
|
|-- app/
|   |-- api/
|   |-- core/
|   |-- data/
|   |-- database/
|   |-- models/
|   |-- services/
|
|-- docs/
|-- migrations/
|   |-- versions/
|
|-- scripts/
|-- tests/
|   |-- integration/
|   |-- unit/
|
|-- Dockerfile
|-- docker-compose.yml
|-- alembic.ini
|-- pyproject.toml
|-- uv.lock
|-- README.md
```

## Project Status

The backend foundation is implemented, including:

- FastAPI application and API endpoints.
- PostgreSQL database integration.
- Database models and Alembic migrations.
- Document loading and control record importing.
- Framework and category-based document filtering.
- Dockerized API, PostgreSQL and Redis services.
- Unit and integration test organization.
- Automated test coverage reporting.

Further development will expand framework crosswalk accuracy, evidence recommendations, and AI-assisted explanations.

## User Persona

GRC analyst at a mid-size stockbroker in Chennai preparing for its first SEBI CSCRF audit while the parent group reports against NIST CSF.

## Hardest Technical Problem

Accurately mapping one CSCRF requirement to multiple NIST CSF 2.0 outcomes and NIST SP 800-53 Rev 5 controls.

The application must also determine applicability based on the organization's SEBI entity category.

All mappings must come from structured, reviewed data (OSCAL, CPRT/OLIR, and reviewed mapping tables). The LLM must never invent mappings or regulatory requirements.

## Target Evaluation Metrics

| Metric | Target |
|---|---|
| Crosswalk mapping agreement | 90% or higher across 60 controls |
| Entity-category applicability accuracy | 95% or higher across 40 questions |

These are project evaluation targets and must be validated through testing.

## Important Regulatory Disclaimer

ControlMap provides compliance mapping assistance and evidence recommendations. It does not guarantee regulatory compliance or predict audit outcomes. Final compliance decisions require verification against official regulatory documents and auditor assessment.

## License

To be determined.