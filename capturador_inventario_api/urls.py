from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Importamos las vistas existentes
from .views.bootstrap import VersionView
from .views.capturaInventario import CapturaInventarioView, SincronizarCapturaView, DetalleIndividualView
from .views.auth import CustomAuthToken, Logout

# --- CAMBIO: Importamos la Nueva Vista Unificada ---
# Dado que pegaste el código de UsuarioGestionView en 'empleado.py', importamos de ahí.
from .views.empleado import UsuarioGestionView

# Importamos vistas de inventario
from .views.capturaInventario import (
    AlmacenOptionsView, 
    CapturaDetailView, 
    ArticuloBusquedaView, 
    TicketCreateView, 
    ExportarCapturaExcelView, 
    EstadoCapturaOptionsView
)

# Importamos vistas de administrador (Legacy - Mantenlas si aun tienes el archivo administrador.py)
from .views.administrador import AdminView, AdminAll 

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("api/version/", VersionView.as_view(), name="api-version"),
    
    # --- GESTIÓN DE USUARIOS UNIFICADA (NUEVO) ---
    # Esta ruta atiende a tu UsuariosService:
    # GET /api/usuarios/?rol=ADMIN
    # GET /api/usuarios/?q=busqueda
    # POST, PUT, DELETE /api/usuarios/
    path("api/usuarios/", UsuarioGestionView.as_view(), name="api-usuarios-gestion"),

    # --- RUTAS LEGACY DE ADMINISTRADORES ---
    # (Puedes mantenerlas si otros sistemas las usan, o borrarlas si 'UsuarioGestionView' ya maneja todo)
    path("api/lista-admins/", AdminAll.as_view(), name="api-admin-list"),
    path("api/admin/", AdminView.as_view(), name="api-admin-manage"),

    # --- RUTAS DE EMPLEADOS (OBSOLETAS) ---
    # Las comento porque al modificar empleado.py, las clases EmpleadoView/EmpleadoAll 
    # probablemente ya no existan y darían error de importación.
    # path("api/lista-empleados/", EmpleadoAll.as_view(), name="api-empleado-list"),
    # path("api/empleado/", EmpleadoView.as_view(), name="api-empleado-manage"),

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