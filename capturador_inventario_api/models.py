from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone 
from rest_framework.authentication import TokenAuthentication

# -------------------------------------------------------------------------
# 1. GESTIÓN DE USUARIOS Y EMPLEADOS
# -------------------------------------------------------------------------

class Empleado(models.Model):
    PUESTO_CHOICES = [
        ('ADMIN', 'Administrador'),
        ('CAPTURADOR', 'Capturador de Almacén'),
        ('OTRO', 'Otro Empleado'),
    ]

    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='empleado')
    
    # Datos laborales
    clave_interna = models.CharField(max_length=255, null=True, blank=True, help_text="ID de trabajador o Clave Admin en Microsip")
    puesto = models.CharField(max_length=50, choices=PUESTO_CHOICES, default='CAPTURADOR')
    
    # Datos personales
    telefono = models.CharField(max_length=255, null=True, blank=True)
    rfc = models.CharField(max_length=13, null=True, blank=True, help_text="RFC del empleado")
    fecha_nacimiento = models.DateField(null=True, blank=True)
    edad = models.IntegerField(null=True, blank=True)
    
    creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_puesto_display()}"


# -------------------------------------------------------------------------
# 2. CATÁLOGO DE ARTÍCULOS
# -------------------------------------------------------------------------

class Articulo(models.Model):
    id = models.BigAutoField(primary_key=True)
    articulo_id_msip = models.IntegerField(unique=True, db_index=True, verbose_name="ID MSIP")
    clave = models.CharField(max_length=50, db_index=True, unique=True, help_text="Clave Principal (Rol 17)")
    nombre = models.CharField(max_length=255, db_index=True)
    
    costo_ultimo = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    precio_lista = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    
    seguimiento_tipo = models.CharField(max_length=1, default='N', choices=[('N', 'Normal'), ('L', 'Lotes'), ('S', 'Series')])
    
    activo = models.BooleanField(default=True)
    ultima_sincronizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Artículo"
        verbose_name_plural = "Artículos"
        indexes = [
            models.Index(fields=['nombre', 'activo']),
        ]

    def __str__(self):
        return f"{self.clave} - {self.nombre}"


class ClaveAuxiliar(models.Model):
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, related_name='claves_auxiliares')
    clave = models.CharField(max_length=50, db_index=True)
    rol_clave_msip = models.IntegerField(default=18)

    class Meta:
        verbose_name = "Clave Auxiliar"
        verbose_name_plural = "Claves Auxiliares"
        unique_together = ('articulo', 'clave')

    def __str__(self):
        return f"{self.clave} ({self.articulo.clave})"


# -------------------------------------------------------------------------
# 3. INVENTARIO Y UBICACIONES
# -------------------------------------------------------------------------

class Almacen(models.Model):
    id = models.BigAutoField(primary_key=True)
    almacen_id_msip = models.IntegerField(unique=True)
    nombre = models.CharField(max_length=100)
    activo_web = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class InventarioArticulo(models.Model):
    id = models.BigAutoField(primary_key=True)
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, related_name='existencias_almacen')
    almacen = models.ForeignKey(Almacen, on_delete=models.CASCADE, related_name='inventario')
    
    localizacion = models.CharField(max_length=50, blank=True, null=True, verbose_name="Ubicación", db_index=True)
    existencia = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    
    stock_minimo = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    stock_maximo = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    punto_reorden = models.DecimalField(max_digits=18, decimal_places=5, default=0)

    pendiente_sincronizar_msip = models.BooleanField(default=False, help_text="True si se editó localmente y falta enviar a Microsip")
    fecha_ultima_modificacion_local = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Inventario por Almacén"
        unique_together = ('articulo', 'almacen')
        indexes = [
            models.Index(fields=['articulo', 'almacen']),
        ]

    def __str__(self):
        return f"{self.articulo.clave} en {self.almacen.nombre}: {self.existencia}"


# -------------------------------------------------------------------------
# 4. OPERACIONES Y LOGS
# -------------------------------------------------------------------------

class BitacoraSincronizacion(models.Model):
    STATUS_CHOICES = [
        ('EN_PROCESO', 'En Proceso'),
        ('EXITO', 'Éxito'),
        ('ERROR', 'Error'),
    ]

    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    
    articulos_procesados = models.IntegerField(default=0)
    articulos_creados = models.IntegerField(default=0)
    articulos_actualizados = models.IntegerField(default=0)
    articulos_desactivados = models.IntegerField(default=0)
    
    detalles = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='EN_PROCESO')
    mensaje_error = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Sync {self.fecha_inicio.strftime('%Y-%m-%d %H:%M')} - {self.status}"


class Captura(models.Model):
    ESTADOS = [
        ('BORRADOR', 'Borrador'),
        ('CONFIRMADO', 'Confirmado'),
        ('PROCESADO', 'Procesado'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    folio = models.CharField(max_length=50, unique=True)
    almacen = models.ForeignKey(Almacen, on_delete=models.SET_NULL, null=True)
    capturador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='capturas')
    
    fecha_captura = models.DateTimeField(default=timezone.now)
    
    estado = models.CharField(max_length=20, choices=ESTADOS, default='BORRADOR')
    detalles_texto = models.TextField(blank=True, null=True)
    modo_offline = models.BooleanField(default=False)
    fecha_reportada = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Captura {self.folio} - {self.estado}"


class DetalleCaptura(models.Model):
    captura = models.ForeignKey(Captura, related_name='detalles', on_delete=models.CASCADE)
    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT, null=True, blank=True)
    
    cantidad_contada = models.DecimalField(max_digits=18, decimal_places=5)
    existencia_sistema_al_momento = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    localizacion_al_momento = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        unique_together = ('captura', 'articulo')

    def __str__(self):
        clave = self.articulo.clave if self.articulo else "SIN_ARTICULO"
        return f"{clave}: Contado {self.cantidad_contada}"

# --- NUEVO MODELO: TICKET SALIDA ---
class TicketSalida(models.Model):
    """
    Documenta la salida de mercancía que estaba siendo capturada.
    La cantidad aquí registrada se RESTA de la cantidad_contada del detalle padre.
    """
    detalle = models.ForeignKey(DetalleCaptura, on_delete=models.CASCADE, related_name='tickets')
    responsable = models.CharField(max_length=255, verbose_name="Persona que retira")
    cantidad = models.DecimalField(max_digits=18, decimal_places=5)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket: {self.cantidad} pzas - {self.responsable}"


# -------------------------------------------------------------------------
# 5. CLASES EXTRA (Authentication)
# -------------------------------------------------------------------------

class BearerTokenAuthentication(TokenAuthentication):
    keyword = 'Bearer'