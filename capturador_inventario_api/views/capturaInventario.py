from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.shortcuts import get_object_or_404
from ..models import Captura, DetalleCaptura
from ..serializers import CapturaSerializer, DetalleCapturaSerializer

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


class SincronizarCapturaView(APIView):
    """
    Endpoint: POST /api/inventario/captura/{pk}/sincronizar/
    Recibe un ARRAY de detalles para insertar masivamente en una captura existente.
    Útil para la recuperación de conexión (Offline -> Online).
    """
    def post(self, request, pk, *args, **kwargs):
        captura = get_object_or_404(Captura, pk=pk)

        # Se espera una lista de objetos JSON: [{"producto_codigo": "X", "cantidad_contada": 1}, ...]
        if not isinstance(request.data, list):
            return Response(
                {"error": "Se esperaba una lista (array) de detalles."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Usamos many=True para validar la lista completa
        serializer = DetalleCapturaSerializer(data=request.data, many=True)

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    # Guardamos inyectando la instancia de captura padre
                    serializer.save(captura=captura)
                
                # RETORNO DE SINCRONIZACIÓN:
                # Devolvemos LA LISTA COMPLETA actualizada de la BD para que el frontend
                # reemplace su estado local y asegure consistencia total.
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
        # Esperamos { "captura_id": 1, "producto_codigo": "...", "cantidad_contada": ... }
        # Ojo: El serializador espera 'captura' como ID.
        data = request.data.copy()
        
        # Mapeo simple por si el frontend envía 'captura_id' en lugar de 'captura'
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