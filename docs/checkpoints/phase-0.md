# Phase 0 checkpoint — foundation implemented, acceptance pending

Updated: 4 October 2026.

## Changes delivered

- Additive migrations and a pre-migration SQLite backup in ignored `backups/`.
- Generation-based index persistence, checksums, fresh corpus fingerprint validation, model compatibility checks and cross-process locking.
- Idempotent indexing and safe rebuild on document deletion; retained upload bytes and previous generations.
- Page spans, printed-page offsets and separate-line paragraph marker recognition.
- Roles, server-side permission checks, private PDF delivery and owner-scoped query history.
- Upload validation and environment-based deployment settings.
- Structured answers, deterministic citation membership and semantic support checking.
- Separate evaluation metrics with missing judgment coverage instead of automatic passing scores.
- Source-linked gold review UI and ten unapproved corpus-aligned drafts.

## Before / after evidence

| Area | Before | Current behavior |
| --- | --- | --- |
| Index | 397 vectors, 234 database chunks; 163 stale IDs | Active generation rebuilt against current re-parsed corpus; IDs/count/fingerprint validated |
| Re-index | Delete chunks and append vectors | Preserve unchanged IDs and replace complete generation |
| PDF references | Starting page only | PDF start/end and printed page span |
| Source authority | Both sources unclassified/in-force | SEBI consultation is draft; RBI excerpt is a report |
| Evaluation | Empty expected IDs could pass any non-refusal | Unreviewed or unresolved ground truth blocks evaluation |
| Correctness | Inferred from retrieval/refusal | Separate structured judge result, including unavailable |
| Citations | Regex ID existence | Context membership and per-claim semantic support |
| Access | Any logged-in user could mutate corpus/run eval | Role checks and POST-only mutation endpoints |
| Private files | Development media URLs publicly accessible | Authenticated application route |

## Validation

Regression suite: `python manage.py test tests`. Tests cover actual FAISS generation files with mock embeddings, failed activation, model/text drift, concurrent corpus changes, idempotence, deletion, upload failure cases, authentication, ownership, role permissions, CSRF, gold review, metrics, schema repair and provider errors.

`makemigrations --check --dry-run` reported no model changes. `git diff --check` passed. Django deployment checks passed using temporary explicit production settings and a generated secret; `.env` was not modified to force production behavior.

Normal tests make no live model calls. The prompt-injection test verifies isolation of document instructions at the provider boundary, not actual live-model robustness. Real model quality and judge agreement are not established by these tests.

## Acceptance still open

1. Review and approve the ten questions in [GOLD_REVIEW.md](../GOLD_REVIEW.md), using the application's Evaluation review screen.
2. Run the dense baseline after approval with a functioning configured model provider.
3. Manually adjudicate a subset of generated answers and compare those labels with the automated judge.
4. Record all separate metrics, judgment coverage, failures and actual model identifiers.

`python manage.py check_foundation_gate` intentionally exits nonzero while this evidence is missing. Historical combined scores are retained but are not a replacement for the repaired baseline.

The user explicitly deferred human review and requested continued implementation. Phases 1–3 software workflows were therefore implemented without treating this acceptance gate as passed. Gold approvals remain pending; draft retrieval experiments are clearly provisional. This is a user-authorized sequencing change, not evidence of accepted model quality.

## Operational limits

- Operations are synchronous and the small-corpus implementation rebuilds the full index after each mutation.
- Chunking remains heuristic. It preserves page spans and recognizes separate decimal markers, but table structure and nonuniform printed page labels need further work. Word-count bounding is not an exact embedding-token guarantee.
- Filesystem activation and SQLite audit updates are not a distributed transaction. Readers validate the active pointer against database content; a rebuild is the recovery operation after an interrupted audit update.
- Existing legacy answers lack source snapshots that were never recorded. Their text and original logs are retained.
- No retention cleanup, production deployment, organization-level corpus isolation or live adversarial assurance has been implemented.
