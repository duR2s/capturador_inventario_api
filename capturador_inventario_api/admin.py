from django.contrib import admin
from django.utils.html import format_html
from capturador_inventario_api.models import Administradores, Capturadores, Captura, DetalleCaptura


@admin.register(Administradores)
class AdministradoresAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "clave_admin", "telefono", "fecha_nacimiento", "edad", "creation")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name", "clave_admin", "rfc")
    list_filter = ("creation",)

@admin.register(Capturadores)
class CapturadoresAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "id_trabajador", "telefono", "creation")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name", "id_trabajador")
    list_filter = ("creation",)

class DetalleCapturaInline(admin.TabularInline):
    model = DetalleCaptura
    extra = 1 # Muestra un campo extra para añadir un nuevo detalle
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
