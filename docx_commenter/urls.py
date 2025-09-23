from django.urls import path
from django.views.generic import TemplateView
from docx_editor import views

app_name = 'docx_commenter'

urlpatterns = [
    # Template views
    path('', TemplateView.as_view(template_name='commenter/index.html'), name='home'),
    
    # API endpoints
    path('api/upload/', views.UploadDocumentView.as_view(), name='upload'),
    path('api/documents/', views.ListDocumentsView.as_view(), name='list_documents'),
    path('api/document/<int:document_id>/', views.GetDocumentView.as_view(), name='view_document'),
    path('api/document/<int:document_id>/export/', views.ExportDocumentView.as_view(), name='export'),
    path('api/add_comment/', views.AddCommentView.as_view(), name='add_comment'),
]