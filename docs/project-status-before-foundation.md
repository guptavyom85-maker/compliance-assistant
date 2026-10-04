# Compliance Assistant Project Status

Last reviewed: 3 October 2026  
Repository revision reviewed: `508cc5c` on `main`

## Overview

The project is a Django-based RBI and SEBI regulatory compliance assistant. It uses Retrieval-Augmented Generation to retrieve passages from uploaded regulatory PDFs and give a grounded answer through an OpenRouter-hosted language model.

The current repository contains a functional academic prototype with:

- User authentication
- Regulatory PDF upload and management
- Clause-oriented PDF chunking
- Sentence Transformer embeddings
- FAISS similarity search
- Grounded language-model answers
- Paragraph citation checking
- Query logging
- Gold-question evaluation
- A Bootstrap-based web interface

The prototype demonstrates the complete path from uploading a document to retrieving evidence and generating an answer. It is not yet ready for production compliance decisions because index consistency, evaluation validity, source governance, authorization, and deployment security still need work.

## Technology Stack

| Area | Technology |
| --- | --- |
| Web framework | Django 4.2 |
| Database | SQLite |
| PDF extraction | PyMuPDF |
| Embeddings | `all-MiniLM-L6-v2` through Sentence Transformers |
| Vector search | FAISS `IndexFlatIP` |
| Language model access | OpenAI Python client connected to OpenRouter |
| Frontend | Django templates, Bootstrap 5, Bootstrap Icons |
| Authentication | Django authentication |

## Repository Structure

```text
compliance-assiistant/
├── compliance_assistant/    Django project settings and root URLs
├── qa/                      Models, views, forms, admin, migrations, and evaluation
├── rag/                     Chunking, embeddings, retrieval, generation, and citations
├── templates/               Application pages and shared layout
├── static/                  Custom static assets
├── media/documents/         Uploaded regulatory PDFs
├── vectorstore/             FAISS index and chunk-ID mapping
├── db.sqlite3               Local application data
├── manage.py                Django command entry point
└── requirements.txt         Python dependencies
```

## Features Built So Far

### Authentication

- Django login and logout routes are configured.
- Question answering, document management, query history, and evaluation pages require authentication.
- Django administration is available to staff users.
- The home page remains public and shows basic corpus statistics.

### Document Management

Authenticated users can:

- View uploaded regulatory documents
- Upload a document with a title, regulator, status, and effective date
- Index an uploaded document
- Delete a document and its current vectors

The `Document` model stores:

- Title
- Uploaded file
- RBI or SEBI regulator classification
- In-force, amended, or repealed status
- Effective date
- Upload time
- Indexing status
- Number of chunks

### PDF Chunking

`rag/chunker.py` extracts text page by page with PyMuPDF. It starts a new chunk when a line begins with a recognized structure such as:

- `3`
- `3.1`
- `(a)`
- `(iv)`

Each chunk records:

- Text
- Sequential chunk index
- Paragraph or clause identifier
- Starting PDF page
- Document title metadata

Very short chunks are merged into the preceding chunk.

### Embeddings and Vector Search

`rag/embedder.py` uses `all-MiniLM-L6-v2` to produce normalized 384-dimensional embeddings.

`rag/vectorstore.py` provides:

- Loading and saving a FAISS index
- Mapping FAISS positions to database chunk IDs
- Adding chunk vectors
- Similarity search
- Removing selected document chunks

Because the embeddings are normalized, inner-product search behaves like cosine similarity search.

### Question Answering

The question-answering workflow is implemented in `rag/pipeline.py` and `qa/views.py`:

1. The user submits a question.
2. The question is embedded.
3. FAISS returns the most similar chunks.
4. Matches below the configured threshold are removed.
5. Matching chunk records are loaded from SQLite.
6. The source text and metadata are sent to OpenRouter.
7. The model is instructed to answer only from the retrieved context.
8. The answer is checked for cited paragraph identifiers.
9. The answer and retrieval details are stored in the query log.

Current retrieval configuration:

| Setting | Value |
| --- | --- |
| Top results | `5` |
| Similarity threshold | `0.3` |
| Embedding dimension | `384` |

### Grounded Generation

`rag/llm.py`:

