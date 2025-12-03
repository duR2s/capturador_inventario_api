from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from .models import *

# --- 1. Serializadores de Usuario y Empleado ---

class UserSerializer(serializers.ModelSerializer):
    """Serializador básico para el modelo User de Django."""
    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email", "username")


class EmpleadoSerializer(serializers.ModelSerializer):
    """
    Serializador unificado para el modelo Empleado.
    Reemplaza a AdministradoresSerializer y CapturadoresSerializer.
    """
    user = UserSerializer(read_only=True)
    puesto_display = serializers.CharField(source='get_puesto_display', read_only=True)

    class Meta:
        model = Empleado
        fields = "__all__"
        read_only_fields = ['id', 'user', 'creation', 'puesto_display']


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
    class Meta:
        model = DetalleCaptura
        fields = ['id', 'producto_codigo', 'cantidad_contada'] 
        read_only_fields = ['id']


class CapturaSerializer(serializers.ModelSerializer):
    detalles = DetalleCapturaSerializer(many=True)
    
    capturador_nombre = serializers.CharField(
        source='capturador.username', 
        read_only=True
    )

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
            'modo_offline',
            'fecha_reportada'
        ]
        read_only_fields = ['id', 'capturador_nombre']

    def validate(self, data):
        detalles = data.get('detalles', [])
        codigos_enviados = {item['producto_codigo'] for item in detalles}
        
        if not codigos_enviados:
            raise serializers.ValidationError({"detalles": "La captura debe tener al menos un detalle."})

        codigos_encontrados = set(
            ClaveAuxiliar.objects.filter(clave__in=codigos_enviados).values_list('clave', flat=True)
        )

        codigos_inexistentes = codigos_enviados - codigos_encontrados

        if codigos_inexistentes:
            raise serializers.ValidationError({
                "error_integridad": "Códigos de producto no válidos o no encontrados en catálogo.",
                "codigos_fallidos": list(codigos_inexistentes)
            })

        return data

    def create(self, validated_data):
        detalles_data = validated_data.pop('detalles')
        modo_offline = validated_data.pop('modo_offline', False)
        fecha_reportada = validated_data.pop('fecha_reportada', None)

        captura = Captura.objects.create(**validated_data)
        
        if modo_offline and fecha_reportada:
            captura.fecha_captura = fecha_reportada
            captura.save()
        
        objs_detalles = [
            DetalleCaptura(captura=captura, **detalle) 
            for detalle in detalles_data
        ]
        DetalleCaptura.objects.bulk_create(objs_detalles)
            
        return captura