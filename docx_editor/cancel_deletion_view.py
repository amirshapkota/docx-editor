"""
API endpoint to cancel scheduled comment deletion
Usage: POST /editor/api/cancel-scheduled-deletion/
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import Comment


class CancelScheduledDeletionView(APIView):
    """
    Cancel a scheduled comment deletion
    """
    
    def post(self, request):
        comment_id = request.data.get('comment_id')
        document_id = request.data.get('document_id')
        
        if not all([comment_id, document_id]):
            return Response({
                'error': 'Missing required fields: comment_id, document_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Find the comment
            comment = Comment.objects.get(
                comment_id=comment_id,
                document_id=document_id,
                scheduled_deletion_at__isnull=False  # Only scheduled comments
            )
            
            # Cancel the scheduled deletion
            scheduled_time = comment.scheduled_deletion_at
            comment.scheduled_deletion_at = None
            comment.save()
            
            return Response({
                'message': f'Cancelled scheduled deletion for comment {comment_id}',
                'comment_id': comment_id,
                'was_scheduled_for': scheduled_time.isoformat() if scheduled_time else None,
                'status': 'cancelled'
            })
            
        except Comment.DoesNotExist:
            return Response({
                'error': 'Comment not found or not scheduled for deletion'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'Error cancelling scheduled deletion: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)