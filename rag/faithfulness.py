from .generator import structured_call, GenerationError
from .schemas import SupportJudgment
from .prompts import SUPPORT


def check_claims(answer, chunks, api_key=None):
    sources = {c['chunk_id']: c for c in chunks}
    if not answer.claims:
        return dict(claims=[], faithfulness=None, citation_precision=None, supported=False, unavailable=False, metadata={})
    checks, valid = [], []
    for claim in answer.claims:
        item = claim.model_dump()
        if any(i not in sources for i in claim.supporting_chunk_ids):
            checks.append(dict(claim_id=claim.claim_id, status='unsupported',
                               explanation='Citation was not included in retrieved context.', supporting_chunk_ids=[]))
        else:
            valid.append(dict(**item, passages=[sources[i] for i in claim.supporting_chunk_ids]))
    unavailable, metadata = False, {}
    if valid:
        try:
            judged, metadata = structured_call(SUPPORT, {'claims': valid}, SupportJudgment, judge=True, api_key=api_key)
            mapping = {c.claim_id: c for c in answer.claims}
            if len(judged.claims) != len(valid) or {c.claim_id for c in judged.claims} != {c['claim_id'] for c in valid}:
                raise GenerationError('Incomplete claim judgments')
            for item in judged.claims:
                if not set(item.supporting_chunk_ids).issubset(mapping[item.claim_id].supporting_chunk_ids):
                    raise GenerationError('Judge invented supporting citations')
                if item.status == 'supported' and not item.supporting_chunk_ids:
                    raise GenerationError('Support judgment has no supporting citations')
            checks.extend(c.model_dump() for c in judged.claims)
        except GenerationError:
            unavailable = True
            checks.extend(dict(claim_id=c['claim_id'], status='unavailable',
                               explanation='Semantic validation unavailable.', supporting_chunk_ids=[]) for c in valid)
    supported = sum(c['status'] == 'supported' for c in checks)
    citations = sum(len(set(c.supporting_chunk_ids)) for c in answer.claims)
    support_count = sum(len(set(c['supporting_chunk_ids'])) for c in checks if c['status'] in ('supported', 'partial'))
    return dict(claims=checks, faithfulness=None if unavailable else supported / len(answer.claims),
                citation_precision=None if unavailable else support_count / citations,
                supported=supported == len(answer.claims), unavailable=unavailable, metadata=metadata)
