from rest_framework import serializers
from .models import Document, Paragraph, Comment

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['comment_id', 'author', 'text', 'paragraph_id']
    
    paragraph_id = serializers.SerializerMethodField()

    def get_paragraph_id(self, obj):
        return obj.paragraph.paragraph_id
    
class ParagraphSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paragraph
        fields = ['paragraph_id', 'text']

class DocumentSerializer(serializers.ModelSerializer):
    paragraphs = ParagraphSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Document
        fields = ['id', 'filename', 'paragraphs', 'comments']