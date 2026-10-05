# Evaluation methodology and current status

## Ground truth

The active benchmark contains 15 human-reviewed questions with 20 source-evidence references:

- 8 development questions for iteration
- 7 held-out test questions for final checks
- coverage across the SEBI derivatives consultation, RBI financial-stability material, and SEBI master-circular material

Each answerable gold question contains a reviewed reference answer and one or more document paragraph references.

## Metrics

| Metric | Meaning |
| --- | --- |
| Hit@1 | Whether a required passage was the first retrieved result |
| Hit@3 | Whether a required passage appeared in the first three results |
| Hit@k | Whether a required passage appeared anywhere in the configured top-k results |
| Recall@k | The fraction of all required evidence retrieved |
| MRR | Rewards placing the first relevant passage near the top |
| Correctness | Compares the generated answer with the reviewed reference: correct, partial, or wrong |
| Faithfulness | Checks whether generated claims are supported by cited passages |
| Citation precision | Checks whether cited passages genuinely support the claims attached to them |
| Correct refusal | Whether the system refuses when the corpus lacks the answer |
| False refusal | Whether it refuses even though the answer is available |
| Median/P95 latency | Typical and slow-end response time |

## Split and mode

- **Split** selects the question group: development or held-out test.
- **Mode** selects retrieval: semantic search, combined semantic and BM25 search, or combined search with cross-encoder reranking.

## Current interpretation

The reviewed gold set is installed and resolves to the local corpus. A fresh accepted end-to-end answer-quality baseline has not yet been established for the current corpus and gold set.

Historical retrieval-only runs used an older corpus and an older question snapshot, so they must not be reported as current final accuracy. Recent partial runs were affected by external model-generation failures. Metrics marked **Unavailable** are not passing scores.

The evaluation framework is therefore a working engineering feature, while final empirical performance claims remain pending a stable provider run and manual review of a judge-agreement subset.
