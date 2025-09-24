import os
import shutil
import uuid
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from django.conf import settings
from django.db.models import Count
from django.http import FileResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from docx import Document as DocxDocument
from .models import Document, Paragraph, Comment, DocumentImage
from .serializers import DocumentSerializer


class XMLFormattingMixin:
    """Mixin class providing XML formatting methods for DOCX processing"""
    
    def _write_xml_with_proper_formatting(self, tree, file_path):
        """Write XML with proper formatting to avoid corruption"""
        try:
            import xml.dom.minidom
            
            # First write to get XML content
            rough_string = ET.tostring(tree.getroot(), encoding='unicode')
            
            # Add proper XML declaration for Word compatibility
            xml_content = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + rough_string
            
            # Parse and prettify with minidom
            dom = xml.dom.minidom.parseString(xml_content.encode('utf-8'))
            pretty_xml = dom.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')
            
            # Clean up extra blank lines that minidom adds
            lines = [line for line in pretty_xml.split('\n') if line.strip()]
            clean_pretty_xml = '\n'.join(lines)
            
            # Ensure XML declaration is Word-compatible
            if clean_pretty_xml.startswith('<?xml version="1.0" encoding="utf-8"?>'):
                clean_pretty_xml = clean_pretty_xml.replace(
                    '<?xml version="1.0" encoding="utf-8"?>',
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                )
            elif clean_pretty_xml.startswith('<?xml version="1.0"?>'):
                clean_pretty_xml = clean_pretty_xml.replace(
                    '<?xml version="1.0"?>',
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                )
            
            # Write the properly formatted XML
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(clean_pretty_xml)
                
            # Verify the written XML is valid
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                ET.fromstring(content.encode('utf-8'))
                print(f"Successfully wrote Word-compatible XML to {os.path.basename(file_path)}")
            except ET.ParseError as e:
                print(f"Warning: Generated XML may be malformed in {file_path}: {e}")
                    
        except Exception as e:
            print(f"Error formatting XML for {file_path}: {e}")
            print("Falling back to basic XML writing...")
            # Fallback to basic writing
            tree.write(file_path, encoding='utf-8', xml_declaration=True)

    def _format_xml_file(self, file_path):
        """Format an existing XML file to have proper indentation"""
        try:
            import xml.dom.minidom
            
            # Read the existing XML
            with open(file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # Parse and prettify
            dom = xml.dom.minidom.parseString(xml_content.encode('utf-8'))
            pretty_xml = dom.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')
            
            # Clean up extra blank lines
            lines = [line for line in pretty_xml.split('\n') if line.strip()]
            clean_pretty_xml = '\n'.join(lines)
            
            # Ensure XML declaration is Word-compatible
            if clean_pretty_xml.startswith('<?xml version="1.0" encoding="utf-8"?>'):
                clean_pretty_xml = clean_pretty_xml.replace(
                    '<?xml version="1.0" encoding="utf-8"?>',
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                )
            elif clean_pretty_xml.startswith('<?xml version="1.0"?>'):
                clean_pretty_xml = clean_pretty_xml.replace(
                    '<?xml version="1.0"?>',
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                )
            
            # Write back the formatted XML
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(clean_pretty_xml)
                
            return True
            
        except Exception as e:
            print(f"Error formatting {file_path}: {e}")
            return False

    def _recreate_docx_with_proper_xml_formatting(self, file_path, temp_dir):
        """Recreate DOCX ensuring all XML files are properly formatted"""
        try:
            import xml.dom.minidom
            
            print("Formatting all XML files for Word compatibility...")
            
            # Find all XML files in the temp directory
            xml_files = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.xml'):
                        xml_files.append(os.path.join(root, file))
            
            print(f"Found {len(xml_files)} XML files to format")
            
            # Format each XML file
            for xml_file in xml_files:
                rel_path = os.path.relpath(xml_file, temp_dir).replace('\\', '/')
                
                # Check if file was already formatted by checking if it has proper indentation
                try:
                    with open(xml_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Check if already properly formatted (has multiple lines and indentation)
                    if content.count('\n') > 5 and ('  <' in content or '    <' in content):
                        print(f"  {rel_path}: Already properly formatted")
                        continue
                    
                    # Format the file
                    success = self._format_xml_file(xml_file)
                    if success:
                        print(f"  {rel_path}: Formatted successfully")
                    else:
                        print(f"  {rel_path}: Formatting failed, kept original")
                        
                except Exception as e:
                    print(f"  {rel_path}: Error checking/formatting - {e}")
            
            print("Recreating DOCX with formatted XML files...")
            
            # Recreate the DOCX file
            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as docx_out:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path_full = os.path.join(root, file)
                        # Use forward slashes for archive names (ZIP standard)
                        archive_name = os.path.relpath(file_path_full, temp_dir).replace('\\', '/')
                        docx_out.write(file_path_full, archive_name)
            
            print("DOCX recreation completed with properly formatted XML")
            return True
            
        except Exception as e:
            print(f"Error recreating DOCX with proper XML formatting: {e}")
            return False


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
            return Response({
                'status': 'error',
                'message': 'No file provided',
                'code': 'no_file'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        if not file.name.endswith('.docx'):
            return Response({
                'status': 'error',
                'message': 'Only .docx files are allowed',
                'code': 'invalid_file_type'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save file
        filename = f"{uuid.uuid4()}_{file.name}"
        file_path = os.path.join(settings.MEDIA_ROOT, filename)
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        try:
            # Create document instance
            document = Document.objects.create(
                filename=file.name,
                file_path=file_path,
                is_editable=True  # Make all documents editable
            )
            
            # Use enhanced parser
            from .docx_parser import EnhancedDocxParser
            parser = EnhancedDocxParser(file_path, document)
            paragraphs_data = parser.parse_document()
            
            # Build paragraph objects dictionary for comment linking
            paragraph_objects = {}
            for para_data in paragraphs_data:
                paragraph = Paragraph.objects.get(
                    document=document,
                    paragraph_id=para_data['id']
                )
                paragraph_objects[para_data['id']] = paragraph

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
                'status': 'success',
                'message': 'Document uploaded successfully',
                'data': {
                    'document_id': document.id,
                    'paragraphs': paragraphs_data,
                    'comments': comments_data
                }
            })
            
        except Exception as e:
            print(f"Error parsing document: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
            return Response({'error': f'Error parsing document: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EditParagraphView(XMLFormattingMixin, APIView):
    def put(self, request):
        document_id = request.data.get('document_id')
        paragraph_id = request.data.get('paragraph_id')
        new_text = request.data.get('text', '')
        
        if not all([document_id, paragraph_id]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Use get_document method if available (for full editor), otherwise use direct lookup
            if hasattr(self, 'get_document'):
                document = self.get_document(document_id)
                if not document:
                    return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
            else:
                document = Document.objects.get(id=document_id)
            
            paragraph = Paragraph.objects.get(document=document, paragraph_id=paragraph_id)
            
            # Update paragraph text in database
            paragraph.text = new_text
            paragraph.save()
            
            # Update paragraph text in DOCX file
            self.update_paragraph_in_docx(document.file_path, paragraph_id, new_text)
            
            return Response({
                'paragraph_id': paragraph.paragraph_id,
                'text': paragraph.text
            })
            
        except Document.DoesNotExist:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
        except Paragraph.DoesNotExist:
            return Response({'error': 'Paragraph not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error editing paragraph: {e}")
            return Response({'error': f'Error editing paragraph: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update_paragraph_in_docx(self, file_path, paragraph_id, new_text):
        try:
            # Debug: Check if method exists
            if not hasattr(self, '_recreate_docx_with_proper_xml_formatting'):
                print(f"ERROR: {self.__class__.__name__} does not have _recreate_docx_with_proper_xml_formatting method")
                print(f"MRO: {[cls.__name__ for cls in self.__class__.__mro__]}")
                # Fallback without XML formatting
                raise AttributeError("XML formatting method not available")
            
            # Create a backup
            backup_path = file_path + '.backup'
            shutil.copy2(file_path, backup_path)
            
            # Extract the DOCX
            temp_dir = file_path + '_temp'
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Update document.xml
            document_path = os.path.join(temp_dir, 'word', 'document.xml')
            
            if not os.path.exists(document_path):
                raise Exception("Document.xml not found")
            
            ET.register_namespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
            
            tree = ET.parse(document_path)
            root = tree.getroot()
            
            namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            
            # Find and update the target paragraph
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
                        # Clear existing text elements but preserve structure
                        runs = para.findall('.//w:r', namespaces)
                        
                        # Remove all text elements from runs
                        for run in runs:
                            text_elements = run.findall('.//w:t', namespaces)
                            for text_elem in text_elements:
                                run.remove(text_elem)
                        
                        # If no runs exist, create one
                        if not runs:
                            new_run = ET.SubElement(para, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
                            runs = [new_run]
                        
                        # Add new text to the first run
                        if new_text.strip():
                            first_run = runs[0]
                            new_text_elem = ET.SubElement(first_run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
                            new_text_elem.text = new_text
                            
                            if new_text != new_text.strip():
                                new_text_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                        
                        break
            
            tree.write(document_path, encoding='utf-8', xml_declaration=True)
            
            # Recreate the DOCX file with proper XML formatting for ALL files
            self._recreate_docx_with_proper_xml_formatting(file_path, temp_dir)
            
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


class AddParagraphView(APIView):
    def post(self, request):
        document_id = request.data.get('document_id')
        text = request.data.get('text', '')
        position = request.data.get('position')  # Optional: insert at specific position
        
        if not document_id:
            return Response({'error': 'Document ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Allow empty text for new paragraphs
        if text is None:
            text = ''
        
        try:
            document = Document.objects.get(id=document_id)
            
            # Determine the new paragraph ID
            if position and position > 0:
                new_paragraph_id = position
                # Update existing paragraphs with IDs >= position
                paragraphs_to_update = Paragraph.objects.filter(
                    document=document, 
                    paragraph_id__gte=position
                ).order_by('-paragraph_id')  # Order by descending to avoid conflicts
                
                for para in paragraphs_to_update:
                    para.paragraph_id += 1
                    para.save()
            else:
                # Add at the end
                last_paragraph = Paragraph.objects.filter(document=document).order_by('-paragraph_id').first()
                new_paragraph_id = (last_paragraph.paragraph_id + 1) if last_paragraph else 1
            
            # Create paragraph in database
            paragraph = Paragraph.objects.create(
                document=document,
                paragraph_id=new_paragraph_id,
                text=text
            )
            
            # Add paragraph to DOCX file
            self.add_paragraph_to_docx(document.file_path, new_paragraph_id, text, position)
            
            return Response({
                'paragraph_id': paragraph.paragraph_id,
                'text': paragraph.text,
                'message': 'Paragraph added successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Document.DoesNotExist:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error adding paragraph: {e}")
            import traceback
            traceback.print_exc()  # for debigging
            return Response({'error': f'Error adding paragraph: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def add_paragraph_to_docx(self, file_path, paragraph_id, text, position=None):
        backup_path = None
        temp_dir = None
        
        try:
            # Create a backup
            backup_path = file_path + '.backup'
            shutil.copy2(file_path, backup_path)
            
            # Extract the DOCX
            temp_dir = file_path + '_temp'
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Update document.xml
            document_path = os.path.join(temp_dir, 'word', 'document.xml')
            
            if not os.path.exists(document_path):
                raise Exception(f"Document.xml not found at {document_path}")
            
            # Register namespace to preserve XML structure
            ET.register_namespace('', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
            ET.register_namespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
            
            tree = ET.parse(document_path)
            root = tree.getroot()
            
            namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            
            # Create new paragraph element with proper namespace
            w_ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            new_para = ET.Element(f'{w_ns}p')
            new_run = ET.SubElement(new_para, f'{w_ns}r')
            new_text_elem = ET.SubElement(new_run, f'{w_ns}t')
            new_text_elem.text = text if text.strip() else ' '  # Ensure at least a space
            
            # Find the body element
            body = root.find('.//w:body', namespaces)
            if body is None:
                raise Exception("Document body not found")
            
            if position and position > 0:
                # Insert at specific position
                all_paragraphs = body.findall('w:p', namespaces)
                
                # Count only non-empty paragraphs to match our numbering system
                non_empty_count = 0
                insert_index = len(all_paragraphs)  # Default to end
                
                for i, para in enumerate(all_paragraphs):
                    # Check if paragraph has text content
                    para_text = ""
                    for t in para.findall('.//w:t', namespaces):
                        if t.text:
                            para_text += t.text
                    
                    if para_text.strip():
                        non_empty_count += 1
                        
                    if non_empty_count == position - 1:
                        insert_index = i + 1
                        break
                
                body.insert(insert_index, new_para)
            else:
                # Add at the end
                body.append(new_para)
            
            tree.write(document_path, encoding='utf-8', xml_declaration=True)
            
            # Recreate the DOCX file
            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_ref:
                for root_dir, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path_full = os.path.join(root_dir, file)
                        arc_name = os.path.relpath(file_path_full, temp_dir)
                        zip_ref.write(file_path_full, arc_name)
                zip_ref.close()
            import time
            time.sleep(0.5)  # Ensure file system has settled
            
            # Cleanup
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            if backup_path and os.path.exists(backup_path):
                os.remove(backup_path)
            
        except Exception as e:
            # Restore backup if something went wrong
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, file_path)
                os.remove(backup_path)
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise e


@method_decorator(csrf_exempt, name='dispatch')
class DeleteParagraphView(APIView):
    def delete(self, request):
        # Parse JSON data using DRF's request.data instead of raw request.body
        try:
            data = request.data
            document_id = data.get('document_id')
            paragraph_id = data.get('paragraph_id')
        except (AttributeError, ValueError) as e:
            return Response({'error': 'Invalid JSON in request data'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not all([document_id, paragraph_id]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            document = Document.objects.get(id=document_id)
            paragraph = Paragraph.objects.get(document=document, paragraph_id=paragraph_id)
            
            # Check if this is the last paragraph
            total_paragraphs = Paragraph.objects.filter(document=document).count()
            if total_paragraphs <= 1:
                return Response({'error': 'Cannot delete the last paragraph'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Delete associated comments first
            deleted_comments = Comment.objects.filter(paragraph=paragraph)
            comment_count = deleted_comments.count()
            deleted_comments.delete()
            
            # Delete paragraph from DOCX file first (so we can restore if DB update fails)
            self.delete_paragraph_from_docx(document.file_path, paragraph_id)
            
            # Delete paragraph from database
            paragraph.delete()
            
            # Update paragraph IDs for paragraphs that come after the deleted one
            paragraphs_to_update = Paragraph.objects.filter(
                document=document, 
                paragraph_id__gt=paragraph_id
            ).order_by('paragraph_id')
            
            for para in paragraphs_to_update:
                para.paragraph_id -= 1
                para.save()
            
            # Also update comment references
            comments_to_update = Comment.objects.filter(
                document=document,
                paragraph__paragraph_id__gt=paragraph_id - 1  # After the shift
            )
            
            for comment in comments_to_update:
                # Find the paragraph with the updated ID
                try:
                    comment.paragraph = Paragraph.objects.get(
                        document=document,
                        paragraph_id=comment.paragraph.paragraph_id
                    )
                    comment.save()
                except Paragraph.DoesNotExist:
                    comment.delete()  # Remove orphaned comments
            
            return Response({
                'message': 'Paragraph deleted successfully',
                'deleted_comments': comment_count,
                'updated_paragraphs': paragraphs_to_update.count()
            })
            
        except Document.DoesNotExist:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
        except Paragraph.DoesNotExist:
            return Response({'error': 'Paragraph not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error deleting paragraph: {e}")
            import traceback
            traceback.print_exc()
            return Response({'error': f'Error deleting paragraph: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete_paragraph_from_docx(self, file_path, paragraph_id):
        backup_path = None
        temp_dir = None
        
        try:
            # Create a backup
            backup_path = file_path + '.backup'
            shutil.copy2(file_path, backup_path)
            
            # Extract the DOCX
            temp_dir = file_path + '_temp'
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Update document.xml
            document_path = os.path.join(temp_dir, 'word', 'document.xml')
            
            if not os.path.exists(document_path):
                raise Exception(f"Document.xml not found at {document_path}")
            
            # Register namespaces
            ET.register_namespace('', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
            ET.register_namespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
            
            tree = ET.parse(document_path)
            root = tree.getroot()
            
            namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            
            # Find the body element first
            body = root.find('.//w:body', namespaces)
            if body is None:
                raise Exception("Document body not found")
            
            # Find and delete the target paragraph
            paragraphs = body.findall('w:p', namespaces)  # Direct children of body
            paragraph_counter = 0
            paragraph_deleted = False
            
            for i, para in enumerate(paragraphs):
                # Check if paragraph has text content
                para_text = ""
                for t in para.findall('.//w:t', namespaces):
                    if t.text:
                        para_text += t.text
                
                if para_text.strip():
                    paragraph_counter += 1
                    
                    if paragraph_counter == paragraph_id:
                        # Remove this paragraph from the body
                        body.remove(para)
                        paragraph_deleted = True
                        print(f"Deleted paragraph {paragraph_id} at position {i}")
                        break
            
            if not paragraph_deleted:
                raise Exception(f"Paragraph {paragraph_id} not found in document")
            
            # Write the updated XML
            tree.write(document_path, encoding='utf-8', xml_declaration=True)
            
            # Recreate the DOCX file
            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_ref:
                for root_dir, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path_full = os.path.join(root_dir, file)
                        arc_name = os.path.relpath(file_path_full, temp_dir)
                        zip_ref.write(file_path_full, arc_name)
            
            # Cleanup
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            if backup_path and os.path.exists(backup_path):
                os.remove(backup_path)
            
        except Exception as e:
            # Restore backup if something went wrong
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, file_path)
                os.remove(backup_path)
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise e
        
class AddCommentView(XMLFormattingMixin, APIView):
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
            
            # Write XML with proper formatting
            self._write_xml_with_proper_formatting(tree, comments_path)
            
            # Update document.xml to add comment reference
            self.add_comment_reference_to_document(temp_dir, paragraph_id, comment_id)
            
            # Update relationships if needed
            self.ensure_comments_relationship(temp_dir)
            
            # Ensure comments content type is registered
            self.ensure_comments_content_type(temp_dir)
            
            # Recreate the DOCX file with proper XML formatting for ALL files
            self._recreate_docx_with_proper_xml_formatting(file_path, temp_dir)
            
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
            self._write_xml_with_proper_formatting(tree, rels_path)

    def ensure_comments_content_type(self, temp_dir):
        """Ensure comments.xml is registered in [Content_Types].xml"""
        content_types_path = os.path.join(temp_dir, '[Content_Types].xml')
        
        if not os.path.exists(content_types_path):
            return
        
        try:
            tree = ET.parse(content_types_path)
            root = tree.getroot()
            
            # Check if comments content type already exists
            namespaces = {'ct': 'http://schemas.openxmlformats.org/package/2006/content-types'}
            existing = root.find(".//ct:Override[@PartName='/word/comments.xml']", namespaces)
            
            if existing is None:
                # Add the comments content type
                override_elem = ET.SubElement(root, '{http://schemas.openxmlformats.org/package/2006/content-types}Override')
                override_elem.set('PartName', '/word/comments.xml')
                override_elem.set('ContentType', 'application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml')
                
                # Save the content types file
                ET.register_namespace('', 'http://schemas.openxmlformats.org/package/2006/content-types')
                self._write_xml_with_proper_formatting(tree, content_types_path)
                
        except Exception as e:
            print(f"Error updating content types: {e}")


@method_decorator(csrf_exempt, name='dispatch')
class DeleteCommentView(XMLFormattingMixin, APIView):
    def delete(self, request):
        # Parse JSON data from request body for DELETE requests
        try:
            data = request.data
            document_id = data.get('document_id')
            comment_id = data.get('comment_id')
        except (AttributeError, ValueError) as e:
            return Response({'error': 'Invalid JSON in request data'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not all([document_id, comment_id]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            document = Document.objects.get(id=document_id)
            comment = Comment.objects.get(document=document, comment_id=comment_id)
            
            # Delete comment from DOCX file first
            self.delete_comment_from_docx(document.file_path, comment_id)
            
            # Delete comment from database
            comment.delete()
            
            return Response({
                'message': 'Comment deleted successfully',
                'comment_id': comment_id
            })
            
        except Document.DoesNotExist:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
        except Comment.DoesNotExist:
            return Response({'error': 'Comment not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error deleting comment: {e}")
            return Response({'error': f'Error deleting comment: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete_comment_from_docx(self, file_path, comment_id):
        backup_path = None
        temp_dir = None
        
        try:
            # Create a backup
            backup_path = file_path + '.backup'
            shutil.copy2(file_path, backup_path)
            
            # Extract the DOCX
            temp_dir = file_path + '_temp'
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Update comments.xml
            comments_path = os.path.join(temp_dir, 'word', 'comments.xml')
            
            if os.path.exists(comments_path):
                ET.register_namespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
                
                tree = ET.parse(comments_path)
                root = tree.getroot()
                
                namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                
                # Find and remove the comment
                comments = root.findall('.//w:comment', namespaces)
                for comment in comments:
                    if comment.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id') == str(comment_id):
                        root.remove(comment)
                        break
                
                self._write_xml_with_proper_formatting(tree, comments_path)
            
            # Remove comment references from document.xml
            self.remove_comment_references_from_document(temp_dir, comment_id)
            
            # Recreate the DOCX file with proper XML formatting for ALL files
            self._recreate_docx_with_proper_xml_formatting(file_path, temp_dir)
            
            # Cleanup
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            if backup_path and os.path.exists(backup_path):
                os.remove(backup_path)
                
        except Exception as e:
            # Restore backup if something went wrong
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, file_path)
                os.remove(backup_path)
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise e

    def remove_comment_references_from_document(self, temp_dir, comment_id):
        document_path = os.path.join(temp_dir, 'word', 'document.xml')
        
        if not os.path.exists(document_path):
            return
        
        ET.register_namespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
        
        tree = ET.parse(document_path)
        root = tree.getroot()
        
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        # Create parent map for efficient parent lookup
        parent_map = {child: parent for parent in root.iter() for child in parent}
        
        # Helper function to remove elements using parent map
        def remove_elements_by_xpath(xpath_pattern):
            elements_to_remove = root.findall(xpath_pattern, namespaces)
            for element in elements_to_remove:
                parent = parent_map.get(element)
                if parent is not None:
                    parent.remove(element)
        
        # Remove comment range starts
        remove_elements_by_xpath(f'.//w:commentRangeStart[@w:id="{comment_id}"]')
        
        # Remove comment range ends  
        remove_elements_by_xpath(f'.//w:commentRangeEnd[@w:id="{comment_id}"]')
        
        # Remove comment references
        remove_elements_by_xpath(f'.//w:commentReference[@w:id="{comment_id}"]')
        
        self._write_xml_with_proper_formatting(tree, document_path)


class ListDocumentsView(APIView):
    def get(self, request):
        # Show all documents in both interfaces
        documents = Document.objects.all()
            
        # Add comment count and order by upload date
        documents = documents.annotate(comment_count=Count('comments')).order_by('-uploaded_at')
        
        documents_data = []
        for doc in documents:
            documents_data.append({
                'id': doc.id,
                'filename': doc.filename,
                'uploaded_at': doc.uploaded_at.isoformat(),
                'comment_count': doc.comment_count
            })
        
        return Response(documents_data)

class ExportDocumentView(APIView):
    def get(self, request, document_id):
        try:
            document = Document.objects.get(id=document_id)
            print(f"Exporting document {document_id}: {document.filename}")
            print(f"File path: {document.file_path}")
            
            # Ensure filename has .docx extension
            export_filename = document.filename
            if not export_filename.lower().endswith('.docx'):
                export_filename += '.docx'
            
            if not document.file_path:
                return Response({'error': 'No file path saved for document'}, status=status.HTTP_404_NOT_FOUND)
            
            if os.path.exists(document.file_path):
                try:
                    file = open(document.file_path, 'rb')
                    response = FileResponse(
                        file,
                        as_attachment=True,
                        filename=f"updated_{export_filename}",
                        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    )
                    return response
                except PermissionError as e:
                    print(f"Permission error: {str(e)}")
                    return Response({'error': f'Permission denied: {str(e)}'}, status=status.HTTP_403_FORBIDDEN)
                except Exception as e:
                    print(f"File open error: {str(e)}")
                    return Response({'error': f'Error opening file: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                print(f"File not found at path: {document.file_path}")
                return Response({
                    'error': f'File not found at path: {document.file_path}'
                }, status=status.HTTP_404_NOT_FOUND)
                
        except Document.DoesNotExist:
            print(f"Document {document_id} not found in database")
            return Response({'error': 'Document not found in database'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Unexpected error in export: {str(e)}")
            return Response({'error': f'Export error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetDocumentView(APIView):
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
                    'paragraph_id': comment.paragraph.paragraph_id
                })
            
            return Response({
                'paragraphs': paragraphs_data,
                'comments': comments_data
            })
            
        except Document.DoesNotExist:
            return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)


class ServeImageView(APIView):
    def get(self, request, image_id):
        """Serve document images"""
        try:
            image = DocumentImage.objects.get(id=image_id)
            
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