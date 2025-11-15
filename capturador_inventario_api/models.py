from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authentication import TokenAuthentication
from django.contrib.auth.models import AbstractUser, User
from django.conf import settings

from django.db import models
from django.contrib.auth.models import User

from rest_framework.authentication import TokenAuthentication

class BearerTokenAuthentication(TokenAuthentication):
    keyword = "Bearer"

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
    producto_codigo = models.CharField(max_length=100)
    cantidad_contada = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.cantidad_contada} de {self.producto_codigo} en folio {self.captura.folio}"
