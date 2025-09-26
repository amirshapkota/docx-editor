from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/editor/', permanent=False)),
    path('admin/', admin.site.urls),
    path('commenter/', include('docx_commenter.urls', namespace='commenter')),
    path('editor/', include('docx_full_editor.urls', namespace='editor')),
    path('api/', include('docx_editor.urls')),  # Keep for backward compatibility
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
