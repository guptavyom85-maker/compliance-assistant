# Compliance Assistant — implementation status

Updated: 4 October 2026.

## Outcome

The main software workflows in Phases 0–3 of ANTIGRAVITY_IMPLEMENTATION_PLAN.md are implemented. **Acceptance is still incomplete.** At the user's request, human gold-answer review was deferred while implementation continued. No draft has been silently approved and no production-readiness claim is made.

## What is built

- Foundation: additive migrations/backfills, pre-migration SQLite backup, validated PDF uploads, page spans, source authority metadata, role permissions, authenticated files and owner-scoped history.
- Index integrity: immutable FAISS generations, JSON mappings, checksums, corpus fingerprints, cross-process locking, atomic activation with bounded Windows sharing-violation retries, stale-index rejection and recoverable old generations.
- Answers: structured claims, application-generated source metadata, citation membership checks, semantic support judgments, conservative uncalibrated evidence bands and explicit provider failures.
- Retrieval: dense search, BM25/dense reciprocal-rank fusion, cross-encoder reranking, document/type filters and selectable retrieval mode.
- Agent: bounded evidence-gathering plans, schema-validated tools, process-enforced timeouts, operational traces, scoped version comparisons and synthesis.
- Obligations: resumable extraction from eligible binding sources, verbatim quotation checks, semantic validation, zero-result handling and explicit human confirmation/edit/rejection.
- Gap analysis: company-policy comparison against confirmed obligations, five finding statuses, source snapshots, human review, HTML detail and downloadable PDF.
- Governance: unified review queue, reviewer audit history, date-filtered analytics, trust/limitations page, source-linked gold review and human-versus-judge labeling.
- Evaluation: distinct retrieval/correctness/support/citation/refusal metrics, configuration snapshots and coverage, with explicitly provisional and retrieval-only modes.

## Local evidence

The full regression suite passed **78 tests** on 4 October 2026. Tests use isolated databases/files and mocked remote providers; they verify software behavior, not live model quality.

An OpenRouter empty/invalid structured-response stall was fixed on 4 October 2026 by requiring native JSON-schema output, selecting compatible endpoints, adding a recorded free-router fallback, and skipping futile repair calls for empty content. The suite now passes **79 tests**. A live synthetic answer plus independent support check completed successfully; real document content was not sent during that diagnostic.

The supplied corpus contains a draft SEBI derivatives consultation (110 chunks) and an RBI financial-stability report excerpt (375 chunks): **485 indexed chunks**. Neither is treated as a binding obligation source. Historic questions, results and logs are retained.

Ten source-aligned gold drafts (IDs 11–20, five development/five test) remain unapproved. Retrieval-only comparison runs 3–5 completed without errors on the test split:

| Mode | Hit@1 | Hit@5 | Recall@5 | MRR | Median ms | P95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 0.75 | 1.00 | 0.875 | 0.8333 | 3000 | 139422 |
| Hybrid | 0.75 | 1.00 | 1.000 | 0.8750 | 172 | 219 |
| Hybrid + reranker | 1.00 | 1.00 | 0.875 | 1.0000 | 10547 | 17328 |

These are **provisional**, tiny-sample retrieval measurements, not answer accuracy. Latency includes cold model loading; dense ran first, so timings are not a controlled warm-latency comparison. The default remains dense. See [evaluation](docs/evaluation.md).

## Remaining acceptance and limitations

1. Human review of the draft references, then live answer-quality evaluation and a manually labeled judge-agreement subset.
2. Development-set threshold/confidence calibration, followed by held-out validation; controlled warm/cold latency measurement.
3. A live multi-document agent demonstration and live adversarial testing. Automated provider mocks do not establish model reliability.
4. Actual binding regulations and a company policy, reviewed obligations and at least five real reviewed gap findings. Synthetic regression fixtures are not substitute production evidence.
5. Production deployment/security review and operational load testing. This is a synchronous, single shared-corpus application.
6. Optional Phase 4 extensions remain unimplemented.

The original pre-upgrade report remains in [the archive](docs/project-status-before-foundation.md). See the [operator guide](README.md), [demo](docs/demo.md), and [phase checkpoints](docs/checkpoints/phase-0.md).
