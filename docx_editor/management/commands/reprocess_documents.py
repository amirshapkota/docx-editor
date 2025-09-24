from django.core.management.base import BaseCommand
from docx_editor.models import Document, Paragraph, DocumentImage, ParagraphImage
from docx_editor.docx_parser import EnhancedDocxParser
import os


class Command(BaseCommand):
    help = 'Reprocess existing DOCX documents to extract images and formatting'

    def add_arguments(self, parser):
        parser.add_argument(
            '--document-id',
            type=int,
            help='Reprocess specific document by ID'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Reprocess all documents'
        )

    def handle(self, *args, **options):
        if options['document_id']:
            documents = Document.objects.filter(id=options['document_id'])
        elif options['all']:
            documents = Document.objects.all()
        else:
            self.stdout.write(
                self.style.ERROR('Please specify --document-id or --all')
            )
            return

        for document in documents:
            self.stdout.write(f'Reprocessing document: {document.filename}')
            
            if not os.path.exists(document.file_path):
                self.stdout.write(
                    self.style.ERROR(f'File not found: {document.file_path}')
                )
                continue
            
            try:
                # Clear existing images for this document
                DocumentImage.objects.filter(document=document).delete()
                
                # Clear existing paragraphs
                document.paragraphs.all().delete()
                
                # Use enhanced parser to reprocess
                parser = EnhancedDocxParser(document.file_path, document)
                paragraphs_data = parser.parse_document()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully reprocessed {document.filename}: '
                        f'{len(paragraphs_data)} paragraphs, '
                        f'{DocumentImage.objects.filter(document=document).count()} images'
                    )
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error reprocessing {document.filename}: {e}')
                )