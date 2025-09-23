import os
from django.conf import settings
from django.http import FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from docx_editor.models import Document, Paragraph, Comment
from docx_editor.views import UploadDocumentView as BaseUploadView
from docx_editor.views import AddCommentView as BaseAddCommentView
from docx_editor.serializers import DocumentSerializer

class CommentUploadDocumentView(BaseUploadView):
    def post(self, request):
        # Reuse the base upload functionality
        response = super().post(request)
        
        if response.status_code == status.HTTP_200_OK:
            # Update the document to be comment-only
            document = Document.objects.get(id=response.data['document_id'])
            document.is_editable = False
            document.save()
        
        return response

class ListDocumentsView(APIView):
    def get(self, request):
        # Only list documents that are marked as comment-only
        documents = Document.objects.filter(is_editable=False)
        serializer = DocumentSerializer(documents, many=True)
        return Response(serializer.data)

class ViewDocumentView(APIView):
    def get(self, request, document_id):
        try:
            document = Document.objects.get(id=document_id, is_editable=False)
            
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
                    'paragraph_id': comment.paragraph.paragraph_id,
                    'created_at': comment.created_at
                })
            
            return Response({
                'paragraphs': paragraphs_data,
                'comments': comments_data
            })
            
        except Document.DoesNotExist:
            return Response({'error': 'Document not found or not accessible'}, 
                          status=status.HTTP_404_NOT_FOUND)

class AddCommentView(BaseAddCommentView):
    def post(self, request):
        document_id = request.data.get('document_id')
        
        try:
            # Verify this is a comment-only document
            document = Document.objects.get(id=document_id, is_editable=False)
        except Document.DoesNotExist:
            return Response({'error': 'Document not found or not accessible'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        # Use the base comment functionality
        return super().post(request)

class ExportDocumentView(APIView):
    def get(self, request, document_id):
        try:
            document = Document.objects.get(id=document_id, is_editable=False)
            
            if os.path.exists(document.file_path):
                response = FileResponse(
                    open(document.file_path, 'rb'),
                    as_attachment=True,
                    filename=f"commented_{document.filename}"
                )
                return response
            else:
                return Response({'error': 'File not found'}, 
                              status=status.HTTP_404_NOT_FOUND)
                
        except Document.DoesNotExist:
            return Response({'error': 'Document not found or not accessible'}, 
                          status=status.HTTP_404_NOT_FOUND)
