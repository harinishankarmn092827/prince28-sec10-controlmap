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
## D07 — Document Parsing and Storage

### Implementation
- Added `src/controlmap/ingest/store.py` to store parsed documents and page metadata in the database.
- Added `scripts/parse_corpus.py` to parse supported documents from the collected corpus.
- Added `tests/unit/test_store.py` to test document storage, duplicate detection, and parse-failure tracking.
- Page metadata includes page numbers, heading paths, headings, and extracted tables.

### Corpus Parsing Verification
- Ran `scripts/parse_corpus.py --dry-run`.
- Documents discovered: 15.
- Successfully parsed: 15.
- Failed: 0.
- Database changes: None; this was a dry run.
- Supported formats in the corpus include PDF, JSON, and HTML.

### PDF Parser Comparison

**Method:** Compared PyMuPDF and pypdf on all six PDFs available in `data/raw` at the time of testing.

**Script:** `scripts/compare_parsers.py`

**Results:** `data/parser_comparison.csv`

| Metric | PyMuPDF | pypdf |
|---|---:|---:|
| PDFs tested | 6 | 6 |
| Total pages | 750 | 750 |
| Extracted characters | 2,875,078 | 2,097,499 |
| Empty pages | 0 | 0 |
| Total execution time | 15.7569 seconds | 40.3584 seconds |

**Findings**
- Both parsers successfully processed all six PDFs.
- Both reported the same total page count, with no empty pages.
- PyMuPDF extracted approximately 37.1% more characters than pypdf.
- PyMuPDF completed the comparison in approximately 61.0% less time.
- Character count and execution time are indicators, not proof of extraction accuracy.
- PyMuPDF remains the primary parser because it performed better in this initial comparison and also supports the existing heading and table extraction logic.

**Scope limitation:** Six PDFs were available. The comparison does not satisfy a requirement to test ten PDFs. Additional PDFs must be obtained before claiming a ten-PDF comparison.

### Automated Verification
- Unit tests: 38 passed.
- Ruff lint: passed.
- Ruff formatting check: passed for `scripts/parse_corpus.py`, `src/controlmap/ingest/store.py`, and `tests/unit/test_store.py`.
- Pre-commit checks passed when committing the parsing and storage implementation.

### Outstanding Work
### Database and Metadata Validation

- The configured Neon database contains 37 documents and 1,936 pages.
- A corpus parsing dry run discovered 15 documents, parsed all 15 successfully, and reported zero failures.
- Subsequent corpus runs skipped the 15 documents as duplicates.
- Database metadata inspection found that heading and table metadata are not consistently populated.
- Compared local corpus files with database records using SHA-256 hashes. Fifteen documents matched.
- A read-only alignment check found substantial text differences between the current parser output and existing database pages. Bulk metadata backfill is deferred until these differences are understood.
- PDF parser comparison covered six PDFs, not the target of ten. This limitation remains documented.
- No bulk metadata backfill has been performed.
- Further work: investigate extraction differences, validate metadata quality, and expand the parser comparison to ten PDFs if additional suitable documents become available.

## D08 — LLM Gateway Verification

### Automated verification

- Unit tests: 58 passed.
- Ruff linting: passed (`uv run ruff check .`).
- Gateway tests cover primary-provider generation, retries, exponential backoff with jitter, provider fallback, circuit-breaker behavior, streaming, and token-usage capture.

### Live deployment verification

- Live `/health` endpoint previously returned a healthy status.
- `/v1/chat` returned a streamed AI response.
- The stream included request metadata and terminated with `event: done`.
- `/v1/usage` reflected one additional successful request.
- Usage deltas observed: 446 prompt tokens, 70 completion tokens, and 516 total tokens.
- Estimated cost increased by ₹0.005173.
- The fallback counter increased by one.

### Outstanding verification

- Confirm the actual primary and fallback providers from provider-level logs.
- Verify retry and circuit-breaker behavior with targeted experiments.
- Confirm the official D08 lab evaluator status.

### Notes

- Live usage values are observations from the test request, not permanent totals.
- The aggregate fallback counter alone does not prove which providers handled the request.
- Automated unit tests passing does not replace the remaining live experiments.
## D09 - Versioned Prompts and Question Classification

### Prompt evaluation

- Test set: `eval/prompt_testset.jsonl`.
- Total labelled questions: 20.
- Label distribution: 10 docs, 5 personal, and 5 off_topic.
- Evaluation script: `scripts/compare_prompts.py`.
- Results report: `eval/prompt_comparison.json`.
- Responses are cached under `eval/cache/` to avoid unnecessary repeated API calls.

