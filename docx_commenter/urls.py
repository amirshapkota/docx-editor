from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'docx_commenter'

urlpatterns = [
    # Template views
    path('', TemplateView.as_view(template_name='commenter/index.html'), name='home'),
    
    # API endpoints
    path('api/upload/', views.CommentUploadDocumentView.as_view(), name='upload'),
    path('api/documents/', views.ListDocumentsView.as_view(), name='list_documents'),
    path('api/document/<int:document_id>/', views.ViewDocumentView.as_view(), name='view_document'),
    path('api/document/<int:document_id>/export/', views.ExportDocumentView.as_view(), name='export'),
    path('api/add_comment/', views.AddCommentView.as_view(), name='add_comment'),
    path('api/delete_comment/', views.DeleteCommentView.as_view(), name='delete_comment'),
    path('api/image/<int:image_id>/', views.ServeImageView.as_view(), name='serve_image'),
    
    # Version management endpoints (reuse from editor)
    path('api/document/<int:document_id>/versions/', views.GetDocumentVersionsView.as_view(), name='get_versions'),
    path('api/versions/stats/', views.DocumentVersionStatsView.as_view(), name='version_stats'),
]