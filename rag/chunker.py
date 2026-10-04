"""Clause extraction retaining PDF spans, bounded to avoid embedding truncation."""
import hashlib
import re
import fitz

CHUNKER_VERSION = '2'
CLAUSE = re.compile(r'^(\d+(?:\.\d+)*\.?|\([a-z]+\))\s+', re.I)
STANDALONE_CLAUSE = re.compile(r'^(\d+\.\d+(?:\.\d+)*\.?|\d+\.|\([a-z]+\))$', re.I)

def chunk_pdf(pdf_path, document_title='', printed_page_offset=0):
    chunks, current = [], None
    paragraph = 'Unnumbered'
    with fitz.open(pdf_path) as pdf:
        if pdf.needs_pass:
            raise ValueError('Encrypted PDFs are not supported.')
        for page_index, page in enumerate(pdf):
            page_no = page_index + 1
            lines = [line.strip() for line in page.get_text('text').splitlines() if line.strip()]
            for line_index, line in enumerate(lines):
                # PDF extraction sometimes puts the paragraph number alone on a
                # line. Decimal markers are clauses; bare chart numbers are not.
                match = CLAUSE.match(line)
                if not match:
                    marker = STANDALONE_CLAUSE.match(line)
                    following = lines[line_index + 1] if line_index + 1 < len(lines) else ''
                    # Chart series contain many isolated decimal values. Treat a
                    # standalone marker as a clause only when prose follows it.
                    if marker and len(re.findall(r'[A-Za-z]{2,}', following)) >= 3:
                        match = marker
                if match:
                    paragraph = match.group(1)
                if current and (match or len(current['text'].split()) + len(line.split()) > 160):
                    chunks.append(current)
                    current = None
                words = line.split()
                for offset in range(0, len(words), 160):
                    fragment = ' '.join(words[offset:offset + 160])
                    if current is None:
                        current = dict(text=fragment, paragraph_id=paragraph,
                                       start_page=page_no, end_page=page_no)
                    else:
                        current['text'] += ' ' + fragment
                        current['end_page'] = page_no
                    if offset + 160 < len(words):
                        chunks.append(current)
                        current = None
    if current:
        chunks.append(current)
    for i, chunk in enumerate(chunks):
        chunk.update(chunk_index=i, page_number=chunk['start_page'],
                     printed_start_page=str(chunk['start_page'] + printed_page_offset),
                     printed_end_page=str(chunk['end_page'] + printed_page_offset),
                     content_sha256=hashlib.sha256(chunk['text'].encode()).hexdigest(),
                     chunker_version=CHUNKER_VERSION,
                     metadata={'document_title': document_title})
    return chunks
