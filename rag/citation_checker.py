import re

def check_citations(answer: str, retrieved_chunks: list[dict]) -> dict:
    retrieved_ids = [chunk.get('paragraph_id', '') for chunk in retrieved_chunks if chunk.get('paragraph_id')]
    retrieved_ids_set = set(retrieved_ids)
    
    citation_pattern = re.compile(
        r'(?:§\s*|(?:paragraph|para|clause)\s+)([\w.()\-]+)',
        re.IGNORECASE,
    )
    cited_ids = citation_pattern.findall(answer)
    cited_ids = [cid.strip() for cid in cited_ids]
    
    unverified = []
    for cid in cited_ids:
        if cid not in retrieved_ids_set:
            unverified.append(cid)
            
    verified = bool(cited_ids) and len(unverified) == 0
    
    if verified and cited_ids:
        message = "All citations verified against retrieved context."
    elif not cited_ids:
        message = "No citations found in the answer."
    else:
        message = f"Found unverified citations: {', '.join(unverified)}"
        
    return {
        'cited_ids': cited_ids,
        'retrieved_ids': retrieved_ids,
        'verified': verified,
        'unverified_citations': unverified,
        'message': message
    }
