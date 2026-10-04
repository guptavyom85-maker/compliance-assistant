import io
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


def gap_pdf(run):
    stream = io.BytesIO()
    styles = getSampleStyleSheet()
    story = []
    def paragraph(text, style='BodyText'):
        # ReportLab paragraphs parse markup. User/model text is always escaped.
        safe = escape(str(text)).replace('₹', 'INR ').replace('\n', '<br/>')
        story.append(Paragraph(safe, styles[style]))
        story.append(Spacer(1, 8))
    paragraph(f'Policy gap report #{run.pk}', 'Title')
    paragraph(run.configuration.get('policy_title', run.policy_document.title), 'Heading1')
    paragraph(f'Created: {run.created_at.isoformat()} | Status: {run.status}')
    paragraph('Potential gaps are automated findings for human review, not a compliance certification. '
              'Only the selected policy and confirmed obligations are assessed. Missing retrieved evidence '
              'does not prove absence from the full policy or non-compliance.')
    paragraph('Summary', 'Heading1')
    paragraph(str(run.counts))
    if run.error:
        paragraph(run.error)
    for finding in run.findings.select_related('obligation'):
        paragraph(f'Finding {finding.pk}: {finding.get_effective_status_display()}', 'Heading2')
        paragraph(finding.regulatory_evidence.get('obligation_text', finding.obligation.obligation_text))
        paragraph(finding.explanation)
        for label, evidence in [('Regulatory source', finding.regulatory_evidence), ('Policy source', finding.policy_evidence)]:
            paragraph(label, 'Heading3')
            if evidence:
                paragraph(f"{evidence.get('document_title', '')} | Paragraph {evidence.get('paragraph_id', '')} | "
                          f"PDF {evidence.get('start_page', '')}-{evidence.get('end_page', '')} | Printed {evidence.get('printed_pages', '')}")
                paragraph(evidence.get('text', ''))
            else:
                paragraph('No matching source passage available.')
        paragraph(f'Human review: {finding.review_status}. {finding.reviewer_notes}')
    paragraph('Configuration and limitations', 'Heading1')
    paragraph(f'Corpus fingerprint: {run.corpus_fingerprint}')
    paragraph(str(run.configuration))
    paragraph('Models and prompts are recorded with individual findings. Re-run when source documents change. '
              'The report preserves evidence snapshots from the analysis date.')
    def footer(canvas, document):
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.grey)
        canvas.drawString(40, 25, f'Compliance Assistant | Page {document.page}')
    SimpleDocTemplate(stream, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=45).build(
        story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
