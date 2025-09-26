# Generated migration for document versioning system

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('docx_editor', '0007_add_scheduled_deletion_to_comment'),
    ]

    operations = [
        # Add version fields to Document model
        migrations.AddField(
            model_name='document',
            name='version_number',
            field=models.IntegerField(default=1, help_text='Version number (1, 2, 3, ...)'),
        ),
        migrations.AddField(
            model_name='document',
            name='parent_document',
            field=models.ForeignKey(
                blank=True, 
                null=True, 
                on_delete=django.db.models.deletion.CASCADE, 
                related_name='versions', 
                to='docx_editor.document',
                help_text='Parent document this version was created from'
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='version_status',
            field=models.CharField(
                choices=[
                    ('original', 'Original Upload'),
                    ('commented', 'Has Comments'),
                    ('edited', 'Edited Version'),
                    ('archived', 'Archived')
                ],
                default='original',
                help_text='Current version status in workflow',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='created_from_comments',
            field=models.BooleanField(
                default=False, 
                help_text='True if this version was created by processing comments'
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='base_document',
            field=models.ForeignKey(
                blank=True, 
                null=True, 
                on_delete=django.db.models.deletion.CASCADE, 
                related_name='all_versions', 
                to='docx_editor.document',
                help_text='Root/original document for this version chain'
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='comment_count',
            field=models.IntegerField(default=0, help_text='Number of comments on this version'),
        ),
        migrations.AddField(
            model_name='document',
            name='processed_comment_ids',
            field=models.JSONField(
                blank=True, 
                default=list, 
                help_text='List of comment IDs that were processed to create next version'
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='version_notes',
            field=models.TextField(
                blank=True, 
                help_text='Notes about changes made in this version'
            ),
        ),
        
        # Add index for better performance
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['base_document', 'version_number'], name='doc_version_idx'),
        ),
        
        # Create composite unique constraint for base_document + version_number
        migrations.AddConstraint(
            model_name='document',
            constraint=models.UniqueConstraint(
                fields=['base_document', 'version_number'], 
                name='unique_version_per_base',
                condition=models.Q(base_document__isnull=False)
            ),
        ),
    ]