| Prompt version | Correct | Total | Accuracy | Errors |
|---|---:|---:|---:|---:|
| classify_v1 | 20 | 20 | 100.0% | 0 |
| classify_v2 | 20 | 20 | 100.0% | 0 |
| classify_v3 | 20 | 20 | 100.0% | 0 |
| classify_v4 | 20 | 20 | 100.0% | 0 |

### Findings and limitations

- All four versions achieved 20/20 on the current test set.
- The versions have identical measured accuracy on these 20 questions. The results do not establish that a newer version generalizes better to unseen questions.
- Later prompt versions refine classification guidance, ambiguity handling, and resistance to prompt injection.
- Structured JSON output is requested, and classification responses are validated before being returned.
- The test set is small. Further evaluation with unseen questions and adversarial examples is needed before making broader accuracy claims.

### Implementation

- Added a versioned prompt loader in `src/controlmap/llm/prompts.py`.
- Added the question classifier in `src/controlmap/llm/classify.py`.
- Added four classifier prompts under `prompts/`.
- Added labelled evaluation data and a comparison script.
- Added classifier unit tests and structured-response-format gateway coverage.

### Verification

- Evaluated classifier versions 1 through 4 using `scripts/compare_prompts.py --versions 1 2 3 4`.
- Confirmed that `eval/prompt_comparison.json` contains versions 1, 2, 3, and 4.
- Each version scored 20/20 with zero errors in the recorded run.
- Implemented document-metadata extraction and source-document API filters; endpoint registration and all seven query parameters verified through OpenAPI.
### Metadata Extraction

#### Implementation
- Added versioned metadata extraction using `prompts/extract_v1.md`.
- Added a Pydantic validation contract in `src/controlmap/llm/doc_meta.py`.
- Added a resumable extraction script at `scripts/extract_metadata.py`.
- Extraction results are stored under `metadata._metadata_extraction`.
- Previously successful documents are skipped on subsequent runs. The `--retry-failed` option allows failed documents to be attempted again.
- Document text is treated as untrusted input, and the extraction prompt instructs the model not to follow instructions embedded in source documents.

#### Extraction Results

- Starting corpus: 17 eligible source documents.
- Initial extraction: 13 succeeded and 4 failed.
- First retry: 1 additional document succeeded and 3 remained failed.
- Subsequent retry runs successfully extracted documents 34 (NIST SP 800-53 Revision 5) and 37 (SEBI CSCRF Technical Clarifications August 2025).
- Latest observed status: 16 successful documents and 1 failed document out of 17 eligible documents.
- Remaining failure: document 35, SEBI CSCRF Circular August 2024. Gemini returned a rate-limit error and Groq returned an API status error.
- Extraction commits results per document. Previously successful documents are skipped, and `--retry-failed` retries unsuccessful documents.
- All 17 eligible documents have been attempted, but one still needs a successful extraction.

#### Limitations and Follow-up

- Retry document 35 after provider availability and rate limits have recovered.
- The exact extraction cost and per-document cost have not been verified. Do not report an amount without reliable usage or billing data.
- Five SEBI records were manually compared against their source PDFs; see the Manual metadata verification section below.
- Schema validation does not guarantee factual correctness. Language labels and malformed characters in some summaries still need review.

### D09 Required Reflection

#### Prompt comparison

- Best measured classifier prompts: `classify_v1`, `classify_v2`, `classify_v3`, and `classify_v4`, each scoring 20/20 (100%) on the current test set.
- V4 changes: the versioned prompts refine classification guidance, ambiguity handling, and resistance to prompt injection. V4 did not improve the measured score because all four versions scored 20/20.
- Hardest incorrect question: none was recorded in the current 20-question evaluation because all four versions answered every labelled question correctly. This does not establish performance on unseen questions.
- Test-set label changes after evaluation: not recorded; do not claim a label was changed unless the evaluation history confirms it.
- Input tokens per question: not recorded in the prompt comparison results. Measure token usage before comparing the cost of the prompt versions.

#### DocMeta contract

- Validation contract: `src/controlmap/llm/doc_meta.py`.
- Extraction prompt: `prompts/extract_v1.md`.
- The contract validates structured metadata. Review the project-specific fields against the actual source-document use case; valid output is not proof of factual accuracy.

#### Extraction run

- Prompt version: `extract_v1`.
- Latest observed result: 16 successful, 1 failed, out of 17 eligible source documents.
- Remaining failure: document 35, SEBI CSCRF Circular August 2024.
- Most recent failure reason: Gemini rate limiting and a Groq API status error. Retry after provider availability recovers.
- Extraction cost: not verified. Obtain reliable usage or billing information before recording a rupee amount.
- A valid-but-wrong metadata example should be documented only after comparing a specific extracted field against its source. See the data-quality observations and manual verification section for findings already identified.

