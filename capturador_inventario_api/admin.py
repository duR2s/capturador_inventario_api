from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from capturador_inventario_api.models import (
    Empleado, 
    Captura, 
    DetalleCaptura,
    BitacoraSincronizacion,
    Articulo,
    ClaveAuxiliar
)

# -------------------------------------------------------------------------
# 1. INTEGRACIÓN CON USUARIO (UserAdmin)
# -------------------------------------------------------------------------
# Esto permite editar los datos de Empleado directamente desde la pantalla de Usuario
class EmpleadoInline(admin.StackedInline):
    model = Empleado
    can_delete = False
    verbose_name_plural = 'Datos de Empleado'
    fk_name = 'user'

class UserAdmin(BaseUserAdmin):
    inlines = (EmpleadoInline,)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# -------------------------------------------------------------------------
# 2. ADMINISTRACIÓN DE EMPLEADOS (Unificado)
# -------------------------------------------------------------------------
@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    # Combinamos las columnas útiles de tus antiguos admins
    list_display = (
        "id", 
        "user", 
        "puesto",           # Nuevo: para distinguir Admin vs Capturador
        "clave_interna",    # Reemplaza a clave_admin / id_trabajador
        "telefono", 
        "edad", 
        "creation"
    )
    
    # Búsqueda unificada
    search_fields = (
        "user__username", 
        "user__email", 
        "user__first_name", 
        "user__last_name", 
        "clave_interna"     # Busca tanto claves de admin como IDs de trabajador
    )
    
    # Filtros: Agregamos 'puesto' para simular las tablas separadas
    list_filter = ("puesto", "creation")


# -------------------------------------------------------------------------
# 3. CAPTURA DE INVENTARIO (Tu configuración conservada)
# -------------------------------------------------------------------------
class DetalleCapturaInline(admin.TabularInline):
    model = DetalleCaptura
    extra = 1 # Muestra un campo extra para añadir un nuevo detalle
    # raw_id_fields es útil si tienes miles de productos, para no cargar un dropdown gigante
    # raw_id_fields = ('producto',) 
    readonly_fields = ('producto_codigo', 'cantidad_contada') # Para que no se puedan editar desde la captura

@admin.register(Captura)
class CapturaAdmin(admin.ModelAdmin):
    list_display = ('folio', 'capturador', 'fecha_captura', 'estado')
    search_fields = ('folio', 'capturador__username')
    list_filter = ('estado', 'fecha_captura')
    inlines = [DetalleCapturaInline] # Muestra los detalles dentro de la vista de la captura

@admin.register(DetalleCaptura)
class DetalleCapturaAdmin(admin.ModelAdmin):
    list_display = ('id', 'captura', 'producto_codigo', 'cantidad_contada')
    search_fields = ('producto_codigo', 'captura__folio')


# -------------------------------------------------------------------------
# 4. BITÁCORA DE SINCRONIZACIÓN (Tu configuración conservada)
# -------------------------------------------------------------------------
@admin.register(BitacoraSincronizacion)
class BitacoraSincronizacionAdmin(admin.ModelAdmin):
    # Agregamos los nuevos contadores al list_display
    list_display = (
        'fecha_inicio', 
        'status', 
        'articulos_procesados', 
        'articulos_creados', 
        'articulos_actualizados', 
        'articulos_desactivados',
        'claves_creadas',
        'duracion'
    )
    list_filter = ('status', 'fecha_inicio')
    
    # Campos de solo lectura, incluyendo los nuevos
    readonly_fields = (
        'fecha_inicio', 
        'fecha_fin', 
        'articulos_procesados', 
        'articulos_creados', 
        'articulos_actualizados', 
        'articulos_desactivados',
        'claves_creadas',
        'status', 
        'detalles_procesamiento',
        'mensaje_error'
    )
    
    def duracion(self, obj):
        if obj.fecha_fin and obj.fecha_inicio:
            # Calculamos la diferencia y la formateamos bonito
            diff = obj.fecha_fin - obj.fecha_inicio
            return str(diff).split('.')[0] # Quita los microsegundos para limpieza
        return "-"
    duracion.short_description = "Duración"
    
    def has_add_permission(self, request):
        return False


# -------------------------------------------------------------------------
# 5. CATALOGOS DE MICROSIP (Auxiliares)
# -------------------------------------------------------------------------
@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = ('clave', 'nombre', 'articulo_id_msip', 'activo', 'ultima_sincronizacion')
    search_fields = ('clave', 'nombre')
    list_filter = ('activo', 'seguimiento_tipo')
    readonly_fields = ('ultima_sincronizacion',)

@admin.register(ClaveAuxiliar)
class ClaveAuxiliarAdmin(admin.ModelAdmin):
    list_display = ('clave', 'articulo')
    search_fields = ('clave', 'articulo__clave', 'articulo__nombre')