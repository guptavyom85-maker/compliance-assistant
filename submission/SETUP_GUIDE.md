# Compliance Assistant - setup guide

## Requirements

- Git
- Python 3.12
- An OpenRouter API key for live answer generation
- Internet access on the first run to download the embedding and reranker models

## Installation on Windows PowerShell

```powershell
git clone [Repository URL]
cd compliance-assiistant
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and set:

```text
DJANGO_SECRET_KEY=<a long random local secret>
OPENROUTER_API_KEY=<your own OpenRouter key>
```

Never commit `.env`.

## Database and login

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py bootstrap_roles
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Start the application:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/` and sign in with the created superuser.

## Recreating the demonstration corpus

The Git repository intentionally excludes uploaded PDFs, the SQLite database, and the generated FAISS index. Obtain the approved PDFs listed in `CORPUS_MANIFEST.md`, then:

1. Open **Documents**.
2. Select **Upload Document**.
3. Enter the document type, authority, source category, legal status, and available date/version metadata accurately.
4. Upload the text-based PDF.
5. Select **Index** beside the uploaded document.
6. Wait for the chunk count and green indexed indicator.

OCR is not included. Scanned PDFs without extractable text cannot be indexed.

## Basic use

1. Open **Ask Question**.
2. Enter a question.
3. Select one or more indexed documents.
4. Choose a retrieval mode and strategy.
5. Select **Get Answer**.
6. Review the answer, evidence confidence, warnings, and source passages.

Live generation depends on the configured external model provider. Temporary provider failures can prevent an answer even when retrieval succeeds.

## Validation

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test tests
.\.venv\Scripts\python.exe manage.py check_vector_index
```

Tests use mocked provider responses for most model-dependent paths. Passing tests confirms software behavior, not regulatory or model accuracy.
