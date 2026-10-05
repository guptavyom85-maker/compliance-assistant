# Compliance Assistant — Complete Operations Walkthrough

Updated: 4 October 2026.

This guide explains how to set up, operate, review, and troubleshoot the Compliance Assistant from the beginning. It covers the application that currently exists in this repository. It does not treat automated answers as legal advice or human approval.

## 1. What the application does

The Compliance Assistant works with a controlled collection of PDF documents. It can:

1. Upload and classify regulatory sources and company policies.
2. Parse those PDFs into source-linked passages and build a searchable index.
3. Answer questions using only retrieved passages from the loaded collection.
4. Use semantic search, combined keyword/semantic search, or cross-encoder passage ranking.
5. Run a bounded multi-step evidence search for comparison-style questions.
6. Create draft regulatory obligations from eligible binding sources for human review.
7. Compare a company policy against confirmed obligations and produce a reviewable gap report.
8. Evaluate retrieval and answer quality against human-reviewed reference questions.
9. Record operational history, review queues, analytics, evidence, and reviewer decisions.

It does **not** automatically determine legal compliance. Retrieval, generation, support labels, confidence bands, obligation extraction, and gap classifications can all be wrong. Users must inspect the original source and its legal authority.

## 2. How information flows

```text
PDF upload
   ↓
Document classification and validation
   ↓
Parse into page-linked passages
   ↓
Build and activate a validated FAISS index
   ↓
Question → retrieval → structured answer → citation/support checks
                                └→ saved query and evidence snapshot

Eligible binding source → draft obligations → human confirmation
                                              ↓
Indexed company policy + confirmed obligations
                                              ↓
                                  policy gap report → human review → PDF
```

The database stores documents, passages, questions, runs, reviews, and audit information. The vector index stores search vectors in immutable generations. Uploaded PDFs remain private application files and are served only through authenticated routes.

## 3. Main project locations

| Location | Purpose |
| --- | --- |
| `manage.py` | Runs Django administration and project commands |
| `compliance_assistant/settings.py` | Environment, security, upload, model, and retrieval settings |
| `qa/` | Database models, forms, views, permissions, workflows, and commands |
| `rag/` | Chunking, embeddings, retrieval, reranking, generation, support checks, and agent code |
| `templates/` | Web interface |
| `media/documents/` | Uploaded PDFs; treat as private data |
| `vectorstore/` | Immutable index generations and the active `CURRENT` pointer |
| `db.sqlite3` | Local SQLite database |
| `docs/` | Architecture, evaluation, governance, checkpoints, and review material |
| `tests/` | Isolated regression tests |

Do not manually edit `db.sqlite3`, vector generation files, or the `CURRENT` pointer. Use the application or management commands.

## 4. Requirements

For the existing Windows project:

- Python 3.12 is recommended.
- The existing `.venv` can be reused if its dependencies are intact.
- An OpenRouter API key is required for generated answers, semantic support judgments, obligation extraction, gap classification, and scored answer evaluation.
- Embedding and reranker models may download the first time they are used.
- Internet access is needed for first-time model downloads and remote language-model calls.

Retrieval-only evaluation does not call the answer provider, but local embedding/reranker models are still required.

## 5. First-time local setup

Open PowerShell in the project directory:

```powershell
cd C:\Users\Vyomkesh\Desktop\compliance-assiistant
```

If the existing environment is usable, install or synchronize dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

For a fresh environment instead:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy the example configuration once:

```powershell
Copy-Item .env.example .env
```

Open `.env` and configure at least:

```dotenv
DEBUG=True
DJANGO_SECRET_KEY=a-long-random-local-secret
ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_SECURE_COOKIES=False

OPENROUTER_API_KEY=your-key-here
OPENROUTER_MODEL=your-supported-model
OPENROUTER_JUDGE_MODEL=your-supported-judge-model
```

Never commit `.env` or share its keys. The default model names can change or become unavailable, so use models currently enabled for your OpenRouter account.

Apply the database migrations and create the application roles:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py bootstrap_roles
```

Create the first Django administrator:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Run initial checks:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py check_vector_index
```

`check_vector_index` requires an existing valid index. If this is a new empty installation, build an empty valid generation first:

