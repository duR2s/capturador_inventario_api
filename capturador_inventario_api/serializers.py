from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from .models import *

# --- 1. Serializadores de Usuario y Empleado ---

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email", "username")


class EmpleadoSerializer(serializers.ModelSerializer):
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
    # Campo de entrada: Lo definimos write_only para que DRF no intente buscarlo en el modelo al leer.
    producto_codigo = serializers.CharField(write_only=True) 
    
    # Campos de salida
    articulo_nombre = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DetalleCaptura
        fields = [
            'id', 
            'captura', 
            'articulo',
            'producto_codigo', # Unificado: Entrada y Salida (vía to_representation)
            'cantidad_contada', 
            'articulo_nombre',
            'existencia_sistema_al_momento'
        ] 
        read_only_fields = ['id', 'articulo', 'articulo_nombre', 'existencia_sistema_al_momento']

    # MAGIA AQUÍ: Sobreescribimos la representación de salida
    # para inyectar el valor de la clave en 'producto_codigo'
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.articulo:
            ret['producto_codigo'] = instance.articulo.clave
        else:
            ret['producto_codigo'] = 'SIN_CODIGO'
        return ret

    def create(self, validated_data):
        codigo_raw = validated_data.pop('producto_codigo', '')
        codigo = str(codigo_raw).strip()

        articulo = Articulo.objects.filter(clave__iexact=codigo).first()
        
        if not articulo:
            aux = ClaveAuxiliar.objects.filter(clave__iexact=codigo).select_related('articulo').first()
            if aux:
                articulo = aux.articulo
        
        if not articulo:
            raise serializers.ValidationError({
                "producto_codigo": f"No se encontró el artículo '{codigo}' en el catálogo."
            })

        captura = validated_data.get('captura')
        cantidad_nueva = validated_data.get('cantidad_contada')

        # Buscamos por ID de articulo dentro de la captura para evitar duplicados
        detalle_existente = DetalleCaptura.objects.filter(captura=captura, articulo=articulo).first()

        if detalle_existente:
            detalle_existente.cantidad_contada += cantidad_nueva
            detalle_existente.save()
            return detalle_existente
        
        else:
            validated_data['articulo'] = articulo
            if captura and captura.almacen:
                inv = InventarioArticulo.objects.filter(articulo=articulo, almacen=captura.almacen).first()
                if inv:
                    validated_data['existencia_sistema_al_momento'] = inv.existencia

            return super().create(validated_data)

    def get_articulo_nombre(self, obj):
        if obj.articulo:
            return obj.articulo.nombre
        return "Producto Desconocido"


class CapturaSerializer(serializers.ModelSerializer):
    detalles = DetalleCapturaSerializer(many=True, required=False)
    
    capturador_nombre = serializers.CharField(source='capturador.username', read_only=True)
    almacen_nombre = serializers.CharField(source='almacen.nombre', read_only=True)
    modo_offline = serializers.BooleanField(write_only=True, required=False, default=False)
    fecha_reportada = serializers.DateTimeField(write_only=True, required=False)

    class Meta:
        model = Captura
        fields = [
            'id', 'folio', 'capturador', 'capturador_nombre',
            'almacen', 'almacen_nombre',
            'fecha_captura', 'estado', 'detalles',
            'modo_offline', 'fecha_reportada'
        ]
        read_only_fields = ['id', 'capturador_nombre', 'almacen_nombre']

    def create(self, validated_data):
        detalles_data = validated_data.pop('detalles', [])
        modo_offline = validated_data.pop('modo_offline', False)
        fecha_reportada = validated_data.pop('fecha_reportada', None)

        captura = Captura.objects.create(**validated_data)
        
        if modo_offline and fecha_reportada:
            captura.fecha_captura = fecha_reportada
            captura.save()
        
        objs_detalles = []
        for detalle in detalles_data:
            codigo_raw = detalle.get('producto_codigo', '')
            codigo = str(codigo_raw).strip()
            
            articulo = Articulo.objects.filter(clave__iexact=codigo).first()
            if not articulo:
                 aux = ClaveAuxiliar.objects.filter(clave__iexact=codigo).select_related('articulo').first()
                 if aux: articulo = aux.articulo
            
            if articulo:
                objs_detalles.append(DetalleCaptura(
                    captura=captura, 
                    articulo=articulo, 
                    cantidad_contada=detalle['cantidad_contada']
                ))

        if objs_detalles:
            DetalleCaptura.objects.bulk_create(objs_detalles)
            
        return captura

class AlmacenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Almacen
        fields = ['id', 'almacen_id_msip', 'nombre', 'activo_web']