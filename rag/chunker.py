import fitz
import re

def chunk_pdf(pdf_path: str, document_title: str = '') -> list[dict]:
    """
    Parses a PDF and splits it into chunks based on regulatory paragraph/clause structures.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise ValueError(f"Failed to open PDF {pdf_path}: {e}")
        
    chunks = []
    
    clause_pattern = re.compile(r'^(?:\d+(?:\.\d+)*\.?|\([a-z]\)|\([ivx]+\))\s+', re.IGNORECASE)
    
    current_chunk = None
    chunk_index = 0
    
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        text = page.get_text("text")
        
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            match = clause_pattern.match(line)
            if match:
                if current_chunk:
                    chunks.append(current_chunk)
                    chunk_index += 1
                
                paragraph_id = match.group(0).strip()
                current_chunk = {
                    'text': line,
                    'paragraph_id': paragraph_id,
                    'page_number': page_num + 1,
                    'chunk_index': chunk_index,
                    'metadata': {
                        'document_title': document_title
                    }
                }
            else:
                if current_chunk:
                    current_chunk['text'] += ' ' + line
                else:
                    current_chunk = {
                        'text': line,
                        'paragraph_id': 'Introduction',
                        'page_number': page_num + 1,
                        'chunk_index': chunk_index,
                        'metadata': {
                            'document_title': document_title
                        }
                    }
                    
    if current_chunk:
        chunks.append(current_chunk)
        
    processed_chunks = []
    for chunk in chunks:
        chunk['text'] = chunk['text'].strip()
        if not chunk['text']:
            continue
            
        if len(chunk['text']) < 50 and processed_chunks:
            prev = processed_chunks[-1]
            prev['text'] += ' ' + chunk['text']
        else:
            processed_chunks.append(chunk)
            
    for i, chunk in enumerate(processed_chunks):
        chunk['chunk_index'] = i
        
    return processed_chunks
