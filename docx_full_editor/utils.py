from docx_editor.models import Document, Paragraph, Comment

def make_document_editable(document_id):
    """Make a document editable and return it"""
    try:
        document = Document.objects.get(id=document_id)
        if not document.is_editable:
            document.is_editable = True
            document.save()
        return document
    except Document.DoesNotExist:
        return None