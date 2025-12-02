from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .views.bootstrap import VersionView
from .views.capturaInventario import CapturaInventarioView  # Importamos la nueva vista

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("api/version/", VersionView.as_view(), name="api-version"),
    
    # Endpoint de Captura de Inventario
    path("api/inventario/captura/", CapturaInventarioView.as_view(), name="api-inventario-captura"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)