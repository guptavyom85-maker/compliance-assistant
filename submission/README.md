# Professor submission pack

This folder contains the material intended to accompany the GitHub repository for the Compliance Assistant project.

## Recommended email contents

Send the following:

1. The GitHub repository URL, preferably pinned to a release tag or final commit.
2. `output/pdf/Compliance_Assistant_Project_Report.pdf` as the main attachment.
3. A short screen-recorded walkthrough made from `DEMO_WALKTHROUGH.md`.
4. The sample PDF documents, only if they are public and redistribution is permitted, or the original public download links.
5. `SETUP_GUIDE.md` if the professor is expected to run the project locally.
6. `EVALUATION_NOTE.md` if evaluation methodology is being assessed separately.

`EMAIL_DRAFT.md` contains a ready-to-customize email.

## What not to send or commit

- `.env` or any API key
- `db.sqlite3`
- `.venv/`
- `vectorstore/`
- `media/` unless the documents are explicitly approved for redistribution
- `backups/`, `tmp/`, logs, or cached models

These items are local runtime data and are already excluded by `.gitignore`.

## Scope represented in this submission

The demonstrated scope is document upload, indexing, document-scoped RAG questions, citations, query history, evaluation, index integrity, review operations, analytics, and trust information.

Obligation extraction and Policy Gap Analysis are experimental screens in the repository. They were not covered in the presentation and are not claimed as validated deliverables in this submission.

## Final checklist

- Replace all bracketed placeholders in `EMAIL_DRAFT.md` and `PROJECT_REPORT.md`.
- Rotate the OpenRouter key that was previously shared during debugging.
- Confirm `.env` is untracked with `git status` before pushing.
- Run the tests and Django system check.
- Test the setup instructions from a fresh clone if time permits.
- Record the walkthrough and verify that no API key, private document path, or personal data appears on screen.
- Attach only legally shareable source PDFs or provide their official source links.
