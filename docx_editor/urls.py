from django.urls import path
from django.views.generic import TemplateView
from . import views
from .cancel_deletion_view import CancelScheduledDeletionView

urlpatterns = [
    path('', TemplateView.as_view(template_name='editor/index.html'), name='home'),    
    path('api/documents/', views.ListDocumentsView.as_view(), name='list_documents'),
    path('api/upload/', views.UploadDocumentView.as_view(), name='upload'),
    path('api/document/<int:document_id>/', views.GetDocumentView.as_view(), name='get_document'),
    path('api/document/<int:document_id>/export/', views.ExportDocumentView.as_view(), name='export'),    
    path('api/edit_paragraph/', views.EditParagraphView.as_view(), name='edit_paragraph'),
    path('api/add_paragraph/', views.AddParagraphView.as_view(), name='add_paragraph'),
    path('api/delete_paragraph/', views.DeleteParagraphView.as_view(), name='delete_paragraph'),    
    path('api/add_comment/', views.AddCommentView.as_view(), name='add_comment'),
    path('api/delete_comment/', views.DeleteCommentView.as_view(), name='delete_comment'),
    path('api/image/<int:image_id>/', views.ServeImageView.as_view(), name='serve_image'),
    
    # Document Version Management
    path('api/document/<int:document_id>/create-version/', views.CreateNewVersionView.as_view(), name='create_version'),
    path('api/document/<int:document_id>/versions/', views.GetDocumentVersionsView.as_view(), name='get_versions'),
    path('api/versions/stats/', views.DocumentVersionStatsView.as_view(), name='version_stats'),
    
    # ML Compliance Checking APIs  
    path('api/ml/check-compliance/', views.CheckEditComplianceView.as_view(), name='check_compliance'),
    path('api/ml/check-compliance-realtime/', views.CheckEditComplianceRealTimeView.as_view(), name='check_compliance_realtime'),
    path('api/ml/check-paragraph-compliance/', views.CheckParagraphComplianceView.as_view(), name='check_paragraph_compliance'),
    path('api/ml/model-status/', views.MLModelStatusView.as_view(), name='ml_model_status'),
    path('api/ml/cancel-scheduled-deletion/', CancelScheduledDeletionView.as_view(), name='cancel_scheduled_deletion'),
]