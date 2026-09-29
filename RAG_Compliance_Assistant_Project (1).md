# RBI/SEBI Regulatory Compliance Assistant (RAG)
**Course:** Foundations of AI & ML (ITC104), IIM Amritsar — Group Project

## Problem
Compliance teams have to track a constant stream of RBI/SEBI circulars and master directions, and finding the applicable rule — especially when older circulars have been amended or repealed — is slow and error-prone.

## What we're building
A question-answering tool for compliance staff. A user asks a question in plain English (e.g. *"What must a lender disclose to a borrower before a digital loan is executed?"*), and the tool:
- Retrieves the relevant paragraph(s) from a curated set of regulatory documents
- Answers **only** from those paragraphs — no answering from the model's general knowledge
- Cites the document, paragraph number, and page for every claim
- Says **"not found in the loaded documents"** when the answer isn't covered, instead of guessing

This is a **Retrieval-Augmented Generation (RAG)** system. The retrieval step is what keeps it grounded — proving that grounding works (via evaluation) is the actual substance of the project, not just producing a working chat interface.

## Why this topic
RBI recently completed a major consolidation, repealing thousands of older circulars and replacing them with a smaller set of consolidated Master Directions. Some provisions took effect on different dates than others. This means "which rule is currently in force" is a real, current problem — a plain LLM without retrieval tends to mix old and superseded rules with current ones. Solving that mixing problem is what differentiates this from a generic chatbot wrapper.

## Scope (MVP, given the deadline)
- **Documents:** starting with one core document (RBI Digital Lending Directions) rather than the full 5-8 document target, to guarantee a working, gradable submission on time. Additional documents are a stretch goal if time allows.
- **Retrieval:** plain embedding-based similarity search for the MVP. Hybrid (embedding + keyword/BM25) search and reranking are noted as future improvements, not built yet.
- **Grounded answering:** the LLM is instructed to answer only from retrieved chunks; a retrieval-confidence threshold triggers "not found" before the LLM is even called if nothing relevant is retrieved.
- **Citation verification:** after the LLM answers, the code checks that every cited paragraph was actually among the retrieved chunks — flags the answer if not. This is a cheap, high-value check against confident-but-wrong citations.
- **Evaluation set:** a hand-written gold set of questions with known correct answers, covering direct lookups, at least one multi-paragraph question, and unanswerable questions (to test that the system correctly refuses rather than hallucinating).

## Architecture
```
PDF documents → chunking by clause/paragraph + metadata
                        ↓
         embeddings → vector store (FAISS/Chroma)
                        ↓
User question → retrieval (top-k similar chunks)
                        ↓
        LLM answer (grounded only in retrieved chunks)
                        ↓
           citation verification check
                        ↓
        Answer + citations, or "not found"
```

**Chunking approach:** split by clause/paragraph number (regulatory text is structured that way), not by fixed-size windows — fixed windows tend to cut a rule off from its own exceptions or cross-references.

**Metadata per chunk:** document title, paragraph number, page number, and the source document's status (in force / amended / repealed) — this is what makes citations meaningful and lets the system reason about which rules currently apply.

## Tech stack
- **Backend:** Django (project: `compliance_assistant`, app: `qa`)
- **Database:** SQLite (models: `Document`, `Chunk`, `GoldQuestion`, `EvalRun`, `EvalResult`, `QueryLog`)
- **RAG logic:** a separate plain-Python `rag/` package (chunking, embeddings, vector store, retrieval, LLM calls, citation check) — kept independent of Django so it's testable on its own
- **PDF parsing:** PyMuPDF
- **Frontend:** Django templates + Bootstrap 5 (via CDN), no JS framework
- **Auth:** basic Django login gate for compliance-staff access

## Governance / responsible-AI angle
- The tool retrieves and summarizes regulation — it is explicitly **not legal advice** and doesn't replace a compliance officer's judgment
- Every answer shows its source paragraph text and the source document's status, so nothing is a black box
- Known failure modes (stale documents, misread tables/PDF extraction issues, over-confident wording) are documented rather than hidden
- Query logs are kept so answers can be reviewed after the fact

## Current status
- Django project and app scaffolded (models, admin, stub views, Bootstrap templates, basic auth)
- Clause-based chunking module built and manually spot-checked against a real RBI PDF
- Next: embeddings → vector store → retrieval → grounded LLM answering → citation check → evaluation

## What's explicitly out of scope for this MVP
- Multi-regulator coverage (SEBI documents) — stretch goal only
- Full amendment-linking (automatically pulling in what a chunk amends)
- Hybrid/keyword search and reranking
- Automated circular monitoring / alerts (post-course extension idea only)
