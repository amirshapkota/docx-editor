from django.urls import path
from django.views.generic import TemplateView
from . import views
from docx_editor.views import (
    CheckEditComplianceRealTimeView,
    CheckEditComplianceView,
    CheckParagraphComplianceView,
    MLModelStatusView,
    GetDocumentVersionsView,
    DocumentVersionStatsView,
    CreateNewVersionView
)

app_name = 'docx_full_editor'

urlpatterns = [
    # Template views
    path('', TemplateView.as_view(template_name='editor/index.html'), name='home'),
    
    # API endpoints
    path('api/documents/', views.ListDocumentsView.as_view(), name='list_documents'),
    path('api/upload/', views.EditorUploadDocumentView.as_view(), name='upload'),
    path('api/document/<int:document_id>/', views.EditDocumentView.as_view(), name='edit_document'),
    path('api/document/<int:document_id>/export/', views.ExportDocumentView.as_view(), name='export'),
    path('api/edit_paragraph/', views.EditParagraphView.as_view(), name='edit_paragraph'),
    path('api/add_paragraph/', views.AddParagraphView.as_view(), name='add_paragraph'),
    path('api/delete_paragraph/', views.DeleteParagraphView.as_view(), name='delete_paragraph'),
    path('api/add_comment/', views.AddCommentView.as_view(), name='add_comment'),
    path('api/delete_comment/', views.DeleteCommentView.as_view(), name='delete_comment'),
    
    # Version management endpoints
    path('api/document/<int:document_id>/create-version/', CreateNewVersionView.as_view(), name='create_version'),
    path('api/document/<int:document_id>/versions/', GetDocumentVersionsView.as_view(), name='get_versions'),
    path('api/versions/stats/', DocumentVersionStatsView.as_view(), name='version_stats'),
    
    # ML Compliance Checking APIs  
    path('api/ml/check-compliance/', CheckEditComplianceView.as_view(), name='check_compliance'),
    path('api/ml/check-compliance-realtime/', CheckEditComplianceRealTimeView.as_view(), name='check_compliance_realtime'),
    path('api/ml/check-paragraph-compliance/', CheckParagraphComplianceView.as_view(), name='check_paragraph_compliance'),
    path('api/ml/model-status/', MLModelStatusView.as_view(), name='ml_model_status'),
]