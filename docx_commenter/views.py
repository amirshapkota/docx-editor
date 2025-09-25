import os
from django.conf import settings
from django.http import FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from docx_editor.models import Document, Paragraph, Comment, DocumentImage
from docx_editor.views import UploadDocumentView as BaseUploadView
from docx_editor.views import AddCommentView as BaseAddCommentView
from docx_editor.views import DeleteCommentView as BaseDeleteCommentView
from docx_editor.serializers import DocumentSerializer

class CommentUploadDocumentView(BaseUploadView):
    def post(self, request):
        # Reuse the base upload functionality
        response = super().post(request)
        
        if response.status_code == status.HTTP_200_OK:
            # Update the document to be comment-only
            # The response structure is: {'status': 'success', 'data': {'document_id': ...}}
            document_id = response.data['data']['document_id']
            document = Document.objects.get(id=document_id)
            document.is_editable = False
            document.save()
        
        return response

class ListDocumentsView(APIView):
    def get(self, request):
        # List all documents for commenting
        documents = Document.objects.all()
        serializer = DocumentSerializer(documents, many=True)
        return Response(serializer.data)

class ViewDocumentView(APIView):
    def get(self, request, document_id):
        try:
            document = Document.objects.get(id=document_id)
            
            paragraphs_data = []
            for para in document.paragraphs.all().order_by('paragraph_id'):
                para_data = {
                    'id': para.paragraph_id,
                    'text': para.text,
                    'html_content': para.html_content,
                    'has_images': para.has_images
                }
                
                # Add image information if paragraph has images
                if para.has_images:
                    images = []
                    for para_img in para.paragraph_images.all():
                        images.append({
                            'id': para_img.document_image.id,
                            'filename': para_img.document_image.filename,
                            'image_id': para_img.document_image.image_id,
                            'position': para_img.position_in_paragraph
                        })
                    para_data['images'] = images
                
                paragraphs_data.append(para_data)
            
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
                'document_id': document.id,
                'paragraphs': paragraphs_data,
                'comments': comments_data
            })
            
        except Document.DoesNotExist:
            return Response({'error': 'Document not found'}, 
                          status=status.HTTP_404_NOT_FOUND)

class AddCommentView(BaseAddCommentView):
    def post(self, request):
        document_id = request.data.get('document_id')
        
        try:
            # Verify document exists (allow commenting on any document)
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return Response({'error': 'Document not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        # Use the base comment functionality
        return super().post(request)


@method_decorator(csrf_exempt, name='dispatch')
class DeleteCommentView(BaseDeleteCommentView):
    def delete(self, request):
        # Parse JSON data from request body for DELETE requests
        try:
            import json
            data = json.loads(request.body.decode('utf-8'))
            document_id = data.get('document_id')
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response({'error': 'Invalid JSON in request body'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Allow deleting comments from any document
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return Response({'error': 'Document not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        # Use the base delete functionality
        return super().delete(request)


class ExportDocumentView(APIView):
    def get(self, request, document_id):
        try:
            # Allow export of any document from commenter
            document = Document.objects.get(id=document_id)
            
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
            return Response({'error': 'Document not found'}, 
                          status=status.HTTP_404_NOT_FOUND)


class ServeImageView(APIView):
    def get(self, request, image_id):
        """Serve document images for commenter"""
        try:
            image = DocumentImage.objects.get(id=image_id)
            
            # Allow serving images from any document (no access restriction)
            if os.path.exists(image.file_path):
                response = FileResponse(
                    open(image.file_path, 'rb'),
                    content_type=image.content_type
                )
                return response
            else:
                return Response({'error': 'Image file not found'}, status=status.HTTP_404_NOT_FOUND)
                
        except DocumentImage.DoesNotExist:
            return Response({'error': 'Image not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error serving image: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