- Uses the OpenRouter OpenAI-compatible endpoint
- Sends document title, paragraph ID, page number, and text to the model
- Uses temperature `0`
- Instructs the model to use only the retrieved passages
- Requests paragraph and page citations for claims
- Requests a controlled not-found response for unsupported questions
- Adds an informational-use and legal-advice disclaimer
- Tries configured fallback model names after selected provider errors

### Citation Checking

`rag/citation_checker.py` extracts paragraph or clause references from the generated answer and checks that each cited identifier appeared in the retrieved context.

The application displays either:

- Citations verified
- Citation issue
- No citations found

This is currently an identifier-presence check. It does not yet prove that every claim is supported or that the cited page is correct.

### Query Audit Log

Every completed question can store:

- User
- Question
- Generated answer
- Retrieved chunk IDs
- Similarity scores
- Citation verification status
- Flag status
- Not-found status
- Response time
- Creation time

The interface shows up to 100 recent queries.

### Evaluation Dashboard

The project includes:

- `GoldQuestion` evaluation fixtures
- Batch `EvalRun` records
- Per-question `EvalResult` records
- Correct retrieval, refusal, error, and latency summaries
- A management command that seeds ten questions
- An evaluation dashboard with history and latest-run details

Evaluation currently runs through the live retrieval and OpenRouter answer path.

### Administration

Django admin pages are configured for:

- Documents
- Chunks
- Query logs
- Gold questions
- Evaluation runs
- Evaluation results

Query logs and evaluation results are configured mainly as review records in the admin interface.

### User Interface

The interface includes:

- Home dashboard
- Quick-question form
- Example questions
- Question and answer page
- Retrieved source-passage cards
- Citation-status badges
- Document list and upload pages
- Query log
- Evaluation dashboard
- Login page
- Staff administration link

The current interface uses a dark Bootstrap theme.

## Data Models

| Model | Purpose |
| --- | --- |
| `Document` | Uploaded regulatory source and its metadata |
| `Chunk` | Extracted retrieval passage linked to a document |
| `QueryLog` | Audit history for submitted questions and answers |
| `GoldQuestion` | Hand-written evaluation question and expected result |
| `EvalRun` | Summary of one evaluation batch |
| `EvalResult` | Result for one question within an evaluation run |

## Routes

| Route | Access | Purpose |
| --- | --- | --- |
| `/` | Public | Home page and system statistics |
| `/login/` | Public | Login |
| `/ask/` | Authenticated | Ask a compliance question |
| `/documents/` | Authenticated | View documents |
| `/documents/upload/` | Authenticated | Upload a document |
| `/documents/<id>/index/` | Authenticated POST | Parse and index a document |
| `/documents/<id>/delete/` | Authenticated POST | Delete a document |
| `/query-log/` | Authenticated | View recent queries |
| `/eval/` | Authenticated | View evaluation results |
| `/eval/run/` | Authenticated POST | Run the evaluation suite |
| `/admin/` | Staff | Django administration |

## Current Local Data Snapshot

At the time of review, the local workspace contained:

| Item | Count |
| --- | ---: |
| Documents | 2 |
| Documents marked indexed | 2 |
| Active database chunks | 234 |
| FAISS vectors | 397 |
| Query logs | 15 |
| Gold questions | 10 |
| Evaluation runs | 2 |
| Evaluation results | 20 |

The loaded files are:

- A SEBI consultation paper on strengthening the index derivatives framework
- A chapter from the RBI Financial Stability Report covering financial institutions and NBFCs

Both documents contain extractable text on every page.

## Environment Configuration

The application recognizes:

| Variable | Purpose |
| --- | --- |
| `OPENROUTER_API_KEY` | Authenticates generation requests |
| `OPENROUTER_MODEL` | Selects the primary OpenRouter model |
| `OPENAI_API_KEY` | Legacy fallback when the OpenRouter key is absent |
| `DJANGO_SECRET_KEY` | Django cryptographic signing key |
| `DEBUG` | Enables or disables development mode |

Secret values belong in `.env`. The file is excluded from Git.

## Local Setup

The existing `.venv` executable points to a missing interpreter and should be recreated.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_gold_questions
python manage.py runserver
```

After starting the server, open `http://127.0.0.1:8000/`.

## Validation Completed

