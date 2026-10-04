# Data model

| Model | Runtime role |
| --- | --- |
| Document | Upload, source authority/status, digest, dates/version family, indexing state and private file |
| Chunk | Document-qualified passage, paragraph, hash and PDF/printed page spans |
| VectorIndexBuild | Generation configuration, fingerprint, counts and build audit |
| QueryLog | Question, answer, evidence snapshot, confidence/support, model metadata and failures |
| GoldQuestion / GoldEvidence | Versioned references, review identity, split and resolving document/paragraph/text anchors |
| EvalRun / EvalResult | Separate quality/retrieval metrics, coverage, source/config snapshots and human judge labels |
| AgentRun / AgentStep | Bounded plan, execution state, tool calls/results and timing |
| ObligationExtractionRecord | Resumable content/prompt-keyed extraction state, including zero-result and review records |
| Obligation | Structured duty, source quotation, support and human confirmation |
| GapAnalysisRun / GapFinding | Selected scope, automated findings, preserved evidence and human review |

Migrations 0002 and 0003 add/backfill the upgrade schema without deleting history. Migration 0004 adds document version families and extraction-record review audit fields. Backfilled page values are conservative; reparsing recovers real end pages.

Re-indexing preserves IDs for unchanged positional chunks. Edited chunks may receive new IDs, so gold evidence uses resolving document/paragraph/text anchors. Source changes invalidate gold approvals. Historical records without snapshots remain available but do not acquire evidence that was never captured.

Question history is owner-scoped unless global-log permission is granted. Gap report access similarly checks ownership/global permissions. The document corpus itself is shared, not tenant-isolated. Reviewer identities/timestamps and configuration review histories preserve human provenance; automated extraction never substitutes for a reviewer.
