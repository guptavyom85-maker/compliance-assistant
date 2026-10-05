# Compliance Assistant — implementation status

Updated: 5 October 2026.

## Outcome

The main software workflows in Phases 0–3 of ANTIGRAVITY_IMPLEMENTATION_PLAN.md are implemented. **Acceptance is still incomplete.** The user supplied and approved a replacement 15-question gold set on 5 October 2026; a live answer-quality baseline and production review are still pending.

## What is built

- Foundation: additive migrations/backfills, pre-migration SQLite backup, validated PDF uploads, page spans, source authority metadata, role permissions, authenticated files and owner-scoped history.
- Index integrity: immutable FAISS generations, JSON mappings, checksums, corpus fingerprints, cross-process locking, atomic activation with bounded Windows sharing-violation retries, stale-index rejection and recoverable old generations.
- Answers: structured claims, application-generated source metadata, citation membership checks, semantic support judgments, conservative uncalibrated evidence bands and explicit provider failures.
- Retrieval: dense search, BM25/dense reciprocal-rank fusion, cross-encoder reranking, document/type filters and selectable retrieval mode.
- Query scoping: users must select one to ten indexed reference documents; direct retrieval, agent tools, citations, answer display and audit configuration are restricted to that explicit scope.
- Agent: bounded evidence-gathering plans, schema-validated tools, process-enforced timeouts, operational traces, scoped version comparisons and synthesis.
- Obligations: resumable extraction from eligible binding sources, verbatim quotation checks, semantic validation, zero-result handling and explicit human confirmation/edit/rejection.
- Gap analysis: company-policy comparison against confirmed obligations, five finding statuses, source snapshots, human review, HTML detail and downloadable PDF.
- Governance: unified review queue, reviewer audit history, date-filtered analytics, trust/limitations page, source-linked gold review and human-versus-judge labeling.
- Evaluation: distinct retrieval/correctness/support/citation/refusal metrics, configuration snapshots and coverage, with explicitly provisional and retrieval-only modes.

## Local evidence

The full regression suite passed **85 tests** on 4 October 2026. Tests use isolated databases/files and mocked remote providers; they verify software behavior, not live model quality.

An OpenRouter empty/invalid structured-response stall was fixed on 4 October 2026 by requiring native JSON-schema output, selecting compatible endpoints, adding a recorded free-router fallback, and skipping futile repair calls for empty content. A live synthetic answer plus independent support check completed successfully; real document content was not sent during that diagnostic.

The embedding loader now prefers the existing local Hugging Face cache. In local verification this reduced a fresh-process model initialization from about 25 seconds with a Hub check to about 0.5 seconds from cache. The `position_ids` checkpoint notice was non-fatal; routine load notices are now suppressed without suppressing real exceptions.

The corpus contains the draft SEBI derivatives consultation (110 chunks), an RBI financial-stability report excerpt (375), an in-force SEBI master circular (845), and an internal company policy (56): **1,386 indexed chunks**. Historic questions, results and logs are retained.

Fifteen source-aligned questions (IDs 21–35; eight development/seven test) are active and human-reviewed with 20 resolving evidence references. The previous drafts remain inactive history. Retrieval-only comparison runs 3–5 below used the older five-question test snapshot and remain historical/provisional:

| Mode | Hit@1 | Hit@5 | Recall@5 | MRR | Median ms | P95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 0.75 | 1.00 | 0.875 | 0.8333 | 3000 | 139422 |
| Hybrid | 0.75 | 1.00 | 1.000 | 0.8750 | 172 | 219 |
| Hybrid + reranker | 1.00 | 1.00 | 0.875 | 1.0000 | 10547 | 17328 |

These are **provisional**, tiny-sample retrieval measurements, not answer accuracy. Latency includes cold model loading; dense ran first, so timings are not a controlled warm-latency comparison. The default remains dense. See [evaluation](docs/evaluation.md).

## Remaining acceptance and limitations

1. Run the live answer-quality evaluation on the reviewed set, then label a judge-agreement subset manually.
2. Development-set threshold/confidence calibration, followed by held-out validation; controlled warm/cold latency measurement.
3. A live multi-document agent demonstration and live adversarial testing. Automated provider mocks do not establish model reliability.
4. Review the pending extracted obligations and produce at least five real reviewed gap findings. Synthetic regression fixtures are not substitute production evidence.
5. Production deployment/security review and operational load testing. This is a synchronous, single shared-corpus application.
6. Optional Phase 4 extensions remain unimplemented.

The original pre-upgrade report remains in [the archive](docs/project-status-before-foundation.md). See the [operator guide](README.md), [demo](docs/demo.md), and [phase checkpoints](docs/checkpoints/phase-0.md).
