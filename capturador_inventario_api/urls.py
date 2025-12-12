from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Importamos las vistas existentes
from .views.bootstrap import VersionView
from .views.capturaInventario import CapturaInventarioView, SincronizarCapturaView, DetalleIndividualView
from .views.empleado import EmpleadoView, EmpleadoAll
from .views.auth import CustomAuthToken, Logout
from .views.capturaInventario import AlmacenOptionsView

# Importamos las NUEVAS vistas de administrador
# Asegúrate de que 'administrador.py' esté accesible como módulo. 
# Si está en una carpeta 'views', sería: from .views.administrador import ...
from .views.administrador import AdminView, AdminAll 

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("api/version/", VersionView.as_view(), name="api-version"),
    
    # GET (Listar todos)
    path("api/lista-admins/", AdminAll.as_view(), name="api-admin-list"),
    # GET (Uno por id), POST (Crear), PUT (Editar), DELETE (Borrar)
    path("api/admin/", AdminView.as_view(), name="api-admin-manage"),

    # GET (Listar todos los capturadores)
    path("api/lista-empleados/", EmpleadoAll.as_view(), name="api-empleado-list"),
    # GET (Uno por id), POST (Crear), PUT (Editar), DELETE (Borrar)
    path("api/empleado/", EmpleadoView.as_view(), name="api-empleado-manage"),

    # --- RUTAS DE INVENTARIO ---
    # 1. Gestión de Cabecera (Crear Folio)
    path("api/inventario/captura/", CapturaInventarioView.as_view(), name="api-captura-create"),
    
    # 2. Sincronización Masiva (Offline -> Online)
    path("api/inventario/captura/<int:pk>/sincronizar/", SincronizarCapturaView.as_view(), name="api-captura-sync"),

    # 3. CRUD Detalle Individual (Online Mode)
    path("api/inventario/detalle/", DetalleIndividualView.as_view(), name="api-detalle-create"),
    path("api/inventario/detalle/<int:pk>/", DetalleIndividualView.as_view(), name="api-detalle-manage"),

    # 4. RUTAS DE INVENTARIO ---
    
    # 0. Catálogos para selects (NUEVO)
    path("api/inventario/almacenes/", AlmacenOptionsView.as_view(), name="api-almacenes-list"),

    # 1. Gestión de Cabecera (Crear Folio)
    path("api/inventario/captura/", CapturaInventarioView.as_view(), name="api-captura-create"),
    # --- RUTAS DE AUTENTICACIÓN ---
    path("api/login/", CustomAuthToken.as_view(), name="api-login"),
    path("api/logout/", Logout.as_view(), name="api-logout"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)