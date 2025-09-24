import os
from django.conf import settings
from django.http import FileResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from docx_editor.models import Document, Paragraph, Comment
from docx_editor.serializers import DocumentSerializer
from docx_editor.views import (
    UploadDocumentView as BaseUploadView,
    EditParagraphView as BaseEditParagraphView,
    AddParagraphView as BaseAddParagraphView,
    DeleteParagraphView as BaseDeleteParagraphView,
    AddCommentView as BaseAddCommentView
)
from .utils import make_document_editable

class ListDocumentsView(APIView):
    def get(self, request):
        # List all documents
        documents = Document.objects.all()
        serializer = DocumentSerializer(documents, many=True)
        return Response(serializer.data)

class EditorUploadDocumentView(BaseUploadView):
    def post(self, request):
        # Reuse the base upload functionality
        response = super().post(request)
        
        if response.status_code == status.HTTP_200_OK:
            # Update the document to be editable
            document = Document.objects.get(id=response.data['document_id'])
            document.is_editable = True
            document.save()
        
        return response

class EditDocumentView(APIView):
    def get(self, request, document_id):
        document = make_document_editable(document_id)
        if not document:
            return Response({'error': 'Document not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
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
            'filename': document.filename,
            'paragraphs': paragraphs_data,
            'comments': comments_data
        })

class EditParagraphView(BaseEditParagraphView):
    def put(self, request):
        document_id = request.data.get('document_id')
        document = make_document_editable(document_id)
        if not document:
            return Response({'error': 'Document not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        return super().put(request)

class AddParagraphView(BaseAddParagraphView):
    def post(self, request):
        document_id = request.data.get('document_id')
        document = make_document_editable(document_id)
        if not document:
            return Response({'error': 'Document not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        return super().post(request)

class DeleteParagraphView(BaseDeleteParagraphView):
    def delete(self, request):
        document_id = request.data.get('document_id')
        document = make_document_editable(document_id)
        if not document:
            return Response({'error': 'Document not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        return super().delete(request)

class AddCommentView(BaseAddCommentView):
    def post(self, request):
        document_id = request.data.get('document_id')
        document = make_document_editable(document_id)
        if not document:
            return Response({'error': 'Document not found'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        return super().post(request)

class ExportDocumentView(APIView):
    def get(self, request, document_id):
        try:
            print(f"Attempting to export document {document_id}")
            document = make_document_editable(document_id)
            if not document:
                print(f"Document {document_id} not found")
                return Response({'error': 'Document not found'}, 
                              status=status.HTTP_404_NOT_FOUND)
            
            # Ensure filename has .docx extension
            export_filename = document.filename
            if not export_filename.lower().endswith('.docx'):
                export_filename += '.docx'
            
            print(f"Checking file path: {document.file_path}")
            if os.path.exists(document.file_path):
                try:
                    print(f"Opening file for export")
                    response = FileResponse(
                        open(document.file_path, 'rb'),
                        as_attachment=True,
                        filename=f"edited_{export_filename}",
                        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    )
                    print(f"File response created successfully")
                    return response
                except Exception as e:
                    print(f"Error creating FileResponse: {str(e)}")
                    return Response({'error': f'Error reading file: {str(e)}'}, 
                                  status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                print(f"File not found at path: {document.file_path}")
                return Response({'error': f'File not found at path: {document.file_path}'}, 
                              status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Unexpected error in export: {str(e)}")
            return Response({'error': f'Export error: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)