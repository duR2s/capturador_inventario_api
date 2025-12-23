from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Importamos las vistas existentes
from .views.bootstrap import VersionView
from .views.capturaInventario import CapturaInventarioView, SincronizarCapturaView, DetalleIndividualView
from .views.auth import CustomAuthToken, Logout

# --- CAMBIO: Importamos ambas vistas ---
from .views.empleado import UsuarioGestionView, UsuarioListView

# Importamos vistas de inventario
from .views.capturaInventario import (
    AlmacenOptionsView, 
    CapturaDetailView, 
    ArticuloBusquedaView, 
    TicketCreateView, 
    ExportarCapturaExcelView, 
    EstadoCapturaOptionsView
)



urlpatterns = [
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("api/version/", VersionView.as_view(), name="api-version"),
    
    # --- GESTIÓN DE USUARIOS UNIFICADA ---
    
    # 1. URL PARA OBTENER TODOS (LISTADO)
    # GET /api/lista-usuarios/?rol=ADMIN&q=pepe
    path("api/lista-usuarios/", UsuarioListView.as_view(), name="api-usuarios-list"),

    # 2. URL PARA GESTIÓN INDIVIDUAL (CRUD)
    # GET (Uno), POST (Crear), PUT (Editar), DELETE (Borrar)
    path("api/usuarios/", UsuarioGestionView.as_view(), name="api-usuarios-gestion"),

    # --- RUTAS DE INVENTARIO ---
    
    # 0. Catálogos
    path("api/inventario/almacenes/", AlmacenOptionsView.as_view(), name="api-almacenes-list"),
    path("api/inventario/estados/", EstadoCapturaOptionsView.as_view(), name="api-estados-list"),

    # 0.1 Búsqueda
    path("api/inventario/buscar-articulo/", ArticuloBusquedaView.as_view(), name="api-buscar-articulo"),

    # 1. Gestión de Cabecera
    path("api/inventario/captura/", CapturaInventarioView.as_view(), name="api-captura-create"),
    path("api/inventario/captura/<int:pk>/", CapturaDetailView.as_view(), name="api-captura-detail"),
    
    # 2. Sincronización
    path("api/inventario/captura/<int:pk>/sincronizar/", SincronizarCapturaView.as_view(), name="api-captura-sync"),

    # 3. Detalle Individual
    path("api/inventario/detalle/", DetalleIndividualView.as_view(), name="api-detalle-create"),
    path("api/inventario/detalle/<int:pk>/", DetalleIndividualView.as_view(), name="api-detalle-manage"),

    # 4. Tickets
    path("api/inventario/ticket/", TicketCreateView.as_view(), name="api-ticket-create"),

    # 5. Exportar
    path("api/inventario/captura/<int:pk>/excel/", ExportarCapturaExcelView.as_view(), name="api-captura-excel"),

    # --- RUTAS DE AUTENTICACIÓN ---
    path("api/login/", CustomAuthToken.as_view(), name="api-login"),
    path("api/logout/", Logout.as_view(), name="api-logout"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)