```powershell
.\.venv\Scripts\python.exe manage.py rebuild_vector_index
```

Start the local site:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Then open `http://127.0.0.1:8000/` and sign in at `/login/`.

## 6. Users and roles

The project defines three application groups. Running `bootstrap_roles` creates or updates them but does not assign users.

| Role | Main capabilities |
| --- | --- |
| Viewer | Ask questions, read the shared document list, open authenticated PDFs, view their own query history |
| Contributor | Viewer capabilities plus upload/index documents, extract/review obligations, and run/view their own gap analyses |
| Admin | Contributor capabilities plus delete documents, inspect index integrity, run/review evaluations, view global logs, analytics, and the review queue |

A Django superuser has full application access. Django `staff` status is separate: it controls access to `/admin/` and should only be granted to users who need the Django administration interface.

To add ordinary users:

1. Sign in as the superuser.
2. Open **Admin** in the sidebar.
3. Open **Users** and add or select a user.
4. Add the user to exactly the role group that matches their work: Viewer, Contributor, or Admin.
5. Save.

Avoid assigning permissions one by one unless you understand Django permissions. Re-run `bootstrap_roles` after permission-related migrations or upgrades.

## 7. Navigation and what each screen does

### Home

Shows application context and, for signed-in users, corpus/query summary counts. Anonymous users do not receive private collection counts.

### Ask Question

Accepts a question, retrieval method, and execution strategy. After processing, it opens a detailed answer containing claims, source passages, support labels, confidence, warnings, and run metadata.

### Documents

Lists loaded PDFs, authority/status, type/category, passage count, index state, and actions. Contributors can upload/index; Admin users can delete.

### Query Log

Shows the latest query records. Ordinary users see only their own. Admin users with global-log permission can see all users' records.

### Evaluation

Admin-only area for gold/reference question review, evaluation runs, metrics, and human labeling of automated correctness judgments.

### Index integrity

Admin-only view of the active generation manifest or an integrity error. Use it after corpus/configuration changes or suspected retrieval failures.

### Obligations

Contributor/Admin area for extraction batches, filters, candidates, and human decisions. Only eligible binding regulatory sources can be extracted.

### Policy gap analysis

Contributor/Admin workflow to compare one indexed company policy against confirmed obligations from selected indexed binding sources.

### Review queue

Admin-only combined view for answers and gap-related items needing review. Review resolution is an operational triage record; it does not rewrite source evidence.

### Analytics

Admin-only date-filtered operational summary: volume, errors, refusals, confidence/support, latency, review backlog, cost coverage, topics, and latest evaluation information.

### Scope and trust

Explains source authority, data sent to configured providers, automated-check limitations, and why the system is not legal advice or compliance certification.

### Admin

Django's low-level database administration interface. It is visible only to staff users. Use the purpose-built application screens for normal operations; use Admin for account/group administration and careful record inspection.

## 8. Document workflow

### 8.1 Prepare a PDF

The upload validator requires:

- A real PDF signature, not merely a `.pdf` filename.
- `application/pdf` or generic binary MIME type.
- File size within `MAX_UPLOAD_MB` (25 MB by default).
- 1 to `MAX_PDF_PAGES` pages (500 by default).
- No password/encryption requirement.
- At least some extractable text.
- A file digest that is not already loaded.

Scanned image-only PDFs are rejected because OCR is not implemented. Run trusted OCR externally and review the result before upload.

### 8.2 Upload and classify

Open **Documents → Upload Document**. Complete the fields carefully:

| Field | Meaning and use |
| --- | --- |
| Title | Human-readable source name shown in citations and reports |
| File | The PDF to store and parse |
| Document type | `Regulatory source` or `Company policy`; controls later workflows |
| Regulator | RBI or SEBI for a regulatory source; company policies should not claim a regulator |
| Source category | Legal/authority class used by extraction safeguards |
| Status | In force, amended, repealed, draft/consultation, or not applicable |
| Source URL | Optional official origin for traceability |
| Publication date | Source publication date |
| Effective date | Date the requirements take effect, if applicable |
| Version label | Human label such as `2026 amendment` |
| Version family | Stable family shared by versions that may be compared |
| Printed page offset | Difference between PDF page number and printed page number |

Source-category rules matter:

