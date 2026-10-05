# Evaluation methodology

## Preconditions

Each active answerable question needs a reference answer, reviewer identity/timestamp and required source evidence. Evidence must resolve against the current document and paragraph, with a text anchor where repeated paragraph labels need disambiguation. Unanswerable questions also require review. Editing questions or their evidence through the application invalidates approval.

The active set contains 15 user-supplied, human-reviewed questions covering the SEBI derivatives consultation, RBI financial-stability report, and SEBI master circular. Eight are development questions and seven are held-out test questions. Older draft and legacy sets remain inactive history. The active questions share source documents and do not measure generalization to unseen regulations.

## Metric definitions

- Hit@1/3/k: at least one required evidence item occurs within the stated rank.
- Recall@k: fraction of required evidence items retrieved.
- MRR: reciprocal first relevant rank, zero for no hit.
- Correctness: 1 correct, 0.5 partial, 0 wrong, averaged over judged answerable questions. Refusing an answerable question scores zero.
- Faithfulness: supported claims divided by all substantively judged claims, pooled across answers.
- Citation precision: semantically supporting claim citations divided by judged claim citations.
- Correct refusal: correct abstentions divided by unanswerable questions.
- False refusal: abstentions divided by answerable questions.

Operational failures are shown in run coverage and mark a run partial. Unavailable semantic or correctness judgments remain null and are never reported as successful. Read coverage alongside scores; incomplete coverage cannot satisfy an acceptance gate. Refusal rates do not turn provider errors into successful abstentions.

## Judge and provenance

The structured judge receives reference answers, required evidence and generated claims. Its model, prompt version and explanation are saved. Run configuration records the source fingerprint and gold snapshot. Automated judgments still need comparison with human judgments before claims of model accuracy are made.

The replacement set was recorded as human-reviewed on 5 October 2026 with resolving paragraph and text anchors. Explicit `--allow-unreviewed` experiments remain provisional and do not approve references. `--retrieval-only` skips answer generation, semantic judgments and refusal scoring. Historical combined accuracy is not comparable. Cost is displayed as unknown rather than assumed free.

On 4 October 2026, retrieval-only test runs 3–5 completed against the older 485-chunk corpus and older five-question test snapshot. Dense/hybrid/reranked Hit@1 was 0.75/0.75/1.00; Recall@5 was 0.875/1.00/0.875; MRR was 0.8333/0.875/1.00. Those historical results are not a baseline for the replacement set or current 1,386-chunk corpus. A fresh evaluation is required.

No live answer-quality baseline or human judge-agreement result has been established. Administrators can now label EvalResult correctness through the evaluation screen; reviewer/time/notes are appended to run audit history and agreement is computed over labeled results. Thresholds and qualitative confidence remain uncalibrated. Tune on development data only, then freeze settings before an accepted test run.

## Validation limits

Regression tests mock providers to check metric formulas, identity matching, missing labels, failures and schema handling. They do not prove live model correctness, entailment quality, or resistance to prompt injection. The input-isolation test verifies prompt construction only. A live adversarial benchmark and a manually adjudicated judge-validation subset remain open.
