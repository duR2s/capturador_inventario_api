from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from .models import *

# --- 1. Serializadores de Usuario y Perfiles ---

class UserSerializer(serializers.ModelSerializer):
    """Serializador básico para el modelo User de Django."""
    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email", "username")


class AdministradoresSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True) 

    class Meta:
        model = Administradores
        fields = "__all__"
        read_only_fields = ['id', 'user', 'creation']


class CapturadoresSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Capturadores
        fields = "__all__"
        read_only_fields = ['id', 'user', 'creation']


# --- 2. Serializadores de Artículos y ClavesAuxiliares ---

class ArticuloSerializer(serializers.ModelSerializer):
    seguimiento_display = serializers.CharField(
        source='get_seguimiento_tipo_display', 
        read_only=True
    )
    
    class Meta:
        model = Articulo
        fields = "__all__"
        read_only_fields = ['id', 'ultima_sincronizacion']


class ClaveAuxiliarSerializer(serializers.ModelSerializer):
    articulo = ArticuloSerializer(read_only=True)

    class Meta:
        model = ClaveAuxiliar
        fields = "__all__"
        read_only_fields = ['id']


# --- 3. Serializadores de Captura y Detalle ---

class DetalleCapturaSerializer(serializers.ModelSerializer):
    """
    Serializador para los renglones de la Captura.
    """
    class Meta:
        model = DetalleCaptura
        fields = ['id', 'producto_codigo', 'cantidad_contada'] 
        read_only_fields = ['id']


class CapturaSerializer(serializers.ModelSerializer):
    """
    Serializador principal para el documento de Captura.
    Ahora incluye lógica para modo offline y validación de productos.
    """
    detalles = DetalleCapturaSerializer(many=True)
    
    capturador_nombre = serializers.CharField(
        source='capturador.username', 
        read_only=True
    )

    # Campos para control de Modo Offline (no existen en el modelo, son inputs)
    modo_offline = serializers.BooleanField(write_only=True, required=False, default=False)
    fecha_reportada = serializers.DateTimeField(write_only=True, required=False)

    class Meta:
        model = Captura
        fields = [
            'id', 
            'folio', 
            'capturador', 
            'capturador_nombre', 
            'fecha_captura', 
            'estado', 
            'detalles',
            'modo_offline',   # Input extra
            'fecha_reportada' # Input extra
        ]
        read_only_fields = ['id', 'capturador_nombre']
        # Nota: quitamos 'fecha_captura' de read_only_fields explícitos aquí para 
        # que no cause conflicto visual, aunque el modelo sea auto_now_add.

    def validate(self, data):
        """
        Validación global: Verifica que TODOS los códigos de producto existan en ClaveAuxiliar.
        """
        detalles = data.get('detalles', [])
        
        # 1. Extraer lista única de códigos enviados en el JSON
        codigos_enviados = {item['producto_codigo'] for item in detalles}
        
        if not codigos_enviados:
            raise serializers.ValidationError({"detalles": "La captura debe tener al menos un detalle."})

        # 2. Buscar estos códigos en la base de datos (ClaveAuxiliar)
        # Usamos filter(clave__in=...) para hacer UNA sola consulta eficiente
        codigos_encontrados = set(
            ClaveAuxiliar.objects.filter(clave__in=codigos_enviados).values_list('clave', flat=True)
        )

        # 3. Calcular la diferencia (Set difference)
        codigos_inexistentes = codigos_enviados - codigos_encontrados

        # 4. Si hay diferencias, rechazar la petición indicando cuáles fallaron
        if codigos_inexistentes:
            raise serializers.ValidationError({
                "error_integridad": "Códigos de producto no válidos o no encontrados en catálogo.",
                "codigos_fallidos": list(codigos_inexistentes)
            })

        return data

    def create(self, validated_data):
        """
        Crea la captura y sus detalles. Maneja la lógica de fecha offline.
        """
        detalles_data = validated_data.pop('detalles')
        modo_offline = validated_data.pop('modo_offline', False)
        fecha_reportada = validated_data.pop('fecha_reportada', None)

        # 1. Crear el encabezado (Captura)
        # Nota: 'fecha_captura' tiene auto_now_add=True, Django pondrá la fecha actual aquí.
        captura = Captura.objects.create(**validated_data)
        
        # 2. Lógica Offline: Sobrescribir fecha si es necesario
        if modo_offline and fecha_reportada:
            # Forzamos la actualización de la fecha
            captura.fecha_captura = fecha_reportada
            # update_fields es vital para evitar triggers innecesarios, pero con auto_now_add
            # a veces es mejor usar update() directo o save normal dependiendo de la config.
            # Aquí usamos save() directo modificando el atributo.
            captura.save()
        
        # 3. Crear los detalles
        objs_detalles = [
            DetalleCaptura(captura=captura, **detalle) 
            for detalle in detalles_data
        ]
        DetalleCaptura.objects.bulk_create(objs_detalles)
            
        return captura