import os
import uuid
from django.conf import settings
from django.http import JsonResponse, FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from docx import Document as DocxDocument
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table
from docx.text.paragraph import Paragraph as DocxParagraph
from .models import Document, Paragraph, Comment
from .serializers import DocumentSerializer

class UploadDocumentView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        if not file.name.endswith('.docx'):
            return Response({'error': 'Only .docx files are allowed'}, status=status.HTTP_400_BAD_REQUEST)
        
        # save file
        filename = f"{uuid.uuid4()}_{file.name}"
        file_path = os.path.join(settings.MEDIA_ROOT, filename)
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        # parse document
        try:
            doc = DocxDocument(file_path)
            document = Document.objects.create(filename=file.name, file_path=file_path)
            
            # Extract paragraphs
            paragraphs_data = []
            comments_data = []
            
            for i, para in enumerate(doc.paragraphs):
                if para.text.strip():  # Skip empty paragraphs
                    paragraph = Paragraph.objects.create(
                        document=document,
                        paragraph_id=i + 1,
                        text=para.text
                    )
                    paragraphs_data.append({
                        'id': i + 1,
                        'text': para.text
                    })
            try:
                if hasattr(doc, 'part') and hasattr(doc.part, 'comments_part'):
                    comments_part = doc.part.comments_part
                    if comments_part:
                        for comment_id, comment in enumerate(comments_part.comments):
                            # This is simplified comment extraction
                            # In real project, we need to map comments to paragraphs
                            comment_obj = Comment.objects.create(
                                document=document,
                                paragraph=document.paragraphs.first(),  # Simplified mapping
                                comment_id=comment_id + 1,
                                author=getattr(comment, 'author', 'Unknown'),
                                text=comment.text if hasattr(comment, 'text') else str(comment)
                            )
                            comments_data.append({
                                'id': comment_id + 1,
                                'author': comment_obj.author,
                                'text': comment_obj.text,
                                'paragraph_id': 1  # Simplified
                            })
            except:
                pass
        
            return Response({
                'document_id': document.id,
                'paragraphs': paragraphs_data,
                'comments': comments_data
            })
        except Exception as e:
            return Response({'error': f'Error parsing document: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