#### One thing that went wrong and how it was fixed

- The extraction run encountered provider errors while processing document 35. The script retained successful per-document results, and the `--retry-failed` option allowed unsuccessful documents to be retried without reprocessing previously successful documents.
- The remaining document still needs a successful retry; the extraction task is not yet fully complete.

### Live API Verification

Verified against the deployed service at `https://prince28-sec10-controlmap.onrender.com` on 26 November 2026.

- `/health` returned `status=healthy`, version `v1`, and commit `27653a22197ebcc945a47bdaa95404fc913c2b1f`.
- `/v1/source-documents?language=English` returned 11 records.
- `/v1/source-documents?doc_kind=circular` returned 6 records.
- `/v1/source-documents?framework=CSCRF` returned 6 records.
- `/v1/usage` returned aggregate request, token, cost, and fallback statistics.
- `/v1/documents` returned the existing control-record dataset; its response did not demonstrate filtering by the extracted `doc_kind` metadata. The source-document endpoint is the appropriate endpoint for validating extracted metadata filters.

#### Data-quality observations
- Records 33 and 36 were labelled `Hindi`, although their summaries appeared to describe English circulars. Verify against the original source documents before correcting them.
- Some summaries displayed malformed characters, including `â¯` and `â€™`. Investigate text encoding before performing a bulk correction.
- Successful API responses and schema validation do not independently establish the factual accuracy of extracted metadata.
### Manual metadata verification

On 2026-11-26, five extracted SEBI CSCRF source-document records were compared against their locally downloaded PDFs.

| Record ID | Source document | Verified source date | Additional finding |
|---|---|---|---|
| 28 | SEBI CSCRF Circular August 2024 | 2024-08-20 | Source circular identifier is `SEBI/HO/ITD-1/ITD_CSC_EXT/P/CIR/2024/113`. |
| 30 | SEBI CSCRF Clarifications December 2024 | 2024-12-31 | Source circular identifier is `SEBI/HO/ITD-1/ITD_CSC_EXT/P/CIR/2024/184`. |
| 31 | SEBI CSCRF Clarifications April 2025 | 2025-04-30 | Source circular identifier is `SEBI/HO/ITD-1/ITD_CSC_EXT/P/CIR/2025/60`. |
| 32 | SEBI CSCRF Technical Clarifications August 2025 | 2025-08-28 | Source circular identifier is `SEBI/HO/ITD-1/ITD_CSC_EXT/P/CIR/2025/119`. |
| 33 | `1735646756843-b5a27629686d.pdf` | 2024-12-31 | The source explicitly mentions Data Localisation and the Data Security standard `PR.DS.S2`, supporting the extracted control ID. |

**Review observations:**
- The five source dates match the dates extracted into metadata.
- Record 33's `control_id` value, `PR.DS.S2`, is supported by the source PDF.
- Hindi and English text both appear in the first pages of some PDFs. The intended meaning of the `language` field should be applied consistently; bilingual content alone does not establish an incorrect classification.
- Some extracted summaries contain visibly corrupted character sequences, such as `â¯` and `â€™`. These require further investigation before any correction is made.
- This review verified source dates and the control ID noted above. It does not establish that every metadata field or every generated summary is fully accurate.

### Production Verification

**Production URL:** https://prince28-sec10-controlmap.onrender.com

**Live health check**
- Status: `healthy`
- API version: `v1`
- Deployed commit: `0a07649743738cdf3228b94276e8ce607f44aa95`
- The deployed commit matches the merged D09 extraction error-handling fix in PR #31.

**Source-document API checks**
- `/v1/source-documents`: 16 records returned.
- `/v1/source-documents?language=English`: 13 records returned.
- `/v1/source-documents?doc_kind=profile`: 3 records returned.
- `/v1/usage`: endpoint returned aggregate usage metrics.

**Observed aggregate usage**
- Requests: 6 total; 4 successful; 2 failed.
- Tokens: 682 prompt + 470 completion = 1,152 total.
- Estimated cost: ₹0.011429.
- Fallback requests: 2.

**Metadata extraction status**
- Successful: 16 documents.
- Failed: 1 document.
- Remaining failure: document 35, SEBI CSCRF Circular August 2024.
- Failure reason: Gemini rate limit and Groq API error.
- The error-handling fix prevents the ORM rollback error, but the external provider failure remains unresolved.