- Use **binding regulation**, **master direction**, or **circular** only when the source genuinely has that authority.
- Drafts and consultation papers should be `consultation_paper` with draft status.
- Research/financial-stability publications should be `report`.
- A company policy should use document type `company_policy`, category `internal_policy`, and no regulator.

Incorrectly marking a report or draft as binding would undermine obligation and gap results. The application blocks clearly ineligible categories, but humans remain responsible for accurate classification.

### 8.3 Index the document

Uploading only stores metadata and the PDF. On the Documents page, select **Index**.

Indexing:

1. Revalidates/parses the stored PDF.
2. Splits text into bounded, page-linked passages.
3. Preserves IDs for unchanged positional passages where possible.
4. Rebuilds the complete small-corpus vector index.
5. Validates the files, IDs, model configuration, and corpus fingerprint.
6. Atomically activates the new generation
The operation is synchronous; keep the request open. The first embedding-model use may take longer. After success, the document shows a passage count, ready/indexed state, and becomes searchable.

### 8.4 Re-index

Use **Re-index** when a document needs reparsing under the current chunker or after a prior indexing failure. Metadata changes that affect the corpus fingerprint also require a successful rebuild before questions can continue.

Command-line full rebuild:

```powershell
.\.venv\Scripts\python.exe manage.py rebuild_vector_index
``` 

Then verify:

```powershell
.\.venv\Scripts\python.exe manage.py check_vector_index
```

### 8.5 Delete

Only Admin users can delete documents. Deletion removes the document and its passages from the database and rebuilds the active index. The uploaded bytes are intentionally retained for recovery; there is no automatic retention cleanup. Treat retained files and old index generations as sensitive data.

Do not manually remove an active vector generation. Establish an approved retention/backup policy before cleaning retained data.

## 9. Asking questions

Open **Ask Question** and enter a specific question about the loaded sources.

Select between one and ten indexed documents in **Reference documents**. The selection is mandatory. Use Ctrl-click on Windows (or Cmd-click on macOS) to select several entries. Only selected documents can enter retrieval, agent tools, generation context, or citations. The answer page repeats the source scope, and the audit record stores document IDs plus title/type/category/status snapshots.

Document selection is authoritative: writing “RBI” or a document name in the question does not automatically select it. If you select only the Shadow Banking document, only that document may be cited. To compare two sources, select both and use Automatic or Multi-step evidence search.

Good questions identify the subject, source or time period when relevant:

- “According to the loaded SEBI consultation, who decides the weekly options expiry day?”
- “What deposit growth does the RBI report state for 2025–26?”
- “Compare the 2024 and 2026 versions of policy X regarding record retention.”

Avoid assuming the corpus contains material that has not been loaded. A proper result may abstain.

### 9.1 Retrieval choices

| Choice | What it does | Best use |
| --- | --- | --- |
| Semantic search | Uses embedding similarity | Conceptual questions and the current conservative default |
| Combined search | Fuses semantic and BM25 keyword ranks | Exact terms, clause names, acronyms, and mixed queries |
| Combined search with passage ranking | Reranks combined candidates with a cross-encoder | When best-first ordering matters and extra latency is acceptable |

Scores from these mechanisms have different meanings. They are ranking signals, not correctness probabilities.

### 9.2 Strategy choices

| Choice | What it does |
| --- | --- |
| Automatic | Uses a heuristic: comparison/change/multi-part wording may invoke the bounded agent; other questions use direct search |
| Single search | One retrieval and answer synthesis path |
| Multi-step evidence search | Produces a bounded plan and uses approved read-only evidence tools before synthesis |

The multi-step strategy is useful for comparisons and source/version questions. It is limited to four subquestions and six tool calls by default. Each step and the total run have hard time budgets. It cannot run arbitrary code, browse arbitrary websites, or modify sources.

For change-over-time questions, upload at least two dated documents with the same unambiguous **version family**. Otherwise the system should decline to imply a valid version comparison.

### 9.3 Reading the answer page

Interpret each section separately:

