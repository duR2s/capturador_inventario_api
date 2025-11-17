from rest_framework import serializers
from django.contrib.auth.models import User
from .models import *


# --- 1. Serializadores de Usuario y Perfiles ---

class UserSerializer(serializers.ModelSerializer):
    """Serializador básico para el modelo User de Django."""
    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email", "username") # Agregamos 'username' para referencia


class AdministradoresSerializer(serializers.ModelSerializer):
    """Serializador para el perfil de Administradores."""
    # Usamos el UserSerializer para representar los datos del usuario relacionado (lectura)
    user = UserSerializer(read_only=True) 

    class Meta:
        model = Administradores
        fields = "__all__"
        # Campos de lectura optimizados para la API
        read_only_fields = ['id', 'user', 'creation']


class CapturadoresSerializer(serializers.ModelSerializer):
    """Serializador para el perfil de Capturadores."""
    user = UserSerializer(read_only=True)

    class Meta:
        model = Capturadores
        fields = "__all__"
        read_only_fields = ['id', 'user', 'creation']


# --- 2. Serializadores de Artículos (Caché Microsip) ---

class ArticuloSerializer(serializers.ModelSerializer):
    """
    Serializador para el modelo de referencia Articulo (Caché Microsip).
    Se usa para mostrar al frontend los datos del artículo (incluyendo seguimiento).
    """
    # Mapear el valor de seguimiento (N, L, S) a su descripción para la UX
    seguimiento_display = serializers.CharField(
        source='get_seguimiento_tipo_display', 
        read_only=True
    )
    
    class Meta:
        model = Articulo
        fields = [
            'id', 
            'articulo_id_msip', 
            'clave', 
            'nombre', 
            'codigo_barras', 
            'seguimiento_tipo',
            'seguimiento_display', # Campo para mostrar 'Lotes (1)', 'Series (2)', etc.
            'ultima_sincronizacion'
        ]
        read_only_fields = ['id', 'ultima_sincronizacion']


# --- 3. Serializadores de Captura y Detalle ---

class DetalleCapturaSerializer(serializers.ModelSerializer):
    """
    Serializador para los renglones de la Captura. 
    Ideal para crear o listar los productos capturados.
    """
    class Meta:
        model = DetalleCaptura
        # No incluimos 'captura' para que se asigne en la vista/creación de la Captura
        fields = ['id', 'producto_codigo', 'cantidad_contada'] 
        read_only_fields = ['id']


class CapturaSerializer(serializers.ModelSerializer):
    """
    Serializador principal para el documento de Captura.
    Incluye los detalles (renglones) anidados para facilitar la creación/lectura completa.
    """
    # Renglones anidados (lectura/escritura)
    # Permite crear los detalles junto con la cabecera (Captura)
    detalles = DetalleCapturaSerializer(many=True) 
    
    # Campo de solo lectura para mostrar el nombre del capturador
    capturador_nombre = serializers.CharField(
        source='capturador.username', 
        read_only=True
    )

    class Meta:
        model = Captura
        fields = [
            'id', 
            'folio', 
            'capturador', 
            'capturador_nombre', 
            'fecha_captura', 
            'estado', 
            'detalles'
        ]
        read_only_fields = ['id', 'fecha_captura', 'capturador_nombre']
        
    def create(self, validated_data):
        """
        Sobreescribe el método create para manejar la creación de los detalles anidados.
        """
        # Extraemos los detalles de la lista validada para crearlos por separado
        detalles_data = validated_data.pop('detalles')
        
        # 1. Crear el encabezado (Captura)
        captura = Captura.objects.create(**validated_data)
        
        # 2. Crear los detalles y asignarlos a la captura
        for detalle_data in detalles_data:
            DetalleCaptura.objects.create(captura=captura, **detalle_data)
            
        return captura