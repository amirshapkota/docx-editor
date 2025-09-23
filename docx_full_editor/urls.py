from django.urls import path
from django.views.generic import TemplateView
from . import views

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
]