- **Answerable/reason:** an abstention says the loaded evidence was insufficient or verified synthesis did not complete.
- **Claims:** individual answer statements rather than one unstructured block.
- **Support status:** automated classification such as supported, partial, unsupported, contradicted, or unavailable.
- **Sources:** title, paragraph, PDF page span, printed page span, source category/status, passage, and PDF link.
- **Evidence confidence:** a conservative qualitative band, not a probability and not calibrated legal confidence.
- **Human review required:** why the record was flagged.
- **Run metadata:** model, prompt version, time, retrieval configuration, index generation, and fingerprint.
- **Evidence-gathering trace:** for agent runs, the operational plan/actions, summaries, timing, and errors. It is not hidden model reasoning.

Always open the original PDF and examine context, authority, dates, amendments, and definitions before relying on a claim.

### 9.4 Query history

The Query Log preserves answer/evidence snapshots so an old record remains inspectable even if the corpus later changes. Old historical records may predate structured evidence and will say semantic support was not measured.

## 10. Obligation extraction and review

This workflow turns passages into **draft candidates**, not approved legal duties.

### 10.1 Preconditions

The source must be:

- Document type: regulatory source.
- Status: in force.
- Category: binding regulation, master direction, or circular.
- Successfully indexed.

Reports, guidance, consultations, repealed sources, drafts, and company policies are not eligible sources for this extraction workflow.

### 10.2 Extract a batch

Open **Obligations**, find the eligible source, and run extraction. The web workflow processes up to ten passages per batch. Run another batch to resume. Extraction records are keyed to source content and prompt version, so completed work is not silently repeated.

Command-line equivalent:

```powershell
.\.venv\Scripts\python.exe manage.py extract_obligations --document-id 3 --limit 10
```

Replace `3` with the real document ID. The command permits bounded limits and reports processed passages, candidates, and errors.

Zero candidates can be a valid result. An error or no result must not be converted into an invented obligation.

### 10.3 Review each candidate

Open a candidate and compare it to the displayed quote and original PDF. Review:

- Complete obligation text.
- Obligated party.
- Condition or scope.
- Deadline or trigger.
- Exact source quotation and pages.
- Entailment/support explanation.

Choose:

- **Confirm** when the full duty is accurate and supported.
- **Edit and confirm** when wording/fields need correction; the edited duty is revalidated against the source.
- **Reject** when it is not a valid obligation.

Add useful reviewer notes. Confirmation records the reviewer and time. If the source becomes stale or semantic support fails, the candidate remains outside gap analysis rather than being force-approved.

Filters on the Obligations page can narrow by review status, source document, confidence, entailment, or obligated party.

## 11. Policy gap analysis

### 11.1 Preconditions

You need:

1. One indexed `company_policy` document, normally category `internal_policy` and no regulator.
2. One or more indexed, in-force binding regulatory sources.
3. Human-confirmed, currently supported obligations from those selected sources.
4. A functioning generation/judge provider.

If a document does not appear in a selector, check its document type, category, status, indexed state, and confirmed obligations.

### 11.2 Run an analysis

Open **Policy gap analysis**:

1. Select the company policy.
2. Select one or more binding regulatory sources.
3. Submit the analysis.

For each eligible confirmed obligation, the system searches only within the selected policy, asks for a structured coverage judgment, validates cited candidate passages, and stores an immutable evidence snapshot.

### 11.3 Finding statuses

| Status | Meaning |
| --- | --- |
| Addressed | Policy evidence appears to cover the obligation |
| Partial | Policy evidence covers only part of it |
| Not addressed | No adequate matching policy coverage was established |
| Conflicting | Policy evidence appears inconsistent with the obligation |
| Needs review | Evidence/judgment was ambiguous, invalid, unavailable, or failed validation |

“Not addressed” means no adequate coverage was established by this bounded process. It is not proof of non-compliance.

### 11.4 Review and export

For every finding:

1. Read the regulatory duty and its quotation.
2. Open the original regulatory source.
3. Read any retrieved policy evidence in full context.
4. Accept the automated status or select an override.
5. Record review notes.

The effective report count can reflect human overrides, while the original automated result remains preserved. Download the PDF from the report page after review. The PDF contains scope, limitations, evidence, configuration context, and findings; it is not a compliance certificate.

Users normally see only reports they created. Admin users with global-log permission can inspect all reports.

## 12. Evaluation and gold-reference review

