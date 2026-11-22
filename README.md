# ControlMap

[![CI](https://github.com/harinishankarmn092827/prince28-sec10-controlmap/actions/workflows/ci.yml/badge.svg)](https://github.com/harinishankarmn092827/prince28-sec10-controlmap/actions/workflows/ci.yml)
[![Live](https://img.shields.io/website?url=https%3A%2F%2Fprince28-sec10-controlmap.onrender.com%2Fhealth&label=live)](https://prince28-sec10-controlmap.onrender.com/docs)
[![Uptime](https://img.shields.io/uptimerobot/ratio/m804745569-5afadedf178a16459ccbd318?label=uptime)](https://uptimerobot.com/)

**Status:** Week 1 complete · Live deployment available.

**Live API:** https://prince28-sec10-controlmap.onrender.com

**Documentation:** [Swagger UI](https://prince28-sec10-controlmap.onrender.com/docs) · [Health Check](https://prince28-sec10-controlmap.onrender.com/health) · [Readiness Check](https://prince28-sec10-controlmap.onrender.com/ready)

**Repository:** [GitHub](https://github.com/harinishankarmn092827/prince28-sec10-controlmap)

---

## Cybersecurity Framework Crosswalk and Audit Evidence Mapping

ControlMap is a cybersecurity compliance mapping application designed to help Governance, Risk, and Compliance (GRC) analysts understand and map security controls across multiple cybersecurity frameworks.

## Problem Statement

Organizations must comply with multiple cybersecurity frameworks, including NIST Cybersecurity Framework (CSF) 2.0, NIST SP 800-53 Revision 5, and SEBI's Cybersecurity and Cyber Resilience Framework (CSCRF).

These frameworks describe similar security concepts using different terminology and control structures. Organizations often perform cross-framework mapping manually using spreadsheets, which can lead to inconsistencies, missed requirements, and incorrect applicability assessments.

ControlMap aims to simplify this process through structured control mappings and evidence recommendations.

## Project Objectives

- Map security requirements across NIST CSF 2.0, NIST SP 800-53 Rev. 5, and SEBI CSCRF.
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
5. **AI-Assisted Explanations:** Planned capability for explanations grounded in verified framework data.

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
| GitHub Actions | CI/CD automation |
| Render | Application hosting |
| UptimeRobot | Uptime monitoring |

## Run locally in one command

ControlMap uses Docker Compose to start the API, PostgreSQL database, Redis, and database migrations.

### Prerequisites
- Docker Desktop
- Python and `uv` for local development

### Start the application

From the project root, run:

```bash
docker compose up --build
```

Once the containers are healthy, open:
- API: http://localhost:8000
- Swagger API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health

To stop the services, press `Ctrl+C` and run:

```bash
docker compose down
```

To stop the services and remove the database and Redis volumes as well, run:

```bash
docker compose down -v
```

**Warning:** The `-v` option deletes the persisted database and Redis data.

## Architecture

ControlMap uses a containerized backend architecture.

- **API:** FastAPI application.
- **Database:** PostgreSQL for storing documents and control records.
- **Cache:** Redis service.
- **Migrations:** Alembic for database schema management.
- **Testing:** Unit and PostgreSQL integration tests.
- **Continuous Integration:** GitHub Actions for automated linting, testing, and Docker image builds.
- **Continuous Deployment:** GitHub Actions and the configured Render deployment hook.
- **Monitoring:** UptimeRobot monitors the public health endpoint.

## Live Deployment

The application is deployed on Render.

| Resource | URL |
|---|---|
| Live API | https://prince28-sec10-controlmap.onrender.com |
| Swagger UI | https://prince28-sec10-controlmap.onrender.com/docs |
| Health Check | https://prince28-sec10-controlmap.onrender.com/health |
| Readiness Check | https://prince28-sec10-controlmap.onrender.com/ready |
| GitHub Repository | https://github.com/harinishankarmn092827/prince28-sec10-controlmap |
| GitHub Actions | https://github.com/harinishankarmn092827/prince28-sec10-controlmap/actions |

### Health Check

The `/health` endpoint reports the application's health and deployment information.

Example response:

```json
{
  "status": "healthy",
  "version": "v1",
  "commit": "<deployed-commit-sha>"
}
```

The actual response depends on the currently deployed version and commit.

### Uptime Monitoring

UptimeRobot monitors the following endpoint:

`https://prince28-sec10-controlmap.onrender.com/health`

- **Monitor type:** HTTP/S
- **Check interval:** Every 5 minutes
- **Purpose:** Detect service availability problems and monitor uptime.

The monitor has previously reported an **Up** status. Uptime percentages and incident history change over time and should be verified in the UptimeRobot dashboard.

## Run Locally Using Docker

### Prerequisites

- Docker Desktop
- Git

### Clone the Repository

```bash
git clone https://github.com/harinishankarmn092827/prince28-sec10-controlmap.git
cd prince28-sec10-controlmap
```

### Start the Application

```bash
docker compose up --build -d
```

Docker Compose starts the services configured in the project, including the API, PostgreSQL, and Redis where configured.

### Access the Application

| Resource | URL |
|---|---|
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |
| Readiness Check | http://localhost:8000/ready |

### Check Container Status

```bash
docker compose ps
```

### View API Logs

```bash
docker compose logs -f api
```

### Stop the Application

```bash
docker compose down
```

To remove containers and their persistent database/cache volumes:

```bash
docker compose down -v
```

**Warning:** The `-v` option deletes the associated local database and cache volumes. Use it only if you intend to remove that local data.

## Running Tests

Install development dependencies:

```bash
uv sync --dev
```

### Run Unit Tests

```bash
uv run python -m pytest tests/unit -v
```

### Run Integration Tests

Configure the isolated PostgreSQL test database using `TEST_DATABASE_URL` before executing integration tests.

```bash
uv run python -m pytest tests/integration -v
```

### Run All Tests

```bash
uv run python -m pytest -v
```

### Generate a Coverage Report

```bash
uv run python -m pytest tests/unit --cov=app --cov=scripts --cov-report=term-missing --cov-report=html
```

The HTML coverage report is generated at:

```text
htmlcov/index.html
```

## CI/CD Pipeline

ControlMap uses GitHub Actions to automate code validation, container image building, and deployment.

### Continuous Integration

The CI workflow is defined in:

`.github/workflows/ci.yml`

Its configured jobs include:

- Code linting and formatting checks.
- Automated tests using PostgreSQL.
- Docker image building and publishing to GitHub Container Registry (GHCR), according to workflow conditions.

### Continuous Deployment

The CD workflow is defined in:

`.github/workflows/cd.yml`

It is configured to initiate deployment after a successful CI run on the main branch and verify the deployed service using health checks.

### Nightly Health Check

The nightly workflow is defined in:

`.github/workflows/nightly-health.yml`

It is configured to run a scheduled health check and supports manual execution if configured in the workflow.

### Branch Protection

The main branch is protected using repository rules that require pull requests and the configured CI status checks before merging.

### View Workflow Runs

[ControlMap GitHub Actions](https://github.com/harinishankarmn092827/prince28-sec10-controlmap/actions)

## Data Sources

The project references the following cybersecurity and regulatory sources:

- NIST Cybersecurity Framework (CSF) 2.0.
- NIST SP 800-53 Revision 5.
- NIST OSCAL content.
- NIST CPRT/OLIR mappings.
- SEBI CSCRF circulars and applicable clarifications.
- CERT-In Directions 2022.

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
|-- .github/
|   |-- workflows/
|       |-- ci.yml
|       |-- cd.yml
|       |-- nightly-health.yml
|
|-- Dockerfile
|-- docker-compose.yml
|-- alembic.ini
|-- pyproject.toml
|-- uv.lock
|-- README.md
```

## Project Status

The backend foundation includes:

- FastAPI application and API endpoints.
- PostgreSQL database integration.
- Database models and Alembic migrations.
- Document loading and control record importing.
- Framework and category-based document filtering.
- Dockerized API, PostgreSQL, and Redis services.
- Unit and integration test organization.
- Automated test coverage reporting.
- GitHub Actions CI/CD workflows.
- Live deployment with health and readiness endpoints.
- UptimeRobot monitoring configuration.

Further development will expand framework crosswalk accuracy, evidence recommendations, and AI-assisted explanations.

## User Persona

A GRC analyst at a mid-size stockbroker in Chennai preparing for its first SEBI CSCRF audit while the parent group reports against NIST CSF.

## Hardest Technical Problem

Accurately mapping one CSCRF requirement to multiple NIST CSF 2.0 outcomes and NIST SP 800-53 Revision 5 controls.

The application must also determine applicability based on the organization's SEBI entity category.

All mappings must come from structured, reviewed data, such as OSCAL, CPRT/OLIR, and reviewed mapping tables. The LLM must never invent mappings or regulatory requirements.

## Target Evaluation Metrics

| Metric | Target |
|---|---|
| Crosswalk mapping agreement | 90% or higher across 60 controls |
| Entity-category applicability accuracy | 95% or higher across 40 questions |

These are project evaluation targets, not confirmed results. They must be validated through testing before being reported as achieved metrics.

## Important Regulatory Disclaimer

ControlMap provides compliance mapping assistance and evidence recommendations. It does not guarantee regulatory compliance or predict audit outcomes.

Final compliance decisions require verification against official regulatory documents and auditor assessment.

## License

To be determined.