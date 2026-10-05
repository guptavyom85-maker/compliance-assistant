# Compliance Assistant

Django application for source-grounded PDF questions, bounded multi-document research, reviewed obligation extraction and policy gap reports. Phases 0–3 software workflows are implemented; live answer-quality and production acceptance remain pending. The active 15-question gold set was supplied as human-reviewed on 5 October 2026.

## Local setup (PowerShell)

Use the existing environment if already configured:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py bootstrap_roles
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

For a new checkout, create a Python 3.12 virtual environment first. Copy `.env.example` to `.env` and supply the OpenRouter API key and available model names. Never commit secrets. Normal unit tests use mocked providers and do not need API credentials.

`bootstrap_roles` creates groups; it does not automatically assign or elevate existing users. Use a superuser's Django admin to assign Viewer, Contributor or Admin. The application Admin group can use the evaluation/review screens without being Django staff. Grant staff status separately only when Django-admin access is intended.

## Corpus operations

Upload a text PDF at Documents → Upload. Set its type/category accurately, and set printed-page offset where needed. A policy must have no regulator. Indexing is synchronous; keep the tab open and allow completion.

```powershell
.\.venv\Scripts\python.exe manage.py rebuild_vector_index
.\.venv\Scripts\python.exe manage.py check_vector_index
```

Rebuilds create immutable generation directories and activate one with `CURRENT`. Older generations and the legacy index files are retained. No pickle is loaded. The database and filesystem are not one transaction: after a changed corpus and failed rebuild, the previous generation remains on disk but queries reject it as stale until a successful rebuild.

Document removal retains uploaded bytes for recovery. No automated retention cleanup is implemented. Backups include potentially private content and should remain outside source control.

## Questions and evidence

Ask questions through the application. First select one to ten indexed reference documents; retrieval, agent tools and citations are restricted to those sources. Then choose dense, hybrid (BM25 + dense), or hybrid with cross-encoder reranking, and automatic, direct or agent strategy. Claims cite database-derived source metadata. Semantic validation may report supported, partial, unsupported, contradicted or unavailable. Qualitative confidence bands are not calibrated probabilities. Automated support checks do not establish legal correctness.

Agent execution uses a bounded evidence plan and records tool actions, results and errors on the answer detail page. Dated version comparisons require two dated documents in the same version family. Model loading and synchronous processing can make requests slow; agent timeouts may yield an explicit incomplete/abstaining result.

## Obligations and policy gap reports

Contributors can extract obligations from indexed, in-force binding regulations, master directions or circulars. Reports and draft consultations are ineligible. Extraction is resumable; a candidate is not usable for gap analysis until a human confirms it and its source support is valid.

Upload/index a company policy with no regulator, extract and review duties from the applicable binding sources, then use Gap analysis to select the policy and regulations. Findings distinguish addressed, partial, not addressed, conflicting and needs review. Inspect evidence, record human review and download the PDF. Missing citations or failed model checks remain visible; reports are not compliance certification.

```powershell
.\.venv\Scripts\python.exe manage.py extract_obligations --document-id 3 --limit 10
```

Replace the example ID with an actual eligible document ID. The supplied consultation/report alone cannot demonstrate a real policy gap assessment.

Administrators have a unified Review queue and date-filtered Analytics page. Human review records identity, timestamp and notes. The Trust page describes source authority, provider processing and limitations.

Question histories belong to the asking user; users with global-log permission can inspect all histories. PDFs are served through authenticated routes. This remains a single shared-corpus application, without organization-specific document permissions.

## Human-reviewed evaluation

Open Evaluation, choose a gold question, inspect the reference answer and source excerpts, edit if needed, and explicitly confirm the review. Normal evaluation blocks unreviewed references; the explicit provisional option permits draft experiments without approving them. Evidence must still resolve.

For this repository's two supplied PDFs, source-aligned drafts can be prepared idempotently:

```powershell
.\.venv\Scripts\python.exe manage.py prepare_corpus_gold
.\.venv\Scripts\python.exe manage.py check_foundation_gate
.\.venv\Scripts\python.exe manage.py run_rag_evaluation --label dense-baseline --split test
```

The preparation command is corpus-specific and refuses to invent missing evidence. It retains historical questions/results. Review is required before accepted quality claims. Ten small questions are a smoke benchmark, not evidence of broad regulatory reliability. To repeat the explicitly provisional retrieval comparison without answer-provider calls:

```powershell
.\.venv\Scripts\python.exe manage.py compare_retrieval --allow-unreviewed --split test
```

Embedding/reranker models may download on first use. Timings include model initialization and are not a controlled warm-latency benchmark. In Evaluation, administrators can label generated answer correctness and record human/judge agreement; no labels are fabricated.

Metrics are shown separately as fractions from 0 to 1, with errors and judgment coverage. Cost remains unknown when trustworthy pricing/usage accounting is unavailable.

## Validation

```powershell
.\.venv\Scripts\python.exe manage.py test tests
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Tests create an isolated database and temporary media/index directories. They do not alter real uploads or index data. Provider mocks test orchestration and failure handling, not actual model accuracy or resistance to prompt injection.

## Deployment

Set `DEBUG=False`, a strong `DJANGO_SECRET_KEY`, explicit `ALLOWED_HOSTS`, HTTPS redirect, secure cookies and appropriate HSTS values. Enable the proxy SSL header only behind a trusted proxy that strips client-supplied forwarding headers. Configure the web server so `media/` is not publicly served.

Run `manage.py check --deploy` under those settings. A passing Django check does not replace deployment review, request-size limits, backups or a production server. No production deployment was performed.

## Documentation

- [Complete operations walkthrough](FULL_OPERATIONS_WALKTHROUGH.md)
- [RAG system and code walkthrough](RAG_SYSTEM_CODE_WALKTHROUGH.md)
- [Current status](PROJECT_STATUS.md)
- [Architecture](docs/architecture.md)
- [Data model](docs/data-model.md)
- [Evaluation](docs/evaluation.md)
- [Security and governance](docs/security-and-governance.md)
- [Gold review packet](docs/GOLD_REVIEW.md)
- [Phase 0 checkpoint](docs/checkpoints/phase-0.md)
- [Phase 1 checkpoint](docs/checkpoints/phase-1.md)
- [Phase 2 checkpoint](docs/checkpoints/phase-2.md)
- [Phase 3 checkpoint](docs/checkpoints/phase-3.md)
- [Demo guide](docs/demo.md)
- [Complete implementation plan](ANTIGRAVITY_IMPLEMENTATION_PLAN.md)