- Django's standard system check passes.
- The model definitions and migration state match.
- Public home and login pages render successfully.
- Protected routes redirect unauthenticated users to login.
- Both PDFs have extractable text on every page.
- The cached embedding model loads successfully offline.
- The FAISS index and ID mapping can be read.
- Django discovers zero automated tests.
- Django's deployment check reports six security warnings under the current development settings.

The external language-model endpoint was not invoked during the repository audit, avoiding use of the configured API credential.

## Important Known Limitations

### Stale FAISS Entries

The database contains 234 active chunks, but FAISS and its ID mapping contain 397 entries. Chunk IDs `72` through `234` no longer exist in SQLite.

This indicates that re-indexing appended replacement vectors without first removing the old vectors. Stale entries can occupy top search positions and reduce the number of usable passages returned to the model.

### Evaluation Does Not Measure Answer Accuracy

- All seeded expected paragraph-ID lists are empty.
- The stored expected answer is not compared with the generated answer.
- Any non-refusal can count as correct for an answerable question with no expected IDs.
- Partial retrieval counts fully toward run accuracy.

The displayed evaluation accuracy should therefore not be treated as factual-answer accuracy.

### Corpus and Evaluation Mismatch

Most seeded questions concern RBI digital lending. The currently loaded documents concern SEBI derivatives and RBI financial stability or NBFC analysis.

The gold set should be aligned with the active corpus before evaluation results are used.

### Regulatory Source Classification

The SEBI source is a consultation paper and draft circular, while the RBI source is a financial-stability report chapter. Both are currently marked as in-force documents.

The data model needs a distinction between:

- Binding regulation
- Master direction
- Circular
- Consultation paper
- Draft circular
- Guidance
- Research or financial-stability report

### Page Citation Accuracy

Chunks can span more than one PDF page while storing only their starting page. Printed document page numbers can also differ from PDF file positions.

The NBFC file starts at printed report page 60 even though the application records that as PDF page 1.

### Access Control

Any authenticated user can currently:

- Upload sources
- Index documents
- Delete documents
- View the global query log
- Run evaluations

Production use needs role-based permissions.

### Production Security

The current configuration is for development. The deployment check identifies missing HTTPS and secure-cookie settings, a development-grade secret-key configuration, and enabled debug mode. `ALLOWED_HOSTS` also accepts every host.

### Upload Validation

The browser requests a PDF, but there is no strong server-side validation of:

- File signature
- MIME type
- File size
- Page count
- Malware status
- Parsing resource limits

### Testing

There are no automated tests yet. Priority coverage should include:

- Chunk boundary and metadata tests
- Index consistency tests
- Retrieval threshold tests
- Citation checker tests
- Refusal behavior tests
- Authorization tests
- Upload and deletion tests
- Evaluation scoring tests

## Recommended Next Work

1. Add an atomic `rebuild_vector_index` management command.
2. Make document re-indexing replace old vectors instead of appending duplicates.
3. Store the embedding model, vector dimension, corpus fingerprint, and build time with the index.
4. Align the active corpus and evaluation questions.
5. Populate expected source paragraphs and score answer correctness and faithfulness.
6. Return structured generation results instead of detecting refusal through exact answer text.
7. Track page spans and printed page labels for citations.
8. Add role-based permissions for corpus management, logs, and evaluation.
9. Add automated unit and integration tests.
10. Create separate development and production settings.

## Potential Extensions

After the correctness work, the project can be extended with:

- Hybrid vector and keyword retrieval
- Cross-encoder reranking
- Source highlighting and evidence spans
- Regulation version and amendment tracking
- Automated RBI and SEBI publication monitoring
- Clause-level document comparison
- Compliance obligation and control mapping
- Human answer-review workflows
- User feedback and correction handling
- Exportable audit evidence packages
- REST APIs and case-management integrations
- OCR and table-aware extraction
- Multilingual questions
- Corpus-gap and compliance analytics dashboards

## Current Readiness

The project is suitable for demonstrating a complete RAG workflow and for continued development as an academic or internal prototype.

Before operational compliance use, the system needs consistent vector state, a source-aligned evaluation set, stronger citation evidence, regulatory document governance, role-based permissions, automated tests, and production deployment controls.
