# Architecture

## Application and storage

Django views enforce authentication, role permissions and POST-only mutations. SQLite holds documents, chunks, execution records, evaluation evidence and reviews. Uploaded PDFs stay in private media storage; authenticated application routes deliver them.

Document services parse and validate PDFs, preserve unchanged positional chunk IDs and rebuild the complete small-corpus index under a cross-process lock. FAISS generations contain an index, JSON ID mapping and checksummed manifest. An atomic CURRENT pointer selects one immutable generation. Transient Windows pointer-access errors receive bounded retries; a permanent failure leaves the previous pointer intact.

Queries validate model/dimension, normalization, checksums, IDs and a current text/metadata fingerprint. Slow model inference runs outside the corpus lock using the validated snapshot. Changed database content makes an older generation stale. Filesystem activation and database audit updates are not one transaction; rebuilding reconciles interrupted updates. Never restore a pointer without checking its corpus fingerprint.

## Retrieval and answering

The user selects dense, hybrid or hybrid_rerank retrieval. Hybrid combines normalized dense embeddings with BM25 using reciprocal-rank fusion; reranking applies a cached cross-encoder to candidates. Component scores remain separate and are not probabilities. Document filters are applied before final top-k selection.

Direct answering generates a strict JSON answer over retrieved passages, validates cited IDs against that context, then checks claim support. The application constructs trusted titles/pages/excerpts. Query logs preserve source snapshots, model metadata, timings, support results and failures. Missing judgments/costs remain unknown.

## Agent

Auto routing uses a question heuristic; users can request direct or agent execution. The agent generates a bounded evidence plan (at most four subquestions/six calls) and executes only schema-validated search, metadata, chunk and comparison tools. Worker processes permit hard timeout termination. Remaining total budget bounds synthesis as well as tool work.

Version-change questions require an unambiguous version family with two dated versions. Search scope and final evidence scope are validated. AgentRun/AgentStep persist operational actions and outcomes, not hidden reasoning. This is a bounded static plan, not an unrestricted autonomous browsing agent.

## Obligations and policy comparison

Extraction runs resumable batches keyed by source content and prompt version. Only eligible in-force binding sources qualify. Candidates require exact quotations, semantic support and human review. Review edits revalidate the complete duty; stale/unsupported duties cannot be confirmed.

Gap analysis compares confirmed obligations with passages retrieved only from the selected indexed company policy. Structured findings use addressed, partial, not_addressed, conflicting or needs_review. Invalid evidence produces review-required failures. Immutable source snapshots back the HTML/PDF report; human review changes effective counts without erasing original automated counts.

## Governance and evaluation

Administrators inspect review queues and date-filtered usage/quality analytics. Review events retain reviewer/time/notes. The evaluator separates retrieval from correctness, faithfulness, citations and refusal, storing corpus/gold/model configuration and coverage. Explicit draft runs are provisional; retrieval-only runs make no answer-provider calls.

Operational limits: synchronous requests, full-corpus rebuilds, heuristic text/table chunking, no organization-level isolation, no automatic retention cleanup, no production deployment.
