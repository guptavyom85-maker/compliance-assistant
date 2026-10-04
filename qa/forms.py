import hashlib
import os
import fitz
from django import forms
from django.conf import settings
from .models import Document

def validate_pdf(upload):
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    upload.seek(0)
    data = upload.read(limit + 1)
    upload.seek(0)
    if len(data) > limit:
        raise forms.ValidationError(f'PDF exceeds the {settings.MAX_UPLOAD_MB} MB limit.')
    if not data.startswith(b'%PDF-'):
        raise forms.ValidationError('The file must have a valid PDF signature.')
    mime = getattr(upload, 'content_type', None)
    if mime and mime not in ('application/pdf', 'application/octet-stream'):
        raise forms.ValidationError('Unsupported upload content type.')
    try:
        with fitz.open(stream=data, filetype='pdf') as pdf:
            if pdf.needs_pass:
                raise forms.ValidationError('Encrypted PDFs are not supported.')
            if not 0 < len(pdf) <= settings.MAX_PDF_PAGES:
                raise forms.ValidationError(f'PDF must have 1–{settings.MAX_PDF_PAGES} pages.')
            if not any(page.get_text().strip() for page in pdf):
                raise forms.ValidationError('No readable text found. OCR is not enabled.')
            return hashlib.sha256(data).hexdigest(), len(pdf)
    except forms.ValidationError:
        raise
    except Exception as exc:
        raise forms.ValidationError('The PDF could not be parsed.') from exc

class QuestionForm(forms.Form):
    question = forms.CharField(max_length=settings.MAX_QUESTION_CHARS, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}))
    retrieval = forms.ChoiceField(choices=[('dense', 'Semantic search'), ('hybrid', 'Combined search'),
        ('hybrid_rerank', 'Combined search with passage ranking')], required=False)
    strategy = forms.ChoiceField(choices=[('auto', 'Automatic'), ('direct', 'Single search'),
        ('agent', 'Multi-step evidence search')], required=False)

class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'file', 'document_type', 'regulator', 'source_category', 'status',
                  'source_url', 'publication_date', 'effective_date', 'version_label', 'version_family', 'printed_page_offset']
        widgets = {'publication_date': forms.DateInput(attrs={'type': 'date'}),
                   'effective_date': forms.DateInput(attrs={'type': 'date'})}

    def clean_file(self):
        upload = self.cleaned_data['file']
        digest, pages = validate_pdf(upload)
        if Document.objects.filter(sha256=digest).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This PDF has already been uploaded.')
        self.instance.sha256, self.instance.page_count = digest, pages
        self.instance.original_filename = os.path.basename(upload.name.replace('\\', '/'))[:255]
        return upload
