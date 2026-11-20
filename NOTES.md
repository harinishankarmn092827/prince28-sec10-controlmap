# Day 4 & Day 5 – Docker, Testing, CI/CD, and Deployment

## 1. Docker Implementation

- Created a multi-stage `Dockerfile`.
- Used Python 3.13 slim as the base image.
- Installed dependencies using `uv`.
- Configured a non-root application user.
- Added a `.dockerignore` file to reduce the Docker build context.

## 2. Docker Compose

Configured the following services:

- PostgreSQL with pgvector.
- Redis for caching.
- Migration service for Alembic migrations and control record imports.
- FastAPI application service.

Additional configurations:

- Configured service health checks.
- Set up service dependencies.
- Organized the application services using Docker Compose.

## 3. Database Migrations

- Configured Alembic database migrations.
- Added a separate test database.
- Implemented temporary PostgreSQL databases for integration tests.
- Applied actual Alembic migrations during integration test setup.
- Added database cleanup after tests.

## 4. Testing Results

| Test Type | Tests Passed |
|---|---:|
| Unit tests | 4 |
| Integration tests | 14 |
| **Total** | **18** |

All 18 tests passed during the recorded test run.

## 5. Coverage Results

| Coverage Type | Coverage |
|---|---:|
| Unit tests | 54% |
| Unit and integration tests | 72% |

Generated an HTML coverage report in the `htmlcov/` directory.

## 6. Poe Tasks

Configured the following tasks in `pyproject.toml`:

- `dev`
- `lint`
- `test`
- `test-integration`
- `cov`
- `migrate`
- `seed`

These tasks simplify common development, testing, and database operations.

## 7. Makefile

- Added Makefile targets for common development tasks.
- Simplified execution of development and testing commands.

## 8. API Verification

- Verified the `/health` endpoint.
- Verified the `/ready` endpoint with the database running.
- Verified that `/ready` returns HTTP 503 when PostgreSQL is unavailable.
- Verified API container health.

## 9. Warnings

- The recorded test run reported a Starlette deprecation warning related to HTTPX.
- All 18 tests passed during that test run.

---

# Day 5 – CI/CD Implementation

## 10. Continuous Integration (CI)

Configured GitHub Actions using:

`.github/workflows/ci.yml`

Implemented the following:

- Automated linting and code-quality checks.
- Automated unit and integration testing.
- PostgreSQL service configuration for integration tests.
- Docker image build and publishing workflow.
- Deployed API smoke testing.
- Automated workflow execution for relevant GitHub events.

### CI Verification

- Verified successful `ControlMap CI` workflow runs.
- Confirmed that the CI workflow completed successfully after merging the Day 5 changes.

## 11. Continuous Deployment (CD)

Configured GitHub Actions using:

`.github/workflows/cd.yml`

Implemented the following:

- Configured deployment after a successful CI workflow on the `main