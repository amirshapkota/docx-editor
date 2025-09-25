from django.db import models
import json

class Document(models.Model):
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_editable = models.BooleanField(default=False)  # False means comment-only
    
    def __str__(self):
        return self.filename
    
class DocumentImage(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='images')
    image_id = models.CharField(max_length=100)  # Original image ID from DOCX
    filename = models.CharField(max_length=255)  # Original filename
    file_path = models.CharField(max_length=500)  # Path to extracted image
    content_type = models.CharField(max_length=50, default='image/png')
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Image {self.image_id} in {self.document.filename}"
    
class Paragraph(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='paragraphs')
    paragraph_id = models.IntegerField()
    text = models.TextField()
    html_content = models.TextField(blank=True)  # Rich HTML content with formatting
    has_images = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['document', 'paragraph_id']
    
    def __str__(self):
        return f"Para {self.paragraph_id}: {self.text[:50]}"
    
    def get_images(self):
        """Get images that belong to this paragraph"""
        return ParagraphImage.objects.filter(paragraph=self)

class ParagraphImage(models.Model):
    paragraph = models.ForeignKey(Paragraph, on_delete=models.CASCADE, related_name='paragraph_images')
    document_image = models.ForeignKey(DocumentImage, on_delete=models.CASCADE)
    position_in_paragraph = models.IntegerField(default=0)  # Order within paragraph
    
    class Meta:
        unique_together = ['paragraph', 'position_in_paragraph']
        ordering = ['position_in_paragraph']
    
    def __str__(self):
        return f"Image {self.document_image.image_id} in paragraph {self.paragraph.paragraph_id}"
    
class Comment(models.Model):
    COMPLIANCE_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('compliant', 'Compliant - Can Delete'),
        ('partial', 'Partial Compliance'),
        ('non_compliant', 'Non-compliant'),
    ]
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='comments')
    paragraph = models.ForeignKey(Paragraph, on_delete=models.CASCADE, related_name='comments')
    comment_id = models.IntegerField()
    author = models.CharField(max_length=100)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # ML compliance tracking
    compliance_status = models.CharField(
        max_length=20,
        choices=COMPLIANCE_STATUS_CHOICES,
        default='pending',
        help_text="ML-determined compliance status of edits against this comment"
    )
    compliance_score = models.FloatField(
        null=True, blank=True,
        help_text="ML confidence score (0.0-1.0) for compliance determination"
    )
    last_checked = models.DateTimeField(
        null=True, blank=True,
        help_text="When this comment was last checked for compliance"
    )
    scheduled_deletion_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When this compliant comment is scheduled for automatic deletion (5 min delay)"
    )
    
    def __str__(self):
        return f"Comment by {self.author}: {self.text[:30]}"


# ML Models for Comment-Edit Compliance Checking

