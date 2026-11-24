## D03 — PostgreSQL and Database Migrations

### Database Models
- Database models are maintained in `app/database/models.py`.
- Database configuration and connections are managed by the application database modules.

### Migrations
- Alembic migrations are maintained in `migrations/versions/`.
- Three migration files are present.
- Use Alembic to apply database schema changes consistently.

### Database Loader
- Loader script: `scripts/load_db.py`.
- Verify the loader against the configured database before recording successful execution.

### Verification
- Unit tests: `uv run pytest tests/unit -q`.
- The unit test suite passed four tests in the latest recorded run.
- Set `PYTHONPATH=.` in PowerShell before running tests if required by the current environment.

## D05 — CI/CD and Deployment

### Continuous Integration
- Workflow: `.github/workflows/ci.yml`.
- CI automates project quality checks and tests.

### Continuous Deployment
- Workflow: `.github/workflows/cd.yml`.
- Deployment is configured for the Render-hosted application.
- The `/health` endpoint is used to verify deployment health.

### Rollback and Roll-Forward
- The rollback and roll-forward drill is documented below.
- Application rollback was tested through the Render dashboard.
- Database rollback was not tested as part of this drill.

### Release
- Release tag: `week-1`.
- Verify the tag and deployed commit before submission.


## 11. Continuous Deployment (CD)

Configured GitHub Actions using `.github/workflows/cd.yml`.

Implemented:
- Deployment triggered after successful CI on `main`.
- Render deployment triggered through a GitHub Actions secret.
- Deployment verification using the `/health` endpoint.
- Verification that the deployed commit matches the expected commit.
- Automatic failure when deployment verification does not succeed.

### CD Verification

- Verified successful ControlMap CD workflow runs.
- Confirmed that the application starts successfully on Render.
- Verified the deployed commit through the health endpoint.

## 12. Branch Protection

- Configured protection for the `main` branch.
- Required changes to be submitted through pull requests.
- Configured required CI status checks before merging.

## 13. Live Deployment

- Application: https://prince28-sec10-controlmap.onrender.com
- Health endpoint: https://prince28-sec10-controlmap.onrender.com/health
- Readiness endpoint: https://prince28-sec10-controlmap.onrender.com/ready
- API documentation: https://prince28-sec10-controlmap.onrender.com/docs

Latest verified health response:

```json
{
  "status": "healthy",
  "version": "v1",
  "commit": "131da4f4af8a7d5d1ae16c688c3bee1fd569a4aa"
}
```

## 14. Rollback and Roll-Forward Drill

### Rollback

- Previous application commit: `8e58eff`.
- Trigger: Rollback through the Render dashboard.
- Result: Render reported `Deploy succeeded | Live`.
- Deployment duration: 15.8 seconds.
- Render recorded the deployment as rolled back by the user through the dashboard.

### Roll-Forward

- Restored application commit: `131da4f`.
- Trigger: Manual deployment through the Render dashboard.
- Result: Render reported `Deploy succeeded | Live`.
- Deployment duration: 24.6 seconds.
- Application startup completed successfully.

### Final Verification

The `/health` endpoint returned:

- Status: `healthy`
- Version: `v1`
- Commit: `131da4f4af8a7d5d1ae16c688c3bee1fd569a4aa`

The rollback and roll-forward drill was completed successfully.

Note: These timings represent the deployment durations reported by Render. The drill tested application-version rollback and restoration, not database rollback.

## 15. Nightly Health Check

Workflow file: `.github/workflows/nightly-health.yml`

The workflow is configured to run on a schedule and supports manual execution.

Verification evidence:
- Latest successful run: Record the actual GitHub Actions run and date.
- Health endpoint result: Record the result from the workflow logs.

## 16. Uptime Monitoring

- Configured an UptimeRobot monitor for the `/health` endpoint.
- Monitoring target: `https://prince28-sec10-controlmap.onrender.com/health`
- The monitor previously reported the endpoint as up.
- README monitoring badge configured.

Check the monitor dashboard for the latest status and uptime percentage before submitting the lab.

## 17. Secrets Management

- GitHub Actions deployment secret: `RENDER_DEPLOY_HOOK`.
- Stored in GitHub repository Actions secrets.
- Never commit deployment hooks, credentials, API keys, or other secret values to Git.
- Monitoring API keys should also remain private.

