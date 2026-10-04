"""Conservative qualitative rules. They are explicitly uncalibrated until evaluated."""


def assess(answer, support, chunks):
    if not answer.answerable:
        return 'insufficient', True, answer.reason
    if support['unavailable']:
        return 'low', True, 'Semantic validation unavailable.'
    if not support['supported']:
        return 'low', True, 'At least one claim lacks full support.'
    # Deliberately do not produce a high-confidence label before calibration.
    both = any(c.get('dense_score') is not None and c.get('bm25_score') is not None for c in chunks)
    return 'medium', False, ('All claims supported; lexical and dense retrieval agree.' if both
                             else 'All claims supported by retrieved evidence; confidence is not calibrated.')
