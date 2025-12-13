from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.shortcuts import get_object_or_404
# Asegúrate de importar Almacen y sus serializadores
from ..models import Captura, DetalleCaptura, Almacen, Articulo, ClaveAuxiliar
from ..serializers import CapturaSerializer, DetalleCapturaSerializer, AlmacenSerializer, ArticuloSerializer

class AlmacenOptionsView(APIView):
    """
    Endpoint: GET /api/inventario/almacenes/
    Lista los almacenes activos para llenar selects.
    """
    def get(self, request, *args, **kwargs):
        try:
            almacenes = Almacen.objects.filter(activo_web=True).order_by('nombre')
            serializer = AlmacenSerializer(almacenes, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ArticuloBusquedaView(APIView):
    """
    Endpoint: GET /api/inventario/buscar-articulo/?codigo=XYZ
    NUEVO: Busca un artículo por código principal o auxiliar y retorna su data
    (ID, Nombre, Clave) sin crear registros.
    """
    def get(self, request, *args, **kwargs):
        codigo = request.query_params.get('codigo', '').strip()
        if not codigo:
            return Response({"error": "Código no proporcionado"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Buscar en Articulos (Clave Principal)
        articulo = Articulo.objects.filter(clave__iexact=codigo).first()

        # 2. Buscar en Claves Auxiliares si no se encontró
        if not articulo:
            aux = ClaveAuxiliar.objects.filter(clave__iexact=codigo).select_related('articulo').first()
            if aux:
                articulo = aux.articulo
        
        if articulo:
            # Usamos el serializador existente o construimos una respuesta simple
            data = {
                "id": articulo.id,
                "clave": articulo.clave,
                "nombre": articulo.nombre,
                "existencia_teorica": 0 # Placeholder si quisieras mostrar existencia actual
            }
            return Response(data, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Producto no encontrado"}, status=status.HTTP_404_NOT_FOUND)

class CapturaInventarioView(APIView):
    """
    Endpoint: POST /api/inventario/captura/
    Crea una captura NUEVA con sus detalles iniciales.
    """
    def post(self, request, *args, **kwargs):
        serializer = CapturaSerializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    captura = serializer.save()
                return Response({
                    "mensaje": "Captura guardada exitosamente.",
                    "folio": captura.folio,
                    "id": captura.id,
                    "fecha_registrada": captura.fecha_captura
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({
                    "error": "Error interno al procesar la captura.",
                    "detalle": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CapturaDetailView(APIView):
    """
    Endpoint: GET /api/inventario/captura/<int:pk>/
    Recupera una captura completa (Cabecera + Detalles) por su ID.
    """
    def get(self, request, pk, *args, **kwargs):
        captura = get_object_or_404(Captura, pk=pk)
        serializer = CapturaSerializer(captura)
        return Response(serializer.data, status=status.HTTP_200_OK)

class SincronizarCapturaView(APIView):
    """
    Endpoint: POST /api/inventario/captura/{pk}/sincronizar/
    Recibe un ARRAY de detalles para insertar masivamente.
    """
    def post(self, request, pk, *args, **kwargs):
        captura = get_object_or_404(Captura, pk=pk)

        if not isinstance(request.data, list):
            return Response(
                {"error": "Se esperaba una lista (array) de detalles."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = DetalleCapturaSerializer(data=request.data, many=True)

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    serializer.save(captura=captura)
                
                todos_los_detalles = DetalleCaptura.objects.filter(captura=captura).order_by('-id')
                respuesta_serializer = DetalleCapturaSerializer(todos_los_detalles, many=True)
                
                return Response(respuesta_serializer.data, status=status.HTTP_200_OK)

            except Exception as e:
                return Response({
                    "error": "Error durante la sincronización masiva.",
                    "detalle": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DetalleIndividualView(APIView):
    """
    Endpoint: POST /api/inventario/detalle/
    Para el modo Online: agrega un solo registro.
    """
    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        if 'captura_id' in data:
            data['captura'] = data.pop('captura_id')

        serializer = DetalleCapturaSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk, *args, **kwargs):
        detalle = get_object_or_404(DetalleCaptura, pk=pk)
        detalle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, pk, *args, **kwargs):
        detalle = get_object_or_404(DetalleCaptura, pk=pk)
        serializer = DetalleCapturaSerializer(detalle, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)