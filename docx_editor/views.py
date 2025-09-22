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
                            # In real project we need to map comments to paragraphs
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

class AddCommentView(APIView):
    def post(self, request):
        document_id = request.data.get('document_id')
        paragraph_id = request.data.get('paragraph_id')
        author = request.data.get('author', 'Anonymous')
        text = request.data.get('text', '')
        
        if not all([document_id, paragraph_id, text]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            document = Document.objects.get(id=document_id)
            paragraph = Paragraph.objects.get(document=document, paragraph_id=paragraph_id)
            
            # Creating comment in database
            comment_id = Comment.objects.filter(document=document).count() + 1
            comment = Comment.objects.create(
                document=document,
                paragraph=paragraph,
                comment_id=comment_id,
                author=author,
                text=text
            )
            
            # Update the docx file just saving comment in DB for now
            # In real project we need to modify the actual docx file here
            
            return Response({
                'id': comment.comment_id,
                'author': comment.author,
                'text': comment.text,
                'paragraph_id': paragraph.paragraph_id
            })
            
        except Document.DoesNotExist:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
        except Paragraph.DoesNotExist:
            return Response({'error': 'Paragraph not found'}, status=status.HTTP_404_NOT_FOUND)

class ExportDocumentView(APIView):
    def get(self, request, document_id):
        try:
            document = Document.objects.get(id=document_id)
            
            # For this we'll just return the original file
            # In a full project we need to create a new docx with comments
            if os.path.exists(document.file_path):
                response = FileResponse(
                    open(document.file_path, 'rb'),
                    as_attachment=True,
                    filename=f"updated_{document.filename}"
                )
                return response
            else:
                return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)
                
        except Document.DoesNotExist:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)

class GetDocumentView(APIView):
    def get(self, request, document_id):
        try:
            document = Document.objects.get(id=document_id)
            
            paragraphs_data = []
            for para in document.paragraphs.all().order_by('paragraph_id'):
                paragraphs_data.append({
                    'id': para.paragraph_id,
                    'text': para.text
                })
            
            comments_data = []
            for comment in document.comments.all():
                comments_data.append({
                    'id': comment.comment_id,
                    'author': comment.author,
                    'text': comment.text,
                    'paragraph_id': comment.paragraph.paragraph_id
                })
            
            return Response({
                'paragraphs': paragraphs_data,
                'comments': comments_data
            })
            
        except Document.DoesNotExist:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
