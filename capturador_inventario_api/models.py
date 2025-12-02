from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authentication import TokenAuthentication
from django.contrib.auth.models import AbstractUser, User
from django.conf import settings

# -------------------------------------------------------------------------
# AUTHENTICATION
# -------------------------------------------------------------------------
class BearerTokenAuthentication(TokenAuthentication):
    keyword = "Bearer"


# -------------------------------------------------------------------------
# PERFILES DE USUARIO (Administradores, Capturadores)
# -------------------------------------------------------------------------
class Administradores(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    clave_admin = models.CharField(max_length=255,null=True, blank=True)
    telefono = models.CharField(max_length=255, null=True, blank=True)
    fecha_nacimiento = models.DateField(auto_now_add=False, null=True, blank=True)
    edad = models.IntegerField(null=True, blank=True)
    creation = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    update = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Perfil del admin {self.user.first_name} {self.user.last_name}"

class Capturadores(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    id_trabajador = models.CharField(max_length=255,null=True, blank=True)
    telefono = models.CharField(max_length=255, null=True, blank=True)
    edad = models.IntegerField(null=True, blank=True)
    creation = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    update = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Perfil del capturador {self.user.first_name} {self.user.last_name}"


# -------------------------------------------------------------------------
# CAPTURA DE INVENTARIO (App Móvil/Web)
# -------------------------------------------------------------------------
class Captura(models.Model):
    id = models.BigAutoField(primary_key=True)
    folio = models.CharField(max_length=50, unique=True, null=False, blank=False)
    capturador = models.ForeignKey(User, on_delete=models.PROTECT, related_name="capturas")
    fecha_captura = models.DateTimeField(auto_now_add=True)
    
    ESTADO_CHOICES = [('PROGRESO', 'En Progreso'), ('COMPLETADO', 'Completado')]
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='PROGRESO')

    def __str__(self):
        return f"Captura {self.folio} por {self.capturador.username}"

class DetalleCaptura(models.Model):
    id = models.BigAutoField(primary_key=True)
    captura = models.ForeignKey(Captura, on_delete=models.CASCADE, related_name="detalles")
    producto_codigo = models.CharField(max_length=100) # Código introducido (clave o barras)
    cantidad_contada = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.cantidad_contada} de {self.producto_codigo} en folio {self.captura.folio}"


# -------------------------------------------------------------------------
# MODELOS DE SINCRONIZACIÓN MICROSIP
# Estos son requeridos por 'microsip_api_sync_Articulos.py' y 'tasks.py'
# -------------------------------------------------------------------------

# Mapea ARTICULOS.SEGUIMIENTO (0: Ninguno, 1: Lote, 2: Serie)
SEGUIMIENTO_CHOICES = [
    ('N', 'Ninguno (0)'),
    ('L', 'Lotes (1)'),
    ('S', 'Series (2)'),
]

class Articulo(models.Model):
    """
    Caché local de los artículos de Microsip. 
    Se actualiza automáticamente vía Background Task (Django Q).
    """
    id = models.BigAutoField(primary_key=True)

    # ID interno de Microsip (ARTICULO_ID). Crítico para updates.
    articulo_id_msip = models.IntegerField(
        unique=True, 
        db_index=True,
        verbose_name="ID Microsip (ARTICULO_ID)"
    )

    # Clave visible (ej. "A001")
    clave = models.CharField(
        max_length=50, 
        unique=True,
        verbose_name="Clave Alfanumérica Microsip"
    )

    nombre = models.CharField(max_length=150)

    # Tipo de seguimiento para validaciones (Lotes/Series)
    seguimiento_tipo = models.CharField(
        max_length=1, 
        choices=SEGUIMIENTO_CHOICES, 
        default='N',
        verbose_name="Tipo de Seguimiento"
    )

    # Soft Delete: Si se borra en Microsip, aquí solo se desactiva.
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    ultima_sincronizacion = models.DateTimeField(
        auto_now=True, 
        verbose_name="Última Sincronización"
    )

    class Meta:
        verbose_name = "Artículo Microsip"
        verbose_name_plural = "Artículos Microsip"

    def __str__(self):
        estado = " (Inactivo)" if not self.activo else ""
        return f"[{self.clave}] {self.nombre}{estado}"


class ClaveAuxiliar(models.Model):
    """
    Códigos de barras adicionales asociados a un Artículo.
    Permite escanear cualquier código y encontrar el artículo principal.
    """
    id = models.BigAutoField(primary_key=True)
    
    clave = models.CharField(
        max_length=50, 
        verbose_name="Clave Auxiliar / Código de Barras"
    )
    
    articulo = models.ForeignKey(
        Articulo, 
        on_delete=models.CASCADE, 
        related_name='claves_auxiliares'
    )
    
    class Meta:
        verbose_name = "Clave Auxiliar"
        verbose_name_plural = "Claves Auxiliares"
        unique_together = ('clave',) # Evita duplicados globales

    def __str__(self):
        return f"Clave {self.clave} -> {self.articulo.clave}"


class BitacoraSincronizacion(models.Model):
    """
    Historial de ejecuciones de la tarea de sincronización.
    Permite ver en el Admin si la tarea de Django Q tuvo éxito o falló.
    """
    STATUS_CHOICES = [
        ('EN_PROCESO', 'En Proceso'),
        ('EXITO', 'Éxito'),
        ('ERROR', 'Error'),
    ]

    fecha_inicio = models.DateTimeField(auto_now_add=True, verbose_name="Inicio")
    fecha_fin = models.DateTimeField(null=True, blank=True, verbose_name="Fin")
    
    # Métricas del proceso
    articulos_procesados = models.IntegerField(default=0, help_text="Leídos de Microsip")
    articulos_creados = models.IntegerField(default=0)
    articulos_actualizados = models.IntegerField(default=0)
    articulos_desactivados = models.IntegerField(default=0)
    claves_creadas = models.IntegerField(default=0)
    
    # Logs detallados (ej. IDs que fallaron)
    detalles_procesamiento = models.TextField(null=True, blank=True, verbose_name="Log Detalles")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='EN_PROCESO')
    mensaje_error = models.TextField(null=True, blank=True, verbose_name="Error Traceback")

    class Meta:
        verbose_name = "Bitácora de Sincronización"
        verbose_name_plural = "Bitácora de Sincronizaciones"
        ordering = ['-fecha_inicio']

    def __str__(self):
        return f"Sync {self.fecha_inicio.strftime('%Y-%m-%d %H:%M')} - {self.status}"