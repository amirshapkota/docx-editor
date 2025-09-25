"""
Django management command to process scheduled comment deletions
Usage: python manage.py process_scheduled_deletions
This should be run via cron job every minute or so
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from docx_editor.models import Comment
from docx_editor.views import XMLFormattingMixin
import zipfile
import os


class Command(BaseCommand, XMLFormattingMixin):
    help = 'Process scheduled comment deletions (comments with expired 5-minute delay)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN] Showing scheduled deletions without executing...'))
        
        # Find comments scheduled for deletion that have passed their deadline
        now = timezone.now()
        comments_to_delete = Comment.objects.filter(
            scheduled_deletion_at__isnull=False,
            scheduled_deletion_at__lte=now
        ).select_related('document')
        
        if not comments_to_delete.exists():
            self.stdout.write(
                self.style.SUCCESS('[INFO] No comments ready for scheduled deletion')
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f'[PROCESSING] Found {comments_to_delete.count()} comments ready for deletion')
        )
        
        deleted_count = 0
        error_count = 0
        
        for comment in comments_to_delete:
            try:
                scheduled_time = comment.scheduled_deletion_at
                delay_minutes = (now - scheduled_time).total_seconds() / 60
                
                if dry_run:
                    self.stdout.write(
                        f'[DRY RUN] Would delete comment {comment.comment_id} '
                        f'from document {comment.document.filename} '
                        f'(delayed {delay_minutes:.1f} minutes ago)'
                    )
                    continue
                
                # Delete from DOCX file first
                docx_success = True
                if os.path.exists(comment.document.file_path):
                    try:
                        # Check file integrity
                        with zipfile.ZipFile(comment.document.file_path, 'r') as test_zip:
                            test_zip.testzip()
                        # Delete comment from DOCX
                        self.delete_comment_from_docx(comment.document.file_path, comment.comment_id)
                    except Exception as docx_error:
                        docx_success = False
                        self.stdout.write(
                            self.style.WARNING(f'[WARNING] DOCX deletion failed for comment {comment.comment_id}: {docx_error}')
                        )
                else:
                    docx_success = False
                    self.stdout.write(
                        self.style.WARNING(f'[WARNING] DOCX file not found for comment {comment.comment_id}')
                    )
                
                # Delete from database
                comment_id = comment.comment_id
                document_name = comment.document.filename
                comment.delete()
                
                deleted_count += 1
                status_suffix = " (DOCX+DB)" if docx_success else " (DB only)"
                self.stdout.write(
                    self.style.SUCCESS(f'[DELETED] Comment {comment_id} from {document_name}{status_suffix}')
                )
                
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'[ERROR] Failed to delete comment {comment.comment_id}: {e}')
                )
        
        # Summary
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'[SUMMARY] Deleted {deleted_count} comments, {error_count} errors')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'[DRY RUN COMPLETE] {comments_to_delete.count()} comments would be processed')
            )