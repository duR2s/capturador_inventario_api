from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
import datetime # Importante para obtener el año actual
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


# --- NUEVO SERIALIZADOR DE TICKET ---
class TicketSalidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketSalida
        fields = ['id', 'detalle', 'responsable', 'cantidad', 'fecha_hora']
        read_only_fields = ['id', 'fecha_hora']


# --- 3. Serializadores de Captura y Detalle ---

class DetalleCapturaSerializer(serializers.ModelSerializer):
    # Campo opcional para buscar por texto (legacy/backup)
    producto_codigo = serializers.CharField(write_only=True, required=False, allow_blank=True) 
    
    # NUEVO: Campo para recibir el ID directo del artículo (Prioridad Alta)
    articulo_id = serializers.IntegerField(write_only=True, required=False)

    articulo_nombre = serializers.SerializerMethodField(read_only=True)
    
    tickets = TicketSalidaSerializer(many=True, read_only=True)
    conteo_tickets = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DetalleCaptura
        fields = [
            'id', 
            'captura', 
            'articulo',       # Este es el FK (read_only por defecto en ModelSerializer si no se especifica input)
            'articulo_id',    # Input explícito para ID
            'producto_codigo', 
            'cantidad_contada', 
            'articulo_nombre',
            'existencia_sistema_al_momento',
            'tickets',         
            'conteo_tickets'   
        ] 
        # 'articulo' se envía en el response automáticamente con el ID del objeto relacionado
        read_only_fields = ['id', 'articulo', 'articulo_nombre', 'existencia_sistema_al_momento', 'tickets', 'conteo_tickets']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.articulo:
            ret['producto_codigo'] = instance.articulo.clave
        else:
            ret['producto_codigo'] = 'SIN_CODIGO'
        return ret

    def create(self, validated_data):
        # 1. Intentar obtener por ID directo (Más seguro)
        id_art = validated_data.pop('articulo_id', None)
        
        # 2. Obtener código de barras como fallback
        codigo_raw = validated_data.pop('producto_codigo', '')
        
        articulo = None
        
        if id_art:
            articulo = Articulo.objects.filter(pk=id_art).first()
        
        # Si no se envió ID o no existe, buscamos por clave
        if not articulo and codigo_raw:
            codigo = str(codigo_raw).strip()
            articulo = Articulo.objects.filter(clave__iexact=codigo).first()
            if not articulo:
                aux = ClaveAuxiliar.objects.filter(clave__iexact=codigo).select_related('articulo').first()
                if aux:
                    articulo = aux.articulo
        
        if not articulo:
            raise serializers.ValidationError({
                "producto_codigo": f"No se encontró el artículo (ID: {id_art} o Clave: {codigo_raw})."
            })

        captura = validated_data.get('captura')
        cantidad_nueva = validated_data.get('cantidad_contada')

        # Buscar si ya existe este artículo en esta captura para sumar
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

    def get_conteo_tickets(self, obj):
        total = sum(t.cantidad for t in obj.tickets.all())
        return total


class CapturaSerializer(serializers.ModelSerializer):
    detalles = DetalleCapturaSerializer(many=True, required=False)
    
    capturador_nombre = serializers.CharField(source='capturador.username', read_only=True)
    almacen_nombre = serializers.CharField(source='almacen.nombre', read_only=True)
    
    # Hacemos que el folio sea read_only para que no importe lo que mande el front
    folio = serializers.CharField(required=False, read_only=True) 

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
        read_only_fields = ['id', 'capturador_nombre', 'almacen_nombre', 'folio']

    def create(self, validated_data):
        detalles_data = validated_data.pop('detalles', [])
        modo_offline = validated_data.pop('modo_offline', False)
        fecha_reportada = validated_data.pop('fecha_reportada', None)

        # --- LÓGICA DE GENERACIÓN DE FOLIO ---
        # 1. Obtenemos el año actual
        anio = datetime.date.today().year
        prefix = f"INV-{anio}"
        
        # 2. Buscamos el último folio de este año para incrementar
        # Asumimos formato INV-YYYY-XXXX (ej INV-2025-0001)
        ultimo = Captura.objects.filter(folio__startswith=prefix).order_by('-id').first()
        
        if ultimo:
            try:
                # Extraemos la parte numérica final (despues del último guión)
                secuencia = int(ultimo.folio.split('-')[-1]) + 1
            except:
                secuencia = 1
        else:
            secuencia = 1

        # 3. Formateamos a 4 digitos (rellenando con ceros)
        nuevo_folio = f"{prefix}-{str(secuencia).zfill(4)}"
        
        validated_data['folio'] = nuevo_folio
        # -------------------------------------

        captura = Captura.objects.create(**validated_data)
        
        if modo_offline and fecha_reportada:
            captura.fecha_captura = fecha_reportada
            captura.save()
        
        objs_detalles = []
        for detalle in detalles_data:
            id_art = detalle.get('articulo_id', None)
            codigo_raw = detalle.get('producto_codigo', '')
            
            articulo = None
            if id_art:
                 articulo = Articulo.objects.filter(pk=id_art).first()
            
            if not articulo and codigo_raw:
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