import os
import uuid
import zipfile
import xml.etree.ElementTree as ET
import shutil
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse, FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from docx import Document as DocxDocument
from .models import Document, Paragraph, Comment
from .serializers import DocumentSerializer

class UploadDocumentView(APIView):
    parser_classes = [MultiPartParser]

    def extract_comments_from_docx(self, file_path):
        comments_data = []
        
        try:
            with zipfile.ZipFile(file_path, 'r') as docx_zip:
                if 'word/comments.xml' not in docx_zip.namelist():
                    print("No comments found in document")
                    return comments_data
                
                comments_xml = docx_zip.read('word/comments.xml')
                root = ET.fromstring(comments_xml)
                
                namespaces = {
                    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
                }
                
                for comment in root.findall('.//w:comment', namespaces):
                    comment_id = comment.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id')
                    author = comment.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}author', 'Unknown')
                    date = comment.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}date', '')
                    
                    comment_text = ""
                    for p in comment.findall('.//w:p', namespaces):
                        para_text = ""
                        for t in p.findall('.//w:t', namespaces):
                            if t.text:
                                para_text += t.text
                        if para_text.strip():
                            comment_text += para_text + "\n"
                    
                    comment_text = comment_text.strip()
                    
                    if comment_text:
                        paragraph_id = self.find_comment_paragraph_id(docx_zip, comment_id, namespaces)
                        
                        comments_data.append({
                            'comment_id': comment_id,
                            'author': author,
                            'text': comment_text,
                            'date': date,
                            'paragraph_id': paragraph_id
                        })
        
        except Exception as e:
            print(f"Error extracting comments: {e}")
            
        return comments_data

    def find_comment_paragraph_id(self, docx_zip, comment_id, namespaces):
        try:
            document_xml = docx_zip.read('word/document.xml')
            root = ET.fromstring(document_xml)
            
            paragraph_counter = 0
            
            for para in root.findall('.//w:p', namespaces):
                para_text = ""
                for t in para.findall('.//w:t', namespaces):
                    if t.text:
                        para_text += t.text
                
                if para_text.strip():
                    paragraph_counter += 1
                    
                    comment_refs = para.findall(f'.//w:commentReference[@w:id="{comment_id}"]', namespaces)
                    comment_starts = para.findall(f'.//w:commentRangeStart[@w:id="{comment_id}"]', namespaces)
                    
                    if comment_refs or comment_starts:
                        return paragraph_counter
            
        except Exception as e:
            print(f"Error finding comment paragraph: {e}")
        
        return 1

    def post(self, request):
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        if not file.name.endswith('.docx'):
            return Response({'error': 'Only .docx files are allowed'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Save file
        filename = f"{uuid.uuid4()}_{file.name}"
        file_path = os.path.join(settings.MEDIA_ROOT, filename)
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        try:
            doc = DocxDocument(file_path)
            document = Document.objects.create(filename=file.name, file_path=file_path)
            
            paragraphs_data = []
            paragraph_objects = {}
            
            for i, para in enumerate(doc.paragraphs):
                if para.text.strip():
                    paragraph = Paragraph.objects.create(
                        document=document,
                        paragraph_id=i + 1,
                        text=para.text
                    )
                    paragraph_objects[i + 1] = paragraph
                    paragraphs_data.append({
                        'id': i + 1,
                        'text': para.text
                    })

            comments_data = []
            extracted_comments = self.extract_comments_from_docx(file_path)
            
            for comment_data in extracted_comments:
                try:
                    paragraph_id = int(comment_data['paragraph_id'])
                    paragraph = paragraph_objects.get(paragraph_id)
                    
                    if paragraph:
                        comment_obj = Comment.objects.create(
                            document=document,
                            paragraph=paragraph,
                            comment_id=int(comment_data['comment_id']),
                            author=comment_data['author'],
                            text=comment_data['text']
                        )
                        comments_data.append({
                            'id': comment_obj.comment_id,
                            'author': comment_obj.author,
                            'text': comment_obj.text,
                            'paragraph_id': paragraph_id
                        })
                        
                except Exception as e:
                    print(f"Error creating comment: {e}")
                    continue
        
            return Response({
                'document_id': document.id,
                'paragraphs': paragraphs_data,
                'comments': comments_data
            })
            
        except Exception as e:
            print(f"Error parsing document: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
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
            
            # Get next comment ID
            existing_comments = Comment.objects.filter(document=document)
            next_comment_id = max([c.comment_id for c in existing_comments] + [0]) + 1
            
            # Create comment in database
            comment = Comment.objects.create(
                document=document,
                paragraph=paragraph,
                comment_id=next_comment_id,
                author=author,
                text=text
            )
            
            # Add comment to DOCX file
            self.add_comment_to_docx(document.file_path, paragraph_id, next_comment_id, author, text)
            
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
        except Exception as e:
            print(f"Error adding comment: {e}")
            return Response({'error': f'Error adding comment: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def add_comment_to_docx(self, file_path, paragraph_id, comment_id, author, text):
        try:
            # Create a backup
            backup_path = file_path + '.backup'
            shutil.copy2(file_path, backup_path)
            
            # Extract the DOCX
            temp_dir = file_path + '_temp'
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            namespaces = {
                'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
            }
            
            # Register namespace
            ET.register_namespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
            
            # Update or create comments.xml
            comments_path = os.path.join(temp_dir, 'word', 'comments.xml')
            
            if os.path.exists(comments_path):
                # Load existing comments
                tree = ET.parse(comments_path)
                root = tree.getroot()
            else:
                # Create new comments.xml
                root = ET.Element('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}comments')
                tree = ET.ElementTree(root)
                
                # Ensure word directory exists
                os.makedirs(os.path.join(temp_dir, 'word'), exist_ok=True)
            
            # Create new comment element
            comment_elem = ET.SubElement(root, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}comment')
            comment_elem.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id', str(comment_id))
            comment_elem.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}author', author)
            comment_elem.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}date', datetime.now().isoformat())
            
            # Add comment text
            p_elem = ET.SubElement(comment_elem, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
            r_elem = ET.SubElement(p_elem, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
            t_elem = ET.SubElement(r_elem, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
            t_elem.text = text
            
            tree.write(comments_path, encoding='utf-8', xml_declaration=True)
            
            # Update document.xml to add comment reference
            self.add_comment_reference_to_document(temp_dir, paragraph_id, comment_id)
            
            # Update relationships if needed
            self.ensure_comments_relationship(temp_dir)
            
            # Recreate the DOCX file
            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                for root_dir, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path_full = os.path.join(root_dir, file)
                        arc_name = os.path.relpath(file_path_full, temp_dir)
                        zip_ref.write(file_path_full, arc_name)
            
            shutil.rmtree(temp_dir)
            os.remove(backup_path)
            
        except Exception as e:
            # Restore backup if something went wrong
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, file_path)
                os.remove(backup_path)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise e

    def add_comment_reference_to_document(self, temp_dir, paragraph_id, comment_id):
        document_path = os.path.join(temp_dir, 'word', 'document.xml')
        
        if not os.path.exists(document_path):
            return
        
        ET.register_namespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
        
        tree = ET.parse(document_path)
        root = tree.getroot()
        
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        # Find the target paragraph
        paragraphs = root.findall('.//w:p', namespaces)
        paragraph_counter = 0
        
        for para in paragraphs:
            # Check if paragraph has text content
            para_text = ""
            for t in para.findall('.//w:t', namespaces):
                if t.text:
                    para_text += t.text
            
            if para_text.strip():
                paragraph_counter += 1
                
                if paragraph_counter == paragraph_id:
                    # Find the first run in the paragraph
                    first_run = para.find('.//w:r', namespaces)
                    if first_run is not None:
                        # Add comment range start
                        comment_start = ET.Element('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}commentRangeStart')
                        comment_start.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id', str(comment_id))
                        para.insert(0, comment_start)
                        
                        # Add comment range end
                        comment_end = ET.Element('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}commentRangeEnd')
                        comment_end.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id', str(comment_id))
                        para.append(comment_end)
                        
                        # Add comment reference
                        comment_ref_run = ET.Element('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
                        comment_ref = ET.SubElement(comment_ref_run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}commentReference')
                        comment_ref.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id', str(comment_id))
                        para.append(comment_ref_run)
                    
                    break
        
        tree.write(document_path, encoding='utf-8', xml_declaration=True)

    def ensure_comments_relationship(self, temp_dir):
        rels_path = os.path.join(temp_dir, 'word', '_rels', 'document.xml.rels')
        
        if not os.path.exists(rels_path):
            # Create the _rels directory and file if it doesn't exist
            os.makedirs(os.path.dirname(rels_path), exist_ok=True)
            
            # Create basic relationships file
            rels_root = ET.Element('Relationships')
            rels_root.set('xmlns', 'http://schemas.openxmlformats.org/package/2006/relationships')
        else:
            tree = ET.parse(rels_path)
            rels_root = tree.getroot()
        
        comments_rel_exists = False
        for rel in rels_root.findall('.//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
            if rel.get('Target') == 'comments.xml':
                comments_rel_exists = True
                break
        
        if not comments_rel_exists:
            rel_elem = ET.SubElement(rels_root, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship')
            # Generate a unique relationship ID
            existing_ids = [rel.get('Id', '') for rel in rels_root.findall('.//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship')]
            rel_id = f"rId{max([int(rid[3:]) for rid in existing_ids if rid.startswith('rId') and rid[3:].isdigit()] + [0]) + 1}"
            
            rel_elem.set('Id', rel_id)
            rel_elem.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments')
            rel_elem.set('Target', 'comments.xml')
            
            # Save the relationships file
            ET.register_namespace('', 'http://schemas.openxmlformats.org/package/2006/relationships')
            tree = ET.ElementTree(rels_root)
            tree.write(rels_path, encoding='utf-8', xml_declaration=True)


class ExportDocumentView(APIView):
    def get(self, request, document_id):
        try:
            document = Document.objects.get(id=document_id)
            
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