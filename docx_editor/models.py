from django.db import models

class Document(models.Model):
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_editable = models.BooleanField(default=False)  # False means comment-only
    
    def __str__(self):
        return self.filename
    
class Paragraph(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='paragraphs')
    paragraph_id = models.IntegerField()
    text = models.TextField()
    
    class Meta:
        unique_together = ['document', 'paragraph_id']
    
    def __str__(self):
        return f"Para {self.paragraph_id}: {self.text[:50]}"
    
class Comment(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='comments')
    paragraph = models.ForeignKey(Paragraph, on_delete=models.CASCADE, related_name='comments')
    comment_id = models.IntegerField()
    author = models.CharField(max_length=100)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Comment by {self.author}: {self.text[:30]}"