class EditComplianceData(models.Model):
    """
    Store training/evaluation data for the ML model
    Each record represents a comment-edit pair with compliance information
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='compliance_data')
    paragraph = models.ForeignKey(Paragraph, on_delete=models.CASCADE, related_name='compliance_data')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='compliance_data')
    
    # Text data for ML training
    original_text = models.TextField(help_text="Original paragraph text before edit")
    edited_text = models.TextField(help_text="Final paragraph text after edit")
    comment_text = models.TextField(help_text="Comment/suggestion text")
    
    # ML labels and predictions
    compliance_score = models.FloatField(
        null=True, blank=True, 
        help_text="Compliance score 0.0-1.0 (0=non-compliant, 1=fully compliant)"
    )
    compliance_label = models.CharField(
        max_length=20, 
        choices=[
            ('compliant', 'Compliant'),
            ('partial', 'Partially Compliant'),
            ('non_compliant', 'Non-Compliant'),
            ('needs_review', 'Needs Manual Review')
        ],
        null=True, blank=True
    )
    
    # Edit categorization
    edit_type = models.CharField(
        max_length=20,
        choices=[
            ('grammar', 'Grammar/Spelling'),
            ('content', 'Content Changes'),
            ('style', 'Style/Tone'),
            ('structure', 'Structure/Organization'),
            ('formatting', 'Formatting'),
            ('mixed', 'Mixed Changes')
        ],
        null=True, blank=True
    )
    
    # Quality assurance
    manually_reviewed = models.BooleanField(default=False)
    reviewer_notes = models.TextField(blank=True, help_text="Manual reviewer feedback")
    confidence_score = models.FloatField(null=True, blank=True, help_text="Model confidence 0.0-1.0")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['paragraph', 'comment']  # One compliance record per comment-paragraph pair
        indexes = [
            models.Index(fields=['compliance_label', 'created_at']),
            models.Index(fields=['edit_type', 'compliance_score']),
        ]
    
    def __str__(self):
        return f"Compliance: {self.compliance_label} - Para {self.paragraph.paragraph_id} - Comment {self.comment.comment_id}"


class MLModel(models.Model):
    """
    Track different versions of ML models for compliance checking
    """
    name = models.CharField(max_length=100, help_text="Model name/identifier")
    version = models.CharField(max_length=20, help_text="Model version (e.g., v1.0, v1.1)")
    description = models.TextField(blank=True, help_text="Model description and changes")
    
    # Model files and configuration
    model_path = models.CharField(max_length=500, help_text="Path to model file")
    config_data = models.JSONField(default=dict, help_text="Model configuration and hyperparameters")
    
    # Performance metrics
    accuracy = models.FloatField(null=True, blank=True, help_text="Overall accuracy on test set")
    precision = models.FloatField(null=True, blank=True, help_text="Precision score")
    recall = models.FloatField(null=True, blank=True, help_text="Recall score")
    f1_score = models.FloatField(null=True, blank=True, help_text="F1 score")
    
    # Model metadata
    training_data_size = models.IntegerField(null=True, blank=True, help_text="Number of training samples")
    model_type = models.CharField(
        max_length=50,
        choices=[
            ('bert', 'BERT-based Transformer'),
            ('roberta', 'RoBERTa-based Transformer'),
            ('similarity', 'Similarity-based Model'),
            ('ensemble', 'Ensemble Model'),
            ('custom', 'Custom Architecture')
        ],
        default='custom'
    )
    
    # Status
    is_active = models.BooleanField(default=False, help_text="Currently deployed model")
    is_production_ready = models.BooleanField(default=False, help_text="Ready for production use")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    deployed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['name', 'version']
        ordering = ['-created_at']
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.name} {self.version} ({status}) - Acc: {self.accuracy or 'N/A'}"


class ComplianceCheckResult(models.Model):
    """
    Store real-time compliance check results for monitoring and feedback
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='compliance_results')
    paragraph = models.ForeignKey(Paragraph, on_delete=models.CASCADE, related_name='compliance_results')
    
    # Input data
    original_text = models.TextField()
    edited_text = models.TextField()
    comment_text = models.TextField()
    
    # ML prediction results
    model_used = models.ForeignKey(MLModel, on_delete=models.SET_NULL, null=True)
    predicted_score = models.FloatField(help_text="Predicted compliance score 0.0-1.0")
    predicted_label = models.CharField(max_length=20, help_text="Predicted compliance label")
    confidence_score = models.FloatField(help_text="Model confidence in prediction")
    
    # Additional model outputs
    explanation_data = models.JSONField(
        default=dict, 
        help_text="Model explanation/reasoning (attention weights, key features, etc.)"
    )
    
    # User feedback
    user_feedback = models.CharField(
        max_length=20,
        choices=[
            ('correct', 'Prediction was correct'),
            ('incorrect', 'Prediction was incorrect'),
            ('partially_correct', 'Prediction was partially correct'),
            ('no_feedback', 'No user feedback provided')
        ],
        default='no_feedback'
    )
    user_notes = models.TextField(blank=True, help_text="User feedback notes")
    
    # Processing metadata
    processing_time_ms = models.IntegerField(null=True, blank=True, help_text="Model inference time in milliseconds")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['created_at', 'predicted_label']),
            models.Index(fields=['model_used', 'user_feedback']),
        ]
    
    def __str__(self):
        return f"Check Result: {self.predicted_label} ({self.predicted_score:.2f}) - Para {self.paragraph.paragraph_id}"