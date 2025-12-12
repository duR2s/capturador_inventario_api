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
    # Nombre del artículo para mostrar en respuesta (readonly)
    articulo_nombre = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DetalleCaptura
        fields = ['id', 'captura', 'producto_codigo', 'cantidad_contada', 'articulo_nombre'] 
        read_only_fields = ['id', 'articulo_nombre']
        # 'captura' se puede enviar, pero si se usa en bulk sync por URL, se inyectará en el save()

    def get_articulo_nombre(self, obj):
        # Intenta buscar el nombre para dar feedback visual inmediato
        try:
            # Primero busca si es clave directa de Articulo
            art = Articulo.objects.filter(clave=obj.producto_codigo).first()
            if art: return art.nombre
            
            # Si no, busca en auxiliares
            aux = ClaveAuxiliar.objects.filter(clave=obj.producto_codigo).select_related('articulo').first()
            if aux: return aux.articulo.nombre
            
            return "Producto Desconocido"
        except:
            return "N/A"


class CapturaSerializer(serializers.ModelSerializer):
    detalles = DetalleCapturaSerializer(many=True, required=False) # Hacemos detalles opcional al crear cabecera
    
    capturador_nombre = serializers.CharField(
        source='capturador.username', 
        read_only=True
    )
    
    # Agregamos campo de lectura para mostrar nombre de almacén si se desea
    almacen_nombre = serializers.CharField(source='almacen.nombre', read_only=True)

    modo_offline = serializers.BooleanField(write_only=True, required=False, default=False)
    fecha_reportada = serializers.DateTimeField(write_only=True, required=False)

    class Meta:
        model = Captura
        fields = [
            'id', 
            'folio', 
            'capturador', 
            'capturador_nombre',
            'almacen',          # <--- AGREGADO: Necesario para guardar el almacén
            'almacen_nombre',   # <--- AGREGADO: Para lectura
            'fecha_captura', 
            'estado', 
            'detalles',
            'modo_offline',
            'fecha_reportada'
        ]
        read_only_fields = ['id', 'capturador_nombre', 'almacen_nombre']


    def create(self, validated_data):
        # Extraemos detalles si vienen, si no, lista vacía
        detalles_data = validated_data.pop('detalles', [])
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
    
class AlmacenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Almacen
        fields = ['id', 'almacen_id_msip', 'nombre', 'activo_web']