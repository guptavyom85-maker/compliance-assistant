# Evaluation methodology

## Preconditions

Each active answerable question needs a reference answer, reviewer identity/timestamp and required source evidence. Evidence must resolve against the current document and paragraph, with a text anchor where repeated paragraph labels need disambiguation. Unanswerable questions also require review. Editing questions or their evidence through the application invalidates approval.

The two supplied PDFs concern derivatives-market consultation and financial stability. The old digital-lending question set is retained as history and is inactive. Ten new unapproved drafts cover only these documents. Development and test splits each contain five questions. This is a small smoke benchmark; both splits share source documents and do not measure generalization to unseen regulations.

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

Human gold review was deferred at the user's request. Explicit `--allow-unreviewed` experiments remain provisional and do not approve references. `--retrieval-only` skips answer generation, semantic judgments and refusal scoring. Historical combined accuracy is not comparable. Cost is displayed as unknown rather than assumed free.

On 4 October 2026, retrieval-only test runs 3–5 completed without errors against 485 chunks. Dense/hybrid/reranked Hit@1 was 0.75/0.75/1.00; Recall@5 was 0.875/1.00/0.875; MRR was 0.8333/0.875/1.00. Hit@5 was 1.00 for all three. These scores use only the answerable subset of the five-question test split. See PROJECT_STATUS.md for timings. Cold model startup is included, disproportionately affecting the first dense run; no controlled speedup claim is justified.

No live answer-quality baseline or human judge-agreement result has been established. Administrators can now label EvalResult correctness through the evaluation screen; reviewer/time/notes are appended to run audit history and agreement is computed over labeled results. Thresholds and qualitative confidence remain uncalibrated. Tune on development data only, then freeze settings before an accepted test run.

## Validation limits

Regression tests mock providers to check metric formulas, identity matching, missing labels, failures and schema handling. They do not prove live model correctness, entailment quality, or resistance to prompt injection. The input-isolation test verifies prompt construction only. A live adversarial benchmark and a manually adjudicated judge-validation subset remain open.