Evaluation is an Admin workflow. It answers two separate questions:

1. Did retrieval find the required source passages?
2. Did the generated answer have acceptable correctness, support, citations, and refusal behavior?

### 12.1 Prepare draft questions

For the two sample PDFs in this repository:

```powershell
.\.venv\Scripts\python.exe manage.py prepare_corpus_gold
```

This creates or refreshes corpus-aligned **drafts**. It never approves them and does not overwrite human-reviewed or edited references. Legacy data is retained.

### 12.2 Review a reference question

Open **Evaluation**, select a question, and inspect:

- The exact wording.
- Development or held-out test split.
- Answerable/unanswerable category.
- Reference answer and notes.
- Every required document/paragraph/text anchor.
- Current matching source passages.

Use passage search to add the correct evidence, remove incorrect evidence, and save edits. Saving or changing evidence invalidates prior approval. Confirm only after the answer and evidence are correct; confirmation records reviewer identity and time.

Answerable questions require a reference answer and resolving required evidence. Unanswerable questions require human review but do not need invented source evidence.

The current IDs 11–20 remain unapproved because review was explicitly deferred. Do not treat provisional results as accepted accuracy.

### 12.3 Run evaluation

Normal command:

```powershell
.\.venv\Scripts\python.exe manage.py run_rag_evaluation --label dense-baseline --split test --mode dense
```

Normal runs require reviewed data. For an explicitly provisional draft experiment:

```powershell
.\.venv\Scripts\python.exe manage.py run_rag_evaluation --label draft-check --split dev --mode hybrid --allow-unreviewed
```

For retrieval without answer-provider calls:

```powershell
.\.venv\Scripts\python.exe manage.py run_rag_evaluation --label retrieval-check --split test --mode hybrid_rerank --allow-unreviewed --retrieval-only
```

Compare all retrieval modes on the same split:

```powershell
.\.venv\Scripts\python.exe manage.py compare_retrieval --allow-unreviewed --split test
```

First-run timings include model initialization/download and are not a controlled warm-latency comparison.

### 12.4 Interpret metrics

| Metric | Meaning |
| --- | --- |
| Hit@1/3/5 | Whether at least one required source appears within that rank |
| Recall@5 | Fraction of all required evidence retrieved in the first five |
| MRR | Rewards putting the first relevant source earlier |
| Correctness | Automated correct/partial/wrong judgment against the reference |
| Faithfulness | Supported substantive claims divided by judged claims |
| Citation precision | Supporting citations divided by judged claim citations |
| Correct refusal | Appropriate abstentions on unanswerable questions |
| False refusal | Abstentions on answerable questions |
| Coverage/errors | Whether judgments actually completed; unavailable is not success |

Keep development and test roles distinct: tune settings/thresholds on development data, freeze the configuration, then evaluate once on held-out test data.

### 12.5 Human-check the judge

For generated evaluation results, an Admin can label correctness as correct, partial, or wrong and add notes. The application records reviewer/time/notes and calculates exact agreement with the automated judge over human-labeled results. A useful accuracy claim requires enough independent human labels; the feature existing does not itself validate the judge.

Readiness check:

```powershell
.\.venv\Scripts\python.exe manage.py check_foundation_gate
```

This intentionally fails until the active references are reviewed and the required scored baseline exists. That failure currently reflects pending human acceptance, not missing software workflows.

## 13. Review queue and analytics

### Review queue

Use this Admin page to find records needing attention. Review the actual evidence in the underlying answer/finding before marking an item resolved or dismissed. Include a concise resolution note. Queue resolution means “triaged/reviewed”; it does not make an unsupported claim true.

### Analytics

Use optional start/end dates to inspect a defined period. Read metrics together:

- Query count, errors, and refusals.
- Confidence/support distribution.
- Median and p95 response time.
- Known cost coverage; unknown cost remains unknown.
- Frequent question keywords/topics.
- Open review backlog.
- Latest evaluation state.

Analytics describe application operation and automated outputs. They are not evidence that legal obligations are complete.

## 14. Routine operating procedure

