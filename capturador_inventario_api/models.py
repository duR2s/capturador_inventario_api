from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authentication import TokenAuthentication
from django.contrib.auth.models import AbstractUser, User
from django.conf import settings

# MODEL tokens

class BearerTokenAuthentication(TokenAuthentication):
    keyword = "Bearer"


# Models for Administradores, Capturadores
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


# Models for Captura, DetalleCaptura
class Captura(models.Model):
    id = models.BigAutoField(primary_key=True)
    folio = models.CharField(max_length=50, unique=True, null=False, blank=False)
    capturador = models.ForeignKey(User, on_delete=models.PROTECT, related_name="capturas")
    fecha_captura = models.DateTimeField(auto_now_add=True)
    # Podrías añadir un campo de estado
    ESTADO_CHOICES = [('PROGRESO', 'En Progreso'), ('COMPLETADO', 'Completado')]
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='PROGRESO')

    def __str__(self):
        return f"Captura {self.folio} por {self.capturador.username}"

class DetalleCaptura(models.Model):
    id = models.BigAutoField(primary_key=True)
    captura = models.ForeignKey(Captura, on_delete=models.CASCADE, related_name="detalles")
    producto_codigo = models.CharField(max_length=100) # Este es el código que introduce el usuario (puede ser clave o código de barras)
    cantidad_contada = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.cantidad_contada} de {self.producto_codigo} en folio {self.captura.folio}"


# Modelos para Microsip (Datos de Referencia Ligeros)

# Mapea ARTICULOS.SEGUIMIENTO (0: Ninguno, 1: Lote, 2: Serie)
SEGUIMIENTO_CHOICES = [
    ('N', 'Ninguno (0)'),
    ('L', 'Lotes (1)'),
    ('S', 'Series (2)'),
]

class Articulo(models.Model):
    """
    Modelo de referencia ligero para Artículos de Microsip.
    Sirve como caché de datos maestros.
    """
    id = models.BigAutoField(primary_key=True)

    # Campo CRÍTICO: El ID interno que RenglonEntrada acepta (ARTICULOS.ARTICULO_ID)
    articulo_id_msip = models.IntegerField(
        unique=True, 
        db_index=True,
        verbose_name="ID Microsip (ARTICULO_ID)"
    )

    # Clave alfanumérica visible (ARTICULOS.CLAVE o similar)
    clave = models.CharField(
        max_length=50, 
        unique=True,
        verbose_name="Clave Alfanumérica Microsip"
    )

    # Nombre/Descripción
    nombre = models.CharField(max_length=150)

    # Campo CRÍTICO: Mantiene el tipo de control (0, 1, 2)
    seguimiento_tipo = models.CharField(
        max_length=1, 
        choices=SEGUIMIENTO_CHOICES, 
        default='N',
        verbose_name="Tipo de Seguimiento"
    )

    # SOFT DELETE: Indica si el artículo sigue vigente en Microsip
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    # Metadata para control de caché
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
    Modelo para manejar claves secundarias, como códigos de barras,
    asociadas a un artículo principal (relación 1:N).
    """
    id = models.BigAutoField(primary_key=True)
    
    clave = models.CharField(
        max_length=50, 
        verbose_name="Clave Auxiliar / Código de Barras"
    )
    
    # Relación al artículo principal.
    articulo = models.ForeignKey(
        Articulo, 
        on_delete=models.CASCADE, 
        related_name='claves_auxiliares'
    )
    
    class Meta:
        verbose_name = "Clave Auxiliar"
        verbose_name_plural = "Claves Auxiliares"
        # CRÍTICO: Asegura que el código de barras/clave sea único a nivel global.
        unique_together = ('clave',)

    def __str__(self):
        return f"Clave {self.clave} para Articulo ID {self.articulo.articulo_id_msip}"