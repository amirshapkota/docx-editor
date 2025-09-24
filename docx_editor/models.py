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
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='comments')
    paragraph = models.ForeignKey(Paragraph, on_delete=models.CASCADE, related_name='comments')
    comment_id = models.IntegerField()
    author = models.CharField(max_length=100)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Comment by {self.author}: {self.text[:30]}"