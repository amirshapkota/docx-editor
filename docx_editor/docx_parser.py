import os
import shutil
import zipfile
import xml.etree.ElementTree as ET
from django.conf import settings
from .models import Document, Paragraph, DocumentImage, ParagraphImage
import base64
import uuid
import re
from docx import Document as DocxDocument


class EnhancedDocxParser:
    """Enhanced DOCX parser that extracts images and formatting"""
    
    def __init__(self, file_path, document_instance):
        self.file_path = file_path
        self.document = document_instance
        self.temp_dir = None
        self.namespaces = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
            'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
            'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
            'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
        }
        self.image_relationships = {}
        self.extracted_images = {}
        
    def parse_document(self):
        """Main parsing method that extracts paragraphs and images"""
        try:
            # Create temp directory for extraction
            self.temp_dir = f"{self.file_path}_extract_{uuid.uuid4().hex[:8]}"
            
            # Extract DOCX contents
            with zipfile.ZipFile(self.file_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
            
            # Parse relationships to find images
            self._parse_image_relationships()
            
            # Extract images from the archive
            self._extract_images()
            
            # Parse document content
            paragraphs_data = self._parse_paragraphs()
            
            return paragraphs_data
            
        finally:
            # Cleanup temp directory
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
    
    def _parse_image_relationships(self):
        """Parse document relationships to find image references"""
        rels_path = os.path.join(self.temp_dir, 'word', '_rels', 'document.xml.rels')
        
        if not os.path.exists(rels_path):
            return
        
        try:
            tree = ET.parse(rels_path)
            root = tree.getroot()
            
            for rel in root.findall('.//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
                rel_type = rel.get('Type', '')
                if 'image' in rel_type.lower():
                    rel_id = rel.get('Id')
                    target = rel.get('Target')
                    self.image_relationships[rel_id] = target
                    
        except Exception as e:
            print(f"Error parsing relationships: {e}")
    
    def _extract_images(self):
        """Extract images from DOCX and save them to media directory"""
        media_images_dir = os.path.join(settings.MEDIA_ROOT, 'document_images', str(self.document.id))
        os.makedirs(media_images_dir, exist_ok=True)
        
        for rel_id, image_path in self.image_relationships.items():
            # Full path to image in extracted DOCX
            full_image_path = os.path.join(self.temp_dir, 'word', image_path)
            
            if os.path.exists(full_image_path):
                try:
                    # Generate unique filename
                    original_name = os.path.basename(image_path)
                    name, ext = os.path.splitext(original_name)
                    unique_filename = f"{uuid.uuid4().hex[:8]}_{name}{ext}"
                    
                    # Copy image to media directory
                    dest_path = os.path.join(media_images_dir, unique_filename)
                    shutil.copy2(full_image_path, dest_path)
                    
                    # Determine content type
                    content_type = self._get_content_type(ext.lower())
                    
                    # Create DocumentImage instance
                    doc_image = DocumentImage.objects.create(
                        document=self.document,
                        image_id=rel_id,
                        filename=original_name,
                        file_path=dest_path,
                        content_type=content_type
                    )
                    
                    self.extracted_images[rel_id] = doc_image
                    
                except Exception as e:
                    print(f"Error extracting image {image_path}: {e}")
    
    def _get_content_type(self, ext):
        """Get content type based on file extension"""
        content_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.svg': 'image/svg+xml'
        }
        return content_types.get(ext, 'image/png')
    
    def _parse_paragraphs(self):
        """Parse paragraphs with formatting and image references"""
        document_xml_path = os.path.join(self.temp_dir, 'word', 'document.xml')
        
        if not os.path.exists(document_xml_path):
            raise Exception("Document.xml not found")
        
        tree = ET.parse(document_xml_path)
        root = tree.getroot()
        
        paragraphs_data = []
        paragraph_counter = 0  # Counter for consecutive paragraph IDs in database
        
        # Find all paragraphs
        for para_elem in root.findall('.//w:p', self.namespaces):
            # Extract text and HTML content
            text_content, html_content, has_images = self._process_paragraph(para_elem)
            
            # Only create paragraph if it has content
            if text_content.strip() or has_images:
                paragraph_counter += 1  # Increment only when creating a paragraph
                paragraph = Paragraph.objects.create(
                    document=self.document,
                    paragraph_id=paragraph_counter,
                    text=text_content,
                    html_content=html_content,
                    has_images=has_images
                )
                
                # Link images to this paragraph
                self._link_paragraph_images(para_elem, paragraph)
                
                paragraphs_data.append({
                    'id': paragraph_counter,
                    'text': text_content,
                    'html_content': html_content,
                    'has_images': has_images
                })
        
        return paragraphs_data
    
    def _process_paragraph(self, para_elem):
        """Process a paragraph element to extract text, HTML, and images"""
        text_parts = []
        html_parts = []
        has_images = False
        
        # Check paragraph properties for alignment and styling
        para_props = para_elem.find('w:pPr', self.namespaces)
        alignment = None
        is_heading = False
        heading_level = None
        
        if para_props is not None:
            # Check alignment
            jc = para_props.find('w:jc', self.namespaces)
            if jc is not None:
                alignment = jc.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
            
            # Check if it's a heading (look for heading style)
            style_elem = para_props.find('w:pStyle', self.namespaces)
            if style_elem is not None:
                style_val = style_elem.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                if style_val and 'heading' in style_val.lower():
                    is_heading = True
                    # Extract heading level (e.g., "Heading1" -> 1)
                    try:
                        heading_level = int(style_val[-1]) if style_val[-1].isdigit() else 1
                    except:
                        heading_level = 1
                elif style_val in ['Title', 'Subtitle']:
                    is_heading = True
                    heading_level = 1
        
        # Process all runs in the paragraph
        for run in para_elem.findall('.//w:r', self.namespaces):
            run_text, run_html, run_has_image = self._process_run(run)
            text_parts.append(run_text)
            html_parts.append(run_html)
            if run_has_image:
                has_images = True
        
        # Join all parts
        text_content = ''.join(text_parts)
        html_content = ''.join(html_parts)
        
        # Wrap in appropriate HTML tags with formatting
        if html_content.strip():
            # Apply heading formatting
            if is_heading and heading_level:
                tag = f'h{min(heading_level, 6)}'
                html_content = f'<{tag}>{html_content}</{tag}>'
            else:
                # Regular paragraph with alignment
                style_attr = ''
                if alignment:
                    if alignment == 'center':
                        style_attr = ' style="text-align: center;"'
                    elif alignment == 'right':
                        style_attr = ' style="text-align: right;"'
                    elif alignment == 'both':
                        style_attr = ' style="text-align: justify;"'
                
                html_content = f'<p{style_attr}>{html_content}</p>'
        
        return text_content, html_content, has_images
    
    def _process_run(self, run_elem):
        """Process a run element with formatting"""
        text_content = ''
        html_content = ''
        has_image = False
        
        # Check for text
        for text_elem in run_elem.findall('.//w:t', self.namespaces):
            if text_elem.text:
                text_content += text_elem.text
                
                # Get formatting
                formatted_text = self._apply_formatting(text_elem.text, run_elem)
                html_content += formatted_text
        
        # Check for images
        for drawing in run_elem.findall('.//w:drawing', self.namespaces):
            img_html = self._process_drawing(drawing)
            if img_html:
                html_content += img_html
                # This allows screen readers to know there's an image
                text_content += '[IMAGE]'
                has_image = True
        
        return text_content, html_content, has_image
    
    def _apply_formatting(self, text, run_elem):
        """Apply formatting to text based on run properties"""
        # Get run properties
        run_props = run_elem.find('w:rPr', self.namespaces)
        
        if run_props is None:
            return text
        
        # Check for various formatting
        is_bold = run_props.find('w:b', self.namespaces) is not None
        is_italic = run_props.find('w:i', self.namespaces) is not None
        is_underline = run_props.find('w:u', self.namespaces) is not None
        
        # Apply HTML tags
        if is_bold:
            text = f'<strong>{text}</strong>'
        if is_italic:
            text = f'<em>{text}</em>'
        if is_underline:
            text = f'<u>{text}</u>'
        
        return text
    
    def _process_drawing(self, drawing_elem):
        """Process drawing elements (images)"""
        try:
            # Find the relationship ID
            blip = drawing_elem.find('.//a:blip', self.namespaces)
            if blip is not None:
                rel_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                
                if rel_id and rel_id in self.extracted_images:
                    doc_image = self.extracted_images[rel_id]
                    # Create HTML img tag
                    return f'<img src="/api/api/image/{doc_image.id}/" alt="{doc_image.filename}" class="document-image" />'
        
        except Exception as e:
            print(f"Error processing drawing: {e}")
        
        return ''
    
    def _link_paragraph_images(self, para_elem, paragraph):
        """Link images found in paragraph to the paragraph"""
        position = 0
        
        # Find all drawings in this paragraph
        for drawing in para_elem.findall('.//w:drawing', self.namespaces):
            try:
                blip = drawing.find('.//a:blip', self.namespaces)
                if blip is not None:
                    rel_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    
                    if rel_id and rel_id in self.extracted_images:
                        doc_image = self.extracted_images[rel_id]
                        
                        ParagraphImage.objects.create(
                            paragraph=paragraph,
                            document_image=doc_image,
                            position_in_paragraph=position
                        )
                        position += 1
            
            except Exception as e:
                print(f"Error linking image to paragraph: {e}")