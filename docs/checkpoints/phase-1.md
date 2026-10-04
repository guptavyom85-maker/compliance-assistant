# Phase 1 — retrieval and bounded agent

Updated: 4 October 2026. Software implemented; quality acceptance pending.

Delivered dense/BM25 fusion, cross-encoder reranking, source filters, selectable retrieval/strategy controls, separate component scores, bounded plans/tools, process timeouts, evidence/version scoping and persisted operational traces.

Provisional retrieval runs 3–5 used the same 485-chunk corpus and five-question test split with no errors. Reranking improved first-hit rank in this tiny draft benchmark; hybrid had higher Recall@5. See [evaluation](../evaluation.md) for results and cold-start caveats. Dense remains the default.

Regression coverage includes fusion ordering, lexical matches, filtering, reranker behavior, unknown tools, limits, timeout termination and dated-version selection. Remaining: reviewed benchmark, development-set calibration, controlled warm/cold timings, a live multi-document trace and adjudicated answer-quality evidence. Provider mocks cannot establish these outcomes.