### At startup or after configuration changes

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py bootstrap_roles
.\.venv\Scripts\python.exe manage.py check_vector_index
```

If the index reports stale/missing/incompatible:

```powershell
.\.venv\Scripts\python.exe manage.py rebuild_vector_index
.\.venv\Scripts\python.exe manage.py check_vector_index
```

### When adding a source

1. Verify provenance and authority outside the application.
2. Upload with correct type/category/status/dates/version family.
3. Index it and confirm its passage count/state.
4. Open several PDF-linked passages to sanity-check text/pages.
5. Ask targeted questions and review answers.
6. If eligible, run obligation batches and review every candidate.

### When adding a company policy

1. Upload as company policy/internal policy without a regulator.
2. Index and inspect passage/page quality.
3. Confirm applicable regulatory obligations first.
4. Run scoped gap analysis.
5. Human-review every finding before exporting or sharing.

### Before a demonstration or release

```powershell
.\.venv\Scripts\python.exe manage.py test tests
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py check_vector_index
```

Then check role access, original PDF links, model availability, review backlog, current evaluation status, and displayed limitations.

## 15. Troubleshooting

### “Index rebuild required” or questions stop working

The active index is missing, corrupt, incompatible, or stale relative to the database/configuration.

1. Run `check_vector_index` for the exact readiness failure.
2. Run `rebuild_vector_index`.
3. Run `check_vector_index` again.
4. Confirm `EMBEDDING_MODEL` and `EMBEDDING_DIMENSION` match.

The system fails closed rather than querying stale vectors.

### Upload is rejected

Check actual PDF signature, MIME type, size, page count, encryption, extractable text, and duplicate content. Image-only scans require OCR before upload.

### Indexing fails

Check that the PDF still exists and parses, local model files can load/download, disk space is available, and no other long rebuild holds the corpus lock. The previous valid generation remains active, but it will be rejected if the database corpus has changed.

### Provider/model error

Check `OPENROUTER_API_KEY`, model names, account/provider availability, network access, and timeouts. The UI deliberately sanitizes provider details. Do not place secrets in logs or screenshots.

### First question is very slow

The development server preloads the embedding model before accepting requests, and later calls reuse it from memory. On a fresh installation it may first download from Hugging Face; `HF_TOKEN` is optional and only provides higher download limits. A cached model is opened locally without a Hub request. Reranking is still loaded only when first selected. Agent runs also involve several bounded provider/tool steps.

### Agent abstains or times out

Make the question more specific, verify the needed sources are indexed, use correct version-family metadata, try direct mode for a simple question, or adjust timeout settings only after measuring provider behavior. Do not interpret timeout as evidence that the answer does not exist.

### Document is missing from obligation extraction

It must be an indexed regulatory source, in force, and categorized as binding regulation/master direction/circular.

### Document is missing from gap-analysis selectors

The policy must be an indexed company policy. Regulations must be indexed, in force, and binding-category sources. Confirmed supported obligations must also exist for meaningful analysis.

### Evaluation refuses to run

Normal evaluation requires active, human-reviewed questions with valid current evidence. Review them, or use `--allow-unreviewed` only for explicitly provisional experimentation. Provisional mode does not create approvals.

### Confidence seems low despite relevant text

Confidence is deliberately conservative and uncalibrated. Inspect retrieval rank, source support, citation membership, contradictions, and judgment availability. Never raise thresholds or relabel evidence solely to improve a dashboard number.

### `fitz` deprecation warning

The environment may warn that the legacy import name is deprecated. It does not currently invalidate a successful test/index operation, but migration to the current `pymupdf` import style should be handled as dependency maintenance.

## 16. Configuration reference

The complete template is `.env.example`. Important groups:

### Security

- `DEBUG`: local debugging only.
- `DJANGO_SECRET_KEY`: strong secret required when debug is off.
- `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`: explicit deployment origins.
- `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SECURE_COOKIES`, HSTS settings: production HTTPS controls.
- `DJANGO_TRUST_PROXY_SSL_HEADER`: enable only behind a trusted proxy that strips client-supplied forwarding headers.

### Providers

- `OPENROUTER_API_KEY`: remote generation credential.
- `OPENROUTER_MODEL`: answer/planning/extraction model.
- `OPENROUTER_JUDGE_MODEL`: support/correctness/gap judgment model.
- `OPENROUTER_FALLBACK_MODELS`: optional comma-separated 404/429 fallbacks.
- `LLM_TIMEOUT_SECONDS`: provider call timeout.
- Cost-per-million-token fields: optional estimates; zero/unknown must not be reported as measured cost.

### Retrieval

- Embedding/reranker model names and embedding dimension.
- Default retrieval mode.
- Candidate/top-k counts and reciprocal-rank fusion constant.
- Dense/BM25 weights and reranker minimum score.
- Dense confidence floor.
- Agent step/subquestion/time limits.
- Maximum question length.

Treat model, dimension, chunking, and corpus metadata changes as index-affecting changes. Rebuild and reevaluate rather than comparing incompatible runs.

## 17. Production deployment checklist

The repository has not been production-deployed. Before production:

1. Set `DEBUG=False` and a strong secret outside source control.
2. Configure exact hosts, trusted CSRF origins, HTTPS redirect, secure cookies, and suitable HSTS.
3. Use a production application server and trusted reverse proxy.
4. Ensure the web server cannot serve `media/` or backups directly.
5. Decide whether third-party provider processing is allowed for every source/query class.
6. Add organization/tenant isolation if multiple organizations will use the system.
7. Establish encrypted backups, restore tests, retention/deletion, audit retention, and key rotation.
8. Add monitoring, rate/request limits, dependency scanning, log controls, and incident procedures.
9. Run Django deployment checks under the real production configuration:

```powershell
.\.venv\Scripts\python.exe manage.py check --deploy
```

10. Complete live adversarial, model-quality, human-judge, latency, and legal/governance acceptance.

A passing Django check or test suite is not a security audit.

## 18. Current repository state

At the time of this guide:

- The real corpus has 485 indexed passages from two PDFs.
- The SEBI source is a draft consultation, not a binding regulation.
- The RBI source is a financial-stability report excerpt, not a binding regulation.
- Neither source should be used to manufacture confirmed regulatory obligations.
- The ten source-aligned gold drafts remain unapproved because human review was deferred.
- Retrieval-only comparison results are provisional and documented in `PROJECT_STATUS.md`.
- The complete regression suite passes 85 tests with mocked remote providers.
- Real obligation/gap acceptance still needs authorized binding sources, a company policy, human-confirmed duties, and reviewed findings.

## 19. Recommended first practical session

For someone seeing the project for the first time:

1. Read **Scope and trust** in the application.
2. Open **Documents** and inspect the classification of both supplied PDFs.
3. Open each source PDF and verify that page links work.
4. Open **Index integrity** and confirm 485 vectors with no error.
5. Ask one direct question using semantic search.
6. Repeat it with combined search and compare the retrieved passages, not just wording.
7. Ask a comparison question with multi-step strategy and inspect the operational trace.
8. Open **Query Log** and inspect the saved evidence snapshot.
9. Open **Evaluation** and review the provisional runs, without treating drafts as approved.
10. Inspect **Obligations** and **Policy gap analysis**, noting why the current real sources do not satisfy their binding-source/policy prerequisites.
11. Open **Review queue** and **Analytics** as Admin.
12. Run the validation commands before changing source code or configuration.

## 20. Related documentation

- `README.md` — concise setup and feature guide.
- `RAG_SYSTEM_CODE_WALKTHROUGH.md` — complete RAG architecture, code path, and module explanations.
- `PROJECT_STATUS.md` — current implementation/validation status and provisional benchmark.
- `ANTIGRAVITY_IMPLEMENTATION_PLAN.md` — original target plan and acceptance expectations.
- `docs/architecture.md` — component and data-flow design.
- `docs/data-model.md` — stored entities and runtime purpose.
- `docs/evaluation.md` — metric definitions and evaluation limits.
- `docs/security-and-governance.md` — roles, privacy, controls, and deployment risks.
- `docs/demo.md` — short demonstration sequence.
- `docs/GOLD_REVIEW.md` — human-review packet for current reference drafts.
- `docs/checkpoints/` — phase-by-phase implementation and pending acceptance evidence.

When documents disagree, use the current code and `PROJECT_STATUS.md` as the description of what is actually implemented, and treat `ANTIGRAVITY_IMPLEMENTATION_PLAN.md` as the intended specification rather than evidence of completion.
