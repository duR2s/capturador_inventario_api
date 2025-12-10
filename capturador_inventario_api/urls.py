from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .views.bootstrap import VersionView
from .views.capturaInventario import CapturaInventarioView, SincronizarCapturaView, DetalleIndividualView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("api/version/", VersionView.as_view(), name="api-version"),
    
    # 1. Gestión de Cabecera (Crear Folio)
    path("api/inventario/captura/", CapturaInventarioView.as_view(), name="api-captura-create"),
    
    # 2. Sincronización Masiva (Offline -> Online)
    path("api/inventario/captura/<int:pk>/sincronizar/", SincronizarCapturaView.as_view(), name="api-captura-sync"),

    # 3. CRUD Detalle Individual (Online Mode)
    # POST (Crear), DELETE (Borrar pk), PATCH (Editar pk)
    path("api/inventario/detalle/", DetalleIndividualView.as_view(), name="api-detalle-create"),
    path("api/inventario/detalle/<int:pk>/", DetalleIndividualView.as_view(), name="api-detalle-manage"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)