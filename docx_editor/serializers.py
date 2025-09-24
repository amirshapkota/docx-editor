from rest_framework import serializers
from .models import Document, Paragraph, Comment, DocumentImage, ParagraphImage

class DocumentImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentImage
        fields = ['id', 'image_id', 'filename', 'content_type', 'width', 'height']

class ParagraphImageSerializer(serializers.ModelSerializer):
    document_image = DocumentImageSerializer(read_only=True)
    
    class Meta:
        model = ParagraphImage
        fields = ['document_image', 'position_in_paragraph']

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['comment_id', 'author', 'text', 'paragraph_id']
    
    paragraph_id = serializers.SerializerMethodField()

    def get_paragraph_id(self, obj):
        return obj.paragraph.paragraph_id
    
class ParagraphSerializer(serializers.ModelSerializer):
    images = ParagraphImageSerializer(source='paragraph_images', many=True, read_only=True)
    
    class Meta:
        model = Paragraph
        fields = ['paragraph_id', 'text', 'html_content', 'has_images', 'images']

class DocumentSerializer(serializers.ModelSerializer):
    paragraphs = ParagraphSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    images = DocumentImageSerializer(many=True, read_only=True)
    
    class Meta:
        model = Document
        fields = ['id', 'filename', 'paragraphs', 'comments', 'images']