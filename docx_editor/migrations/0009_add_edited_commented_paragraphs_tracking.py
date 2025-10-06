# Generated migration for tracking edited commented paragraphs

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('docx_editor', '0008_add_document_versioning'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='edited_commented_paragraphs',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='List of paragraph IDs with comments that have been edited'
            ),
        ),
    ]