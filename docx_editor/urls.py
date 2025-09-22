from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('api/upload/', views.UploadDocumentView.as_view(), name='upload'),
    path('api/add_comment/', views.AddCommentView.as_view(), name='add_comment'),
    path('api/export/<int:document_id>/', views.ExportDocumentView.as_view(), name='export'),
    path('api/document/<int:document_id>/', views.GetDocumentView.as_view(), name='get_document'),
]