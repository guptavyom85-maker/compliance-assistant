# Security and governance

Viewer users can ask questions, inspect their own logs and read the shared corpus. Contributors additionally upload/index, extract/review obligations and run gap analyses. Administrators delete sources, manage index state, review gold questions, run evaluation, inspect global analytics and resolve the unified review queue. Permissions are checked by the server. `bootstrap_roles` does not assign users or grant staff status.

The agent has schema-validated, read-only evidence tools, call/subquestion limits and process-enforced time budgets. It cannot execute arbitrary code or browse arbitrary URLs. Obligation confirmation requires a human reviewer and supported source quote; gap reports preserve evidence and original automated results alongside human reviews. Report text is escaped before PDF rendering. These controls have regression coverage, not a comprehensive independent security audit.

PDF handling verifies byte size, signature, supported MIME, parser readability, page count, encryption state and extractable text. Uploaded documents are private to authenticated users through application routes. Deployments must not expose the media directory directly. The application currently has one shared corpus; organization-level isolation is not implemented.

Corpus changes use a filesystem lock and new immutable index generations. An interrupted rebuild cannot quietly make stale vectors eligible for retrieval. Old generations and uploaded bytes remain recoverable; no retention deletion runs automatically.

LLM prompts isolate source text as untrusted JSON data. Outputs are schema-validated with one repair attempt. Claims cite server-supplied chunk IDs; the server validates membership and judges support. API/provider failures are sanitized. These controls reduce exposure, but live prompt-injection robustness has not yet been established.

Queries and source excerpts are submitted to the configured model provider. Administrators should confirm that this processing is suitable before uploading private company material. Query/evaluation records and backups also contain content and need appropriate storage access and retention policies.

Production requires a strong secret, explicit hosts, HTTPS and secure cookies, and a trusted reverse-proxy configuration when applicable. Django deployment checks have been exercised with temporary production settings; this is not a production deployment or a comprehensive security audit.

The product displays a scope statement on the question/answer screens. Source category and status are shown beside evidence. A consultation paper or statistical report does not automatically establish a binding obligation. Unsupported or unvalidated answers require review; support labels are automated judgments, not legal advice or compliance certification.
