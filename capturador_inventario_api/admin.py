from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from capturador_inventario_api.models import (
    Empleado, 
    Captura, 
    DetalleCaptura,
    BitacoraSincronizacion,
    Articulo,
    ClaveAuxiliar,
    Almacen,
    InventarioArticulo
)

# -------------------------------------------------------------------------
# 1. INTEGRACIÓN CON USUARIO (UserAdmin)
# -------------------------------------------------------------------------

class EmpleadoInline(admin.StackedInline):
    model = Empleado
    can_delete = False
    verbose_name_plural = 'Datos de Empleado'
    fk_name = 'user'

class UserAdmin(BaseUserAdmin):
    inlines = (EmpleadoInline,)

# Re-registramos el UserAdmin para incluir el perfil de Empleado
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# -------------------------------------------------------------------------
# 2. ADMINISTRACIÓN DE EMPLEADOS
# -------------------------------------------------------------------------

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = (
        "user", 
        "puesto", 
        "clave_interna", 
        "telefono", 
        "creation" 
    )
    search_fields = ("user__username", "user__first_name", "user__last_name", "clave_interna")


# -------------------------------------------------------------------------
# 3. CAPTURAS E INVENTARIO (OPERATIVO)
# -------------------------------------------------------------------------

class DetalleCapturaInline(admin.TabularInline):
    model = DetalleCaptura
    extra = 0
    raw_id_fields = ("articulo",)
    readonly_fields = ("existencia_sistema_al_momento",) 

@admin.register(Captura)
class CapturaAdmin(admin.ModelAdmin):
    # CORREGIDO: Ajustado a los campos reales de models.py (estado, fecha_reportada)
    list_display = ('folio', 'almacen', 'estado', 'fecha_reportada', 'modo_offline')
    list_filter = ('estado', 'almacen', 'fecha_reportada', 'modo_offline')
    search_fields = ('folio',)
    inlines = [DetalleCapturaInline]
    date_hierarchy = 'fecha_reportada' # Ahora sí funciona porque el campo existe

@admin.register(DetalleCaptura)
class DetalleCapturaAdmin(admin.ModelAdmin):
    list_display = ('captura', 'get_articulo_clave', 'cantidad_contada', 'localizacion_al_momento', 'existencia_sistema_al_momento')
    search_fields = ('articulo__clave', 'captura__folio')
    list_filter = ('captura__almacen',)
    raw_id_fields = ("articulo",)
    
    def get_articulo_clave(self, obj):
        return obj.articulo.clave if obj.articulo else "SIN ARTICULO"
    get_articulo_clave.short_description = "Clave Art."


# -------------------------------------------------------------------------
# 4. ARTÍCULOS, ALMACENES E INVENTARIO (Sincronizado)
# -------------------------------------------------------------------------

class ClaveAuxiliarInline(admin.TabularInline):
    model = ClaveAuxiliar
    extra = 0
    readonly_fields = ('clave',)
    can_delete = False

@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = ('clave', 'nombre', 'articulo_id_msip', 'activo', 'seguimiento_tipo')
    search_fields = ('clave', 'nombre', 'articulo_id_msip')
    list_filter = ('activo', 'seguimiento_tipo')
    inlines = [ClaveAuxiliarInline]

@admin.register(Almacen)
class AlmacenAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'almacen_id_msip', 'activo_web')
    search_fields = ('nombre',)
    list_filter = ('activo_web',)

@admin.register(InventarioArticulo)
class InventarioArticuloAdmin(admin.ModelAdmin):
    """
    Vista para verificar Stocks traídos de Microsip/Firebird
    """
    list_display = (
        'get_articulo_clave', 
        'get_articulo_nombre', 
        'get_almacen', 
        'existencia', 
        'localizacion',
        'pendiente_sincronizar_msip'
    )
    search_fields = ('articulo__clave', 'articulo__nombre', 'localizacion')
    list_filter = ('almacen', 'pendiente_sincronizar_msip')
    raw_id_fields = ('articulo',)

    def get_articulo_clave(self, obj):
        return obj.articulo.clave
    get_articulo_clave.short_description = 'Clave'

    def get_articulo_nombre(self, obj):
        return obj.articulo.nombre
    get_articulo_nombre.short_description = 'Artículo'

    def get_almacen(self, obj):
        return obj.almacen.nombre
    get_almacen.short_description = 'Almacén'


# -------------------------------------------------------------------------
# 5. BITÁCORA DE SINCRONIZACIÓN
# -------------------------------------------------------------------------

@admin.register(BitacoraSincronizacion)
class BitacoraSincronizacionAdmin(admin.ModelAdmin):
    list_display = (
        'fecha_inicio', 
        'status', 
        'articulos_procesados', 
        'articulos_creados', 
        'duracion_segundos'
    )
    list_filter = ('status', 'fecha_inicio')
    
    readonly_fields = (
        'fecha_inicio', 
        'fecha_fin', 
        'status', 
        'articulos_procesados',
        'articulos_creados',
        'articulos_actualizados',
        'articulos_desactivados',
        'mensaje_error',
        'detalles'
    )

    def duracion_segundos(self, obj):
        if obj.fecha_inicio and obj.fecha_fin:
            delta = obj.fecha_fin - obj.fecha_inicio
            return f"{delta.total_seconds():.2f} s"
        return "-"
    duracion_segundos.short_description = "Duración"