## 18. Database Migration Safety

Application rollback does not automatically reverse database schema changes.

To support safe deployments:
- Prefer backward-compatible database migrations.
- Avoid removing columns or tables while older application versions may still need them.
- Separate schema expansion from destructive cleanup.
- Back up important data before risky migrations.
- Test migrations and rollback compatibility before production changes.

The completed rollback drill verified application-version recovery; it did not independently verify database rollback.

## 19. Performance Improvement

Potential improvement:
- Add database connection pooling and tune pool size based on measured traffic.
- Monitor response latency and database connection usage before changing configuration.
- Measure performance before and after changes to confirm the benefit.

## 20. Release Tag

Tag: `week-1`

Before submission, verify that the tag points to the intended release commit and update it if the lab requires a different commit.

## 21. Final Verification Checklist

- [x] CI workflow configured and verified.
- [x] CD workflow configured and verified.
- [x] Application deployed on Render.
- [x] `/health` endpoint verified.
- [x] Rollback to `8e58eff` completed.
- [x] Roll-forward to `131da4f` completed.
- [x] Latest application commit verified.
- [x] README deployment and monitoring documentation merged.
- [ ] Nightly health-check run verified

## D06 — Document Collection Pipeline

### Implementation
- Added the asynchronous document fetcher under
  `src/controlmap/ingest/fetch.py`.
- Added `scripts/fetch.py` for URL lists, repositories, sitemaps,
  and manual collection workflows.
- Configured ten source URLs in `data/sources.csv`.
- Added fetcher unit tests and manifest-based download tracking.
- Added retries, concurrency limits, and content-type-aware
  file extension handling.

### Collection results
- The manifest records collected source files.
- The corpus includes NIST OSCAL JSON, NIST PDF publications,
  and SEBI CSCRF PDFs plus previously retained HTML landing pages.
- NIST documents are noted as public domain; SEBI reuse terms
  require verification.
- Generate dataset and capacity reports using
  `uv run python scripts/dataset_report.py`.
### Verification
- Fetcher unit tests: 23 passed in the latest targeted run.
- Full unit test suite: 27 passed in the latest run.
- Ruff lint: passed.
- The regression test `test_download_resumes_partial_file` verifies
  resumption of a partial download using an HTTP Range request.
- An isolated test confirmed the resumed response, final content,
  SHA-256 checksum, and temporary-file cleanup.
- Dataset report: 14 downloaded manifest records, 22.88 MB,
  and 750 readable PDF pages.

### Downloader Repeat-Run Test

**Test date:** 23 November 2026  
**Test environment:** Isolated temporary directory under the Windows temporary folder  
**Command:** `uv run --project . python "$testRoot\scripts\fetch.py" urls --delay 3`

| Run | Downloaded | Skipped | Blocked | Failed |
|---|---:|---:|---:|---:|
| First run | 10 | 0 | 0 | 0 |
| Second run | 0 | 10 | 0 | 0 |
| Third run | 0 | 10 | 0 | 0 |

**Result:** PASS. The first run downloaded all 10 configured sources. The second and third runs skipped all 10 previously downloaded files without downloading them again. No sources were blocked and no downloads failed.

**Scope limitation:** This test verifies that completed downloads are skipped on subsequent runs. It does not independently demonstrate recovery from an interruption during an active download.


### Isolated Downloader Resumability Test

**Date:** 23 November 2026

**Result:** PASS

An isolated test used a mocked HTTP transport and a temporary directory to verify downloader resumption without modifying the project dataset.

| Run | Downloaded | Skipped | Blocked | Failed |
|---|---:|---:|---:|---:|
| First run | 1 | 0 | 0 | 0 |
| Second run | 0 | 1 | 0 | 0 |

Two HTTP requests occurred during the first run: one for `robots.txt` and one for the document. The second run skipped the completed document without additional HTTP requests.

**Conclusion:** The isolated test verified partial-download resumption
using HTTP Range, correct final content, SHA-256 verification, and
temporary-file cleanup. The permanent regression test
`test_download_resumes_partial_file` also covers this behavior.

**Limitation:** The isolated test uses a mocked HTTP transport. It
does not establish recovery behavior for every real-world server.