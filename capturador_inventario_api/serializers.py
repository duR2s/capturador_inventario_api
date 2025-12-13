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
    # Campo de entrada (texto) para recibir "23", "COCA600", etc.
    producto_codigo = serializers.CharField(write_only=True) 
    
    # Campo de salida para mostrar el nombre en la respuesta
    articulo_nombre = serializers.SerializerMethodField(read_only=True)
    
    # Campo de salida para devolver el código real encontrado
    codigo_confirmado = serializers.CharField(source='articulo.clave', read_only=True)

    class Meta:
        model = DetalleCaptura
        fields = [
            'id', 
            'captura', 
            'producto_codigo',   # Entrada
            'codigo_confirmado', # Salida
            'cantidad_contada', 
            'articulo_nombre',
            'existencia_sistema_al_momento'
        ] 
        read_only_fields = ['id', 'articulo_nombre', 'codigo_confirmado', 'existencia_sistema_al_momento']

    def create(self, validated_data):
        # 1. Extraemos y limpiamos el código
        codigo_raw = validated_data.pop('producto_codigo', '')
        codigo = str(codigo_raw).strip() # Quitamos espacios al inicio/final

        print(f"\n[DEBUG] --- Iniciando búsqueda de producto ---")
        print(f"[DEBUG] Código recibido raw: '{codigo_raw}'")
        print(f"[DEBUG] Código limpio: '{codigo}'")

        # 2. Búsqueda del Artículo (Insensible a mayúsculas)
        articulo = Articulo.objects.filter(clave__iexact=codigo).first()
        
        if articulo:
            print(f"[DEBUG] ¡ENCONTRADO en Articulos! ID: {articulo.id}, Nombre: {articulo.nombre}")
        else:
            print(f"[DEBUG] No encontrado en Articulo principal. Buscando en auxiliares...")
            aux = ClaveAuxiliar.objects.filter(clave__iexact=codigo).select_related('articulo').first()
            if aux:
                articulo = aux.articulo
                print(f"[DEBUG] ¡ENCONTRADO en Auxiliares! ID: {articulo.id}, Nombre: {articulo.nombre}")
            else:
                print(f"[DEBUG] X NO ENCONTRADO en ninguna tabla.")
        
        # 3. Validación final
        if not articulo:
            raise serializers.ValidationError({
                "producto_codigo": f"No se encontró el artículo '{codigo}' en el catálogo."
            })

        # ---------------------------------------------------------------------
        # Lógica UPSERT (Sumar si ya existe en la captura)
        # ---------------------------------------------------------------------
        captura = validated_data.get('captura')
        cantidad_nueva = validated_data.get('cantidad_contada')

        detalle_existente = DetalleCaptura.objects.filter(captura=captura, articulo=articulo).first()

        if detalle_existente:
            print(f"[DEBUG] El artículo ya estaba en la captura. Sumando cantidad (+{cantidad_nueva}).")
            detalle_existente.cantidad_contada += cantidad_nueva
            detalle_existente.save()
            return detalle_existente
        
        else:
            print(f"[DEBUG] Creando nuevo registro de detalle.")
            validated_data['articulo'] = articulo
            
            # Snapshot de existencia teórica
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