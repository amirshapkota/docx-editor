"""
Django management command to retrain the ML compliance model
Usage: python manage.py retrain_ml_model
"""

from django.core.management.base import BaseCommand
from docx_editor.ml_compliance import retrain_model_with_comprehensive_data


class Command(BaseCommand):
    help = 'Retrain the ML compliance model with comprehensive training data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force retrain even if model already exists',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('[START] Starting ML model retraining...'))
        
        try:
            classifier = retrain_model_with_comprehensive_data()
            
            if classifier is not None:
                self.stdout.write(
                    self.style.SUCCESS('[SUCCESS] ML model retrained successfully!')
                )
                self.stdout.write(
                    self.style.SUCCESS('[READY] Model is now ready for use in the application')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('[ERROR] Failed to retrain ML model')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'[ERROR] Error during retraining: {